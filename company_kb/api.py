"""FastAPI 后端：为前端提供知识库问答接口。

端点：
    POST   /api/register                   注册（用户名+密码，开放自助注册）
    POST   /api/login                       登录，签发令牌
    POST   /api/logout                      登出，失效令牌
    GET    /api/me                          当前登录用户
    GET    /api/health                     健康检查 + 库状态
    GET    /api/models                     可用模型列表
    GET    /api/documents                  已入库文档列表（全员共享）
    POST   /api/upload                     上传文档入库（全员共享）
    POST   /api/documents/delete           删除文档
    GET    /api/conversations              会话列表（当前用户私有）
    POST   /api/conversations              新建会话
    GET    /api/conversations/{id}         会话全部消息
    PATCH  /api/conversations/{id}         重命名会话
    DELETE /api/conversations/{id}         删除会话
    POST   /api/ask                        问答（流式 SSE，落库 + 多轮上下文）

鉴权：除注册/登录/健康检查外，均需请求头 X-KB-Token 携带登录令牌。

启动：
    python api.py             # 监听 127.0.0.1:8994
"""
import json
import threading
from pathlib import Path

import chromadb
import uvicorn
from fastembed import TextEmbedding
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import config
import ingest
import store
from query import SYSTEM_PROMPT, retrieve, build_prompt

app = FastAPI(title="企业知识库 API")

# 前端与后端可能不同源（3030 vs 8994），放开 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局单例：模型和向量库只加载一次
STATE = {"embedder": None, "embedder_error": None, "coll": None}
# 写库（上传/删除）需串行，避免并发写 ChromaDB
_WRITE_LOCK = threading.Lock()


def _load_embedder():
    """按需加载 Embedding；避免服务启动时因外网不可达而整体失败。"""
    if STATE["embedder"] is not None:
        return STATE["embedder"]
    try:
        STATE["embedder"] = TextEmbedding(model_name=config.EMBED_MODEL)
        STATE["embedder_error"] = None
        return STATE["embedder"]
    except BaseException as e:
        STATE["embedder"] = None
        STATE["embedder_error"] = str(e)
        return None


@app.on_event("startup")
def _load():
    # 初始化会话历史库（标准库 sqlite3，幂等建表）
    store.init_db()
    # 启动阶段只打开已有向量库，不加载 embedding 模型。
    # 首次加载模型可能需要访问 HuggingFace；若服务器网络不可达，
    # 也应保证健康检查、文档列表、前端页面可用。
    try:
        client = chromadb.PersistentClient(path=str(config.DB_DIR))
        STATE["coll"] = client.get_collection(config.COLLECTION)
    except Exception:
        STATE["coll"] = None  # 库未建立
    # 会话历史库：标准库 sqlite3，建表幂等，失败不影响问答主流程。
    try:
        store.init_db()
    except Exception:
        pass


def _ensure_coll():
    """返回集合；若尚未建库则创建一个空集合（首次上传时用）。"""
    if STATE["coll"] is None:
        client = ingest.get_client()
        STATE["coll"] = ingest.open_or_create_collection(client)
    return STATE["coll"]


class AskReq(BaseModel):
    question: str
    model: str | None = None
    conversation_id: str | None = None


class NewConvReq(BaseModel):
    title: str | None = None
    model: str | None = None


class RenameReq(BaseModel):
    title: str


class AuthReq(BaseModel):
    username: str
    password: str


# ---- 鉴权 --------------------------------------------------------------

def current_user(x_kb_token: str | None = Header(default=None)) -> dict:
    """依赖：从 X-KB-Token 头解析当前用户；无效令牌返回 401。"""
    user = store.user_for_token(x_kb_token or "")
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


@app.post("/api/register")
def register(req: AuthReq):
    """开放自助注册。用户名唯一，密码存哈希。"""
    username = (req.username or "").strip()
    password = req.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(username) > 40:
        raise HTTPException(status_code=400, detail="用户名过长（≤40）")
    if len(password) < config.PASSWORD_MIN_LEN:
        raise HTTPException(status_code=400,
                            detail=f"密码至少 {config.PASSWORD_MIN_LEN} 位")
    user = store.create_user(username, password)
    if user is None:
        raise HTTPException(status_code=409, detail="用户名已被占用")
    token = store.create_session(user["id"])
    return {"token": token, "username": user["username"]}


