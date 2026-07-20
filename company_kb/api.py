"""FastAPI 后端：为前端提供知识库问答接口。

端点：
    GET  /api/health          健康检查 + 库状态
    POST /api/ask             问答（流式 SSE 返回）
    GET  /api/models          可用模型列表

启动：
    python api.py             # 监听 127.0.0.1:8994
"""
import json
import threading
from pathlib import Path

import chromadb
import uvicorn
from fastembed import TextEmbedding
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import config
import ingest
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
    # 启动阶段只打开已有向量库，不加载 embedding 模型。
    # 首次加载模型可能需要访问 HuggingFace；若服务器网络不可达，
    # 也应保证健康检查、文档列表、前端页面可用。
    try:
        client = chromadb.PersistentClient(path=str(config.DB_DIR))
        STATE["coll"] = client.get_collection(config.COLLECTION)
    except Exception:
        STATE["coll"] = None  # 库未建立


def _ensure_coll():
    """返回集合；若尚未建库则创建一个空集合（首次上传时用）。"""
    if STATE["coll"] is None:
        client = ingest.get_client()
        STATE["coll"] = ingest.open_or_create_collection(client)
    return STATE["coll"]


class AskReq(BaseModel):
    question: str
    model: str | None = None


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


@app.get("/api/documents")
def documents():
    """列出已入库的文档及其块数。"""
    coll = STATE["coll"]
    if coll is None:
        return {"documents": [], "total": 0}
    docs = ingest.list_sources(coll)
    return {"documents": docs, "total": sum(d["chunks"] for d in docs)}


@app.post("/api/upload")
def upload(files: list[UploadFile] = File(...)):
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
def delete_document(req: DeleteReq):
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


@app.post("/api/ask")
def ask(req: AskReq):
    """流式问答：先返回来源，再逐段返回答案。"""
    if _load_embedder() is None:
        def no_embedder():
            yield _sse("error", {"message": f"Embedding 模型未就绪：{STATE.get('embedder_error') or 'unknown error'}"})
        return StreamingResponse(no_embedder(), media_type="text/event-stream")
    coll = STATE["coll"]
    if coll is None or coll.count() == 0:
        def empty():
            yield _sse("error", {"message": "知识库为空，请先运行 python ingest.py 建库。"})
        return StreamingResponse(empty(), media_type="text/event-stream")

    hits = retrieve(STATE["embedder"], coll, req.question)
    sources = sorted({m["source"] for _, m in hits})
    prompt = build_prompt(req.question, hits)
    model = req.model or config.CHAT_MODEL

    def gen():
        yield _sse("sources", {"sources": sources})
        for m in (model, config.FALLBACK_MODEL):
            try:
                client = OpenAI(base_url=config.BASE_URL, api_key=config.key_for(m))
                stream = client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
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
                        yield _sse("token", {"text": delta})
                yield _sse("done", {"model": m})
                return
            except Exception as e:
                yield _sse("warn", {"message": f"模型 {m} 失败，尝试备用…"})
                continue
        yield _sse("error", {"message": "所有模型均调用失败，请检查网络或密钥。"})

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    (config.BASE_DIR / "logs").mkdir(exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=8994)
