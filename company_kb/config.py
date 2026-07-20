"""企业知识库 - 全局配置。密钥从 .env 读取，避免硬编码入库。"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ---- 中转站 / Chat 模型 ----
BASE_URL = os.getenv("KB_BASE_URL", "https://ai.yxkl.cloud/v1")
GPT_KEY = os.getenv("KB_GPT_KEY", "")
CLAUDE_KEY = os.getenv("KB_CLAUDE_KEY", "")
CHAT_MODEL = os.getenv("KB_CHAT_MODEL", "gpt-5.5")
FALLBACK_MODEL = os.getenv("KB_FALLBACK_MODEL", "claude-sonnet-5")

# 模型 -> 对应密钥（gpt* 用 GPT 组，claude* 用 Claude 组）
def key_for(model: str) -> str:
    return CLAUDE_KEY if model.startswith("claude") else GPT_KEY

# ---- Embedding（本地 fastembed，量化 ONNX，省内存）----
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"

# ---- 目录 ----
DOCS_DIR = BASE_DIR / "documents"
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION = "company_kb"

# ---- 切块参数 ----
CHUNK_SIZE = 400        # 每块约 400 字
CHUNK_OVERLAP = 50      # 块间重叠，避免切断上下文

# ---- 检索参数 ----
TOP_K = 4               # 每次问答检索最相关的块数
