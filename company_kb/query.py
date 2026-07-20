"""问答：检索 ChromaDB -> 拼装提示词 -> 调用 yxkl 中转 Chat。

用法：
    python query.py                    # 进入交互问答（输入问题，quit 退出）
    python query.py "你的问题"          # 单次提问
"""
import sys

import chromadb
from fastembed import TextEmbedding
from openai import OpenAI

import config

SYSTEM_PROMPT = (
    "你是企业内部知识库助手。请只根据【参考资料】回答员工的问题，"
    "用简洁清晰的中文作答。如果参考资料中没有相关信息，直接说"
    "“资料中未找到相关内容”，不要编造。"
)


def _clients():
    """懒加载 embedder 和向量库集合。"""
    embedder = TextEmbedding(model_name=config.EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(config.DB_DIR))
    coll = client.get_collection(config.COLLECTION)
    return embedder, coll


def retrieve(embedder, coll, question: str):
    qvec = list(embedder.embed([question]))[0].tolist()
    res = coll.query(query_embeddings=[qvec], n_results=config.TOP_K)
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    return list(zip(docs, metas))


def build_prompt(question: str, hits) -> str:
    blocks = []
    for i, (doc, meta) in enumerate(hits, 1):
        blocks.append(f"[资料{i} · 来源:{meta['source']}]\n{doc}")
    context = "\n\n".join(blocks)
    return f"【参考资料】\n{context}\n\n【问题】\n{question}"


def ask_llm(prompt: str, model: str = None) -> str:
    """调中转 Chat，失败自动切备用模型。"""
    model = model or config.CHAT_MODEL
    for m in (model, config.FALLBACK_MODEL):
        try:
            client = OpenAI(base_url=config.BASE_URL, api_key=config.key_for(m))
            resp = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content, m
        except Exception as e:
            print(f"  ! 模型 {m} 调用失败: {e}")
    return "（所有模型均调用失败，请检查网络或密钥）", None


def answer(question: str, embedder, coll):
    hits = retrieve(embedder, coll, question)
    if not hits:
        print("向量库为空，请先运行 python ingest.py 建库。")
        return
    prompt = build_prompt(question, hits)
    reply, used = ask_llm(prompt)
    print("\n" + "=" * 50)
    print(reply)
    print("-" * 50)
    srcs = sorted({m["source"] for _, m in hits})
    print(f"来源: {', '.join(srcs)}  | 模型: {used}")
    print("=" * 50 + "\n")


def main():
    embedder, coll = _clients()
    if len(sys.argv) > 1:
        answer(" ".join(sys.argv[1:]), embedder, coll)
        return
    print("企业知识库问答（输入 quit / 退出）")
    while True:
        try:
            q = input("\n问> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "退出", ""):
            break
        answer(q, embedder, coll)


if __name__ == "__main__":
    main()