@app.post("/api/login")
def login(req: AuthReq):
    """用户名/密码登录，签发令牌。"""
    user = store.verify_user((req.username or "").strip(), req.password or "")
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = store.create_session(user["id"])
    return {"token": token, "username": user["username"]}


@app.post("/api/logout")
def logout(x_kb_token: str | None = Header(default=None)):
    """登出：使当前令牌失效（无令牌也返回成功，幂等）。"""
    if x_kb_token:
        store.delete_session(x_kb_token)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "username": user["username"]}


@app.get("/api/health")
def health():
    coll = STATE["coll"]
    count = coll.count() if coll else 0
    return {"ok": True, "indexed": coll is not None, "chunks": count,
            "model": config.CHAT_MODEL,
            "embedder_ready": STATE["embedder"] is not None,
            "embedder_error": STATE.get("embedder_error")}


@app.get("/api/models")
def models():
    return {"default": config.CHAT_MODEL, "fallback": config.FALLBACK_MODEL,
            "options": ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
                        "claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"]}


# ---- 会话管理 ----------------------------------------------------------

@app.get("/api/conversations")
def list_conversations(user: dict = Depends(current_user)):
    """当前用户的会话列表，按最近更新倒序。"""
    return {"conversations": store.list_conversations(user["id"])}


@app.post("/api/conversations")
def create_conversation(req: NewConvReq, user: dict = Depends(current_user)):
    """新建空会话（归当前用户）。"""
    conv = store.create_conversation(
        user["id"],
        title=(req.title or "新对话").strip() or "新对话",
        model=req.model,
    )
    return conv


