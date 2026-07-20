"""建库：documents/ 下的文档 -> 解析 -> 切块 -> 向量化 -> 存入 ChromaDB。

用法：
    python ingest.py            # 处理 documents/ 下所有文档
"""
import sys
from pathlib import Path

import chromadb
from fastembed import TextEmbedding

import config

# ---- 文档解析 ----------------------------------------------------------

def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_xlsx(path: Path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"[表: {ws.title}]")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


READERS = {
    ".txt": read_txt, ".md": read_txt,
    ".docx": read_docx,
    ".pdf": read_pdf,
    ".xlsx": read_xlsx,
}


def load_text(path: Path) -> str:
    reader = READERS.get(path.suffix.lower())
    if not reader:
        return ""
    try:
        return reader(path)
    except Exception as e:
        print(f"  ! 解析失败 {path.name}: {e}")
        return ""

# ---- 切块 --------------------------------------------------------------

def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """按字符切块，块间重叠。先按段落合并，避免切断句子。"""
    text = text.strip()
    if not text:
        return []
    chunks, buf = [], ""
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) <= size:
            buf += para + "\n"
        else:
            if buf:
                chunks.append(buf.strip())
            # 段落本身超长时，硬切
            while len(para) > size:
                chunks.append(para[:size])
                para = para[size - overlap:]
            buf = para + "\n"
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


# ---- 主流程 ------------------------------------------------------------

def main():
    if not config.DOCS_DIR.exists():
        config.DOCS_DIR.mkdir(parents=True)
        print(f"已创建 {config.DOCS_DIR}，请放入文档后重试。")
        return

    files = [p for p in config.DOCS_DIR.rglob("*") if p.suffix.lower() in READERS]
    if not files:
        print(f"{config.DOCS_DIR} 下没有可处理的文档（支持 txt/md/docx/pdf/xlsx）。")
        return

    print(f"加载 Embedding 模型 {config.EMBED_MODEL} ...")
    embedder = TextEmbedding(model_name=config.EMBED_MODEL)

    client = chromadb.PersistentClient(path=str(config.DB_DIR))
    # 重建集合，保证幂等
    try:
        client.delete_collection(config.COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})

    all_chunks, all_meta, all_ids = [], [], []
    for f in files:
        text = load_text(f)
        chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        print(f"  {f.name}: {len(chunks)} 块")
        for i, ch in enumerate(chunks):
            all_chunks.append(ch)
            all_meta.append({"source": f.name, "chunk": i})
            all_ids.append(f"{f.stem}_{i}")

    if not all_chunks:
        print("没有提取到任何文本。")
        return

    print(f"向量化 {len(all_chunks)} 个文本块 ...")
    vectors = [v.tolist() for v in embedder.embed(all_chunks)]

    coll.add(documents=all_chunks, embeddings=vectors, metadatas=all_meta, ids=all_ids)
    print(f"完成！共入库 {len(all_chunks)} 块，来自 {len(files)} 个文档。")
    print(f"向量库位置: {config.DB_DIR}")


if __name__ == "__main__":
    main()
