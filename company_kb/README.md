# 企业知识库（第一期：命令行原型）

本地 Embedding + yxkl 中转 Chat 的极简 RAG 系统，资源占用 < 1GB 内存，无需 GPU。

## 架构

```
文档 → 切块 → 本地向量化(fastembed) → ChromaDB
提问 → 检索最相关块 → 拼提示词 → yxkl中转Chat(gpt-5.5) → 回答
```

- **Embedding**：本地 `BAAI/bge-small-zh-v1.5`（量化 ONNX，约 400MB 内存，不装 PyTorch）
- **Chat**：yxkl 中转，默认 `gpt-5.5`，失败自动切 `claude-sonnet-5`
- **向量库**：ChromaDB 本地文件，无独立进程

## 使用

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 把公司文档放进 documents/（支持 txt/md/docx/pdf/xlsx）

# 3. 建库（首次会自动下载 Embedding 模型）
python ingest.py

# 4a. 命令行问答
python query.py                # 交互模式
python query.py "你的问题"      # 单次提问

# 4b. 或启动 Web 服务（后端 8994）
python api.py
```

> 首次运行 `ingest.py` 会从 HuggingFace 下载 Embedding 模型（约 130MB），
> 需要能访问外网。下载一次后缓存，之后无需联网即可建库/问答。

## 中转站可用模型（实测）

- GPT 组（KB_GPT_KEY）：gpt-5.4 / gpt-5.4-mini / gpt-5.5 / gpt-5.6-*
- Claude 组（KB_CLAUDE_KEY）：claude-opus-4-8 / claude-sonnet-5 / claude-haiku-4-5 等
- **该中转站不支持 Embedding**，故 Embedding 走本地。

## 配置

改 `.env` 可切换默认模型、密钥、base_url。切块/检索参数在 `config.py`。

## Web 部署（第二期）

```
浏览器 → Nginx(3030) → 前端静态页 + /api/* 反代 → FastAPI(8994) → 检索 + 中转Chat
```

```bash
# 启动后端
python api.py                       # 监听 127.0.0.1:8994

# 前端：Nginx 托管 frontend/，反代 /api/ 到 8994（见 nginx.conf.example）
```

- 后端：[api.py](api.py) — FastAPI，端点 `/api/ask`、`/api/health`
- 前端：[frontend/index.html](frontend/index.html) — 单页聊天界面
- Nginx：[nginx.conf.example](nginx.conf.example) — 前端 3030 + 反代
