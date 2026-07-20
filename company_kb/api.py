"""FastAPI 后端：为前端提供知识库问答接口。

端点：
    GET  /api/health          健康检查 + 库状态
    POST /api/ask             问答（流式 SSE 返回）
    GET  /api/models          可用模型列表

启动：
    python api.py             # 监听 127.0.0.1:8994
"""
import json

import chromadb
import uvicorn
from fastembed import TextEmbedding
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import config
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
STATE = {"embedder": None, "coll": None}


@app.on_event("startup")
def _load():
    STATE["embedder"] = TextEmbedding(model_name=config.EMBED_MODEL)
    try:
        client = chromadb.PersistentClient(path=str(config.DB_DIR))
        STATE["coll"] = client.get_collection(config.COLLECTION)
    except Exception:
        STATE["coll"] = None  # 库未建立


class AskReq(BaseModel):
    question: str
    model: str | None = None


@app.get("/api/health")
def health():
    coll = STATE["coll"]
    count = coll.count() if coll else 0
    return {"ok": True, "indexed": coll is not None, "chunks": count,
            "model": config.CHAT_MODEL}


@app.get("/api/models")
def models():
    return {"default": config.CHAT_MODEL, "fallback": config.FALLBACK_MODEL,
            "options": ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
                        "claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"]}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/ask")
def ask(req: AskReq):
    """流式问答：先返回来源，再逐段返回答案。"""
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