@app.get("/api/conversations/{cid}")
def get_conversation(cid: str, user: dict = Depends(current_user)):
    """取会话全部消息（仅限本人会话）。"""
    conv = store.get_conversation(cid, user["id"])
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@app.patch("/api/conversations/{cid}")
def rename_conversation(cid: str, req: RenameReq,
                        user: dict = Depends(current_user)):
    """重命名会话（仅限本人会话）。"""
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if not store.rename_conversation(cid, user["id"], title[:120]):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "id": cid, "title": title[:120]}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: str, user: dict = Depends(current_user)):
    """删除会话及其全部消息（仅限本人会话）。"""
    if not store.delete_conversation(cid, user["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "id": cid}


@app.get("/api/documents")
def documents(user: dict = Depends(current_user)):
    """列出已入库的文档及其块数（全员共享）。"""
    coll = STATE["coll"]
    if coll is None:
        return {"documents": [], "total": 0}
    docs = ingest.list_sources(coll)
    return {"documents": docs, "total": sum(d["chunks"] for d in docs)}


@app.post("/api/upload")
def upload(files: list[UploadFile] = File(...),
           user: dict = Depends(current_user)):
    """上传文档：保存到 documents/，解析切块向量化后增量写入向量库。

    支持 txt/md/docx/pdf/xlsx。重复上传同名文件会覆盖旧内容。
    """
    if _load_embedder() is None:
        raise HTTPException(status_code=503, detail=f"Embedding 模型未就绪：{STATE.get('embedder_error') or 'unknown error'}")
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    with _WRITE_LOCK:
        coll = _ensure_coll()
        for uf in files:
            name = Path(uf.filename or "").name
            ext = Path(name).suffix.lower()
            if not name:
                results.append({"file": uf.filename, "status": "error",
                                "msg": "文件名为空"})
                continue
            if ext not in ingest.SUPPORTED_EXTS:
                results.append({"file": name, "status": "error",
                                "msg": f"不支持的格式 {ext}，仅支持 "
                                       f"{', '.join(ingest.SUPPORTED_EXTS)}"})
                continue
            dest = config.DOCS_DIR / name
            try:
                data = uf.file.read()
                dest.write_bytes(data)
                n = ingest.ingest_file(STATE["embedder"], coll, dest)
                if n == 0:
                    results.append({"file": name, "status": "warn",
                                    "msg": "未提取到文本内容（已保存文件）"})
                else:
                    results.append({"file": name, "status": "ok",
                                    "msg": f"已入库 {n} 个知识块", "chunks": n})
            except Exception as e:
                results.append({"file": name, "status": "error", "msg": str(e)})
    ok = sum(1 for r in results if r["status"] == "ok")
    return {"results": results, "ok": ok, "chunks": coll.count()}


class DeleteReq(BaseModel):
    source: str


@app.post("/api/documents/delete")
def delete_document(req: DeleteReq, user: dict = Depends(current_user)):
    """从向量库删除指定来源(文件名)的全部块，并删除磁盘上的原文件。"""
    coll = STATE["coll"]
    if coll is None:
        raise HTTPException(status_code=404, detail="知识库为空")
    name = Path(req.source).name
    with _WRITE_LOCK:
        try:
            ingest.delete_source(coll, name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        f = config.DOCS_DIR / name
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
    return {"ok": True, "source": name, "chunks": coll.count()}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _title_from(question: str) -> str:
    """用首条问题截断生成会话标题。"""
    t = " ".join(question.split())
    return (t[:24] + "…") if len(t) > 24 else (t or "新对话")


@app.post("/api/ask")
def ask(req: AskReq, user: dict = Depends(current_user)):
    """流式问答：先返回来源，再逐段返回答案。

    带 conversation_id 时：落库用户消息与助手回答，并把本会话最近若干轮
    历史一并发给大模型，实现多轮上下文。
    """
    if _load_embedder() is None:
        def no_embedder():
            yield _sse("error", {"message": f"Embedding 模型未就绪：{STATE.get('embedder_error') or 'unknown error'}"})
        return StreamingResponse(no_embedder(), media_type="text/event-stream")
    coll = STATE["coll"]
    if coll is None or coll.count() == 0:
        def empty():
            yield _sse("error", {"message": "知识库为空，请先运行 python ingest.py 建库。"})
        return StreamingResponse(empty(), media_type="text/event-stream")

    model = req.model or config.CHAT_MODEL

    # 会话：确保存在，落库用户消息，取历史上下文（在调用模型之前完成）
    cid = req.conversation_id
    history: list[dict] = []
    if cid:
        if not store.owns(cid, user["id"]):
            # 前端传了未知/非本人的 id：新建一个归属本人的会话，避免消息丢失
            conv = store.create_conversation(
                user["id"], title=_title_from(req.question), model=model)
            cid = conv["id"]
        else:
            # 首条消息时用问题生成标题
            existing = store.recent_messages(cid, config.HISTORY_TURNS)
            if not existing:
                store.rename_conversation(cid, user["id"], _title_from(req.question))
        history = store.recent_messages(cid, config.HISTORY_TURNS)
        store.add_message(cid, "user", req.question)

    hits = retrieve(STATE["embedder"], coll, req.question)
    sources = sorted({m["source"] for _, m in hits})
    prompt = build_prompt(req.question, hits)

    # 组装发给大模型的消息：system + 历史（不含本次问题）+ 本次带资料的问题
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": prompt})

    def gen():
        if cid:
            yield _sse("conversation", {"conversation_id": cid})
        yield _sse("sources", {"sources": sources})
        answer_parts: list[str] = []
        used_model = None
        for m in (model, config.FALLBACK_MODEL):
            try:
                client = OpenAI(base_url=config.BASE_URL, api_key=config.key_for(m))
                stream = client.chat.completions.create(
                    model=m,
                    messages=messages,
                    temperature=0.3,
                    stream=True,
                )
                yield _sse("model", {"model": m})
                for chunk in stream:
                    # 中转站收尾块可能 choices 为空（仅带 usage），需跳过
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        answer_parts.append(delta)
                        yield _sse("token", {"text": delta})
                used_model = m
                yield _sse("done", {"model": m})
                break
            except Exception:
                yield _sse("warn", {"message": f"模型 {m} 失败，尝试备用…"})
                continue
        else:
            yield _sse("error", {"message": "所有模型均调用失败，请检查网络或密钥。"})

        # 落库助手回答（即使失败也记录已生成部分，便于历史连续）
        if cid:
            answer = "".join(answer_parts)
            if answer:
                store.add_message(cid, "assistant", answer,
                                  sources=sources, model=used_model)
            store.touch_conversation(cid, model=used_model or model)

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    (config.BASE_DIR / "logs").mkdir(exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=8994)
