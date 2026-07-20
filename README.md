# 早会数据处理系统

本仓库包含两种运行形态，**共用同一套数据处理逻辑**（`src/function.py` + `src/report_core.py`）：

- **本机 GUI / exe 版**：人工选文件、出结果 Excel（`src/app.py`）
- **云服务器无界面版**：收邮件 → 自动处理 → 出四张图 → 微信推送（`src/server.py`）
- **经营分析系统**（端口 8991，新增）：积分结构、人员效能、进度预测、风险预警、县分横向对比、历史趋势，独立部署，不影响 8990
- **企业知识库**（前端 3030 / 后端 8994，新增）：本地 Embedding + 中转大模型的 RAG 问答，员工网页提问，独立部署

---

## 项目结构

```
morning_report/
├── src/
│   ├── app.py              # 本机 GUI 主程序
│   ├── function.py         # 数据处理逻辑（两版共用）
│   ├── report_core.py      # 输入归类 + 写模板生成结果 Excel
│   ├── excel_to_image.py   # 服务器版：LibreOffice 导出四张 PNG（首选）
│   ├── image_render.py     # 服务器版：PIL 自绘（LibreOffice 不可用时回退）
│   ├── text_report.py      # 服务器版：动态生成文字通报
│   ├── mail_client.py      # 服务器版：QQ 邮箱 IMAP 收件
│   ├── wechat_sender.py    # 服务器版：OpenClaw 微信发送
│   ├── storage.py          # SQLite 存储（runtime/morning_report.db）
│   ├── zhengqi_web.py      # 政企家庭专项走访统计：Web 层封装（存表/生成/下载）
│   └── server.py / web_server.py
├── zhengqi_visit/           # ── 政企家庭专项走访统计模块 ──────────
│   ├── processor.py        # 核心：读表→筛选→统计→出 DataFrame
│   ├── styling.py          # 写成带样式 Excel（对齐早会五张表风格）
│   ├── cli.py              # 命令行入口
│   └── __init__.py         # 对外暴露 process_excel / compute_stats
├── analytics/              # ── 经营分析后端 ──────────────────────
│   ├── config.py           # 人员名单、预警阈值
│   ├── db.py               # SQLite schema（7张表）+ CRUD
│   ├── pipeline.py         # 文件识别 → 提取 → 入库调度
│   ├── watcher.py          # 监听 8990 DB，自动触发分析（每30秒）
│   ├── excel_export.py     # 导出分析结果 Excel（6个Sheet）
│   ├── extractor/
│   │   ├── wanmei.py       # 完美一单：5个Sheet全量提取
│   │   └── yingfu.py       # 营服报表：效能/CP对/包区/激励档位
│   ├── analyzer/
│   │   ├── metrics.py      # 积分结构/人员效能/风险/横向对比/总览
│   │   └── forecast.py     # 进度预测（日均/月末/人员状态）
│   ├── api/
│   │   └── server.py       # FastAPI（11个端点，内部端口 8992）
│   └── frontend/           # ── 经营分析前端（nginx 托管于 8991）──
│       ├── index.html      # 8个Tab单页应用
│       ├── css/style.css
│       └── js/
│           ├── api.js      # API封装
│           ├── charts.js   # ECharts 14种图表
│           └── app.js      # Tab切换、数据加载、上传弹窗
├── company_kb/              # ── 企业知识库 RAG ────────────────────
│   ├── config.py            # 密钥/模型/切块检索参数
│   ├── ingest.py            # 文档→切块→本地向量化→ChromaDB
│   ├── query.py             # 命令行问答：检索+中转Chat
│   ├── api.py               # FastAPI 后端（端口 8994）
│   ├── frontend/index.html  # 聊天前端（部署 3030）
│   ├── documents/           # 公司原始文档（不入库）
│   └── nginx.conf.example   # Nginx 反代示例
├── scripts/
│   ├── deploy.sh          # 全项目统一增量部署（推荐）
│   ├── deploy_latest.sh   # 旧脚本：仅拉代码重启 8990
│   └── weixin_direct_send.js
├── assets/
│   └── 早会五张表.xlsx      # ⚠️ 模板文件（带公式），必须放在这里
├── requirements.txt            # 8990 服务依赖
├── analytics_requirements.txt  # 经营分析额外依赖（fastapi/uvicorn）
├── run_analytics.py            # 经营分析启动入口
└── .env.example
```

---

## 一、本机 GUI / exe 版

### 打包成 exe

双击运行 `build_windows.bat`，完成后 exe 位于 `dist/早会数据处理系统.exe`，可直接分发，无需安装 Python。

### 功能

- 选择输入文件（营服报表 / 完美一单 / 红黄牌高套 / 商机管控表）
- 指定输出路径，处理结果写入模板对应 Sheet，**保留模板公式**
- 遇到未配置的套餐名称会立即终止并提示

---

## 二、云服务器日报服务（端口 8990）

### 流程

```
轮询 QQ 邮箱未读邮件
  → 下载 Excel 附件（按文件名/内容自动归类）
  → 写入模板生成结果 Excel
  → LibreOffice 导出四张通报图（回退 PIL 自绘）
  → 动态生成文字通报
  → OpenClaw 发四张图 + 文字通报到微信
```

### 安装依赖

```bash
pip install -r requirements.txt

# LibreOffice（强烈推荐，精确出图）
apt-get install -y libreoffice-calc python3-uno poppler-utils fonts-noto-cjk
```

### 配置

复制 `.env.example` 为 `.env` 并填写邮箱账号、微信发送目标等参数。若服务器已有 OpenClaw 的 `QQ_MAIL_*` 配置，无需重复填写。

### 启动

```bash
# 推荐：Web 服务 + 后台轮询一体
python src/web_server.py

# 其他选项
python src/web_server.py --no-poll   # 仅 Web，不轮询邮件
python src/web_server.py --once      # 启动时立刻收一次
python src/server.py --local A.xlsx B.xlsx  # 跳过邮箱，直接处理本地文件
```

浏览器访问 `http://服务器IP:8990/` 查看处理记录和通报图片。

### 政企家庭专项走访统计（复用 8990，无需新端口）

统计政企标准化信息收集表中「企业员工-进企业做家庭专项」的走访数据，按客户经理出表，风格对齐早会五张表。

**统计口径**（集中在 `zhengqi_visit/processor.py` 顶部常量，改口径只改这里）：

- 筛选 G 列「拜访对象类型」==「企业员工-进企业做家庭专项」
- 再按 K 列「预约上门日期」落在**当前自然周（周一~周日）**内 —— 周区间动态，下周自动切下周
- 按 E 列「填写人员姓名」分组，套固定名单 `ROSTER`（无数据补 0；实习期 `EXCLUDED` 不统计）
- 每人指标：今周目标 5（固定）/ 预约数（记录条数）/ 走访数（T 列「已拜访」条数）/ 预约完成率（预约数÷5，<5 户柔和标红）/ 差值（5−预约数），按差值降序排列

**三个 HTTP 接口**（脚本推送 → 服务器处理 → 前端下载）：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/zhengqi/upload` | 推送原始 Excel（raw body 或 multipart 字段 `file`/`files`）|
| POST | `/zhengqi/upload-rows` | 推送 JSON 行（AirScript / 金山文档脚本用，见下）|
| GET  | `/zhengqi/latest` | 下载最新统计结果（按当天口径实时生成）|

原始 Excel 推送示例（raw body 最简单，也支持 multipart 字段名 `file`/`files`）：

```
POST http://服务器IP:8990/zhengqi/upload
Content-Type: application/octet-stream
body = xlsx 文件字节
→ 返回 {"ok":true,"received":...,"generated":...,"rows":N}
```

**AirScript / 金山文档（AirSheet）专用：JSON 行推送**

AirScript 无法把工作簿导出成 xlsx 字节，且禁止请求 IP / 带端口的 URL。统计只依赖 4 列，因此脚本直接读单元格拼成 JSON 行 POST 过来最稳。脚本见 [`scripts/airscript_zhengqi_upload.js`](scripts/airscript_zhengqi_upload.js)。

```
POST https://域名/zhengqi/upload-rows        # 必须 HTTPS、不带端口、不用 IP
Content-Type: application/json
body = {"rows":[{"name":"李东","type":"企业员工-进企业做家庭专项",
                 "appt_date":"2026-07-15","result":"已拜访"}, ...],
        "file_name":"可选"}
→ 返回 {"ok":true,"received":...,"generated":...,"rows":N}
```

> 每行 4 个逻辑键 `name/type/appt_date/result`（也兼容直接用中文表头名）。`upload` 与 `upload-rows` 共用同一套统计核心，口径完全一致；两种来源取较新的一份生成结果。
> ⚠️ AirScript 的 HTTPS/去端口限制需服务器侧给 8990 配 nginx 反代 + 域名 + TLS（参考下文 8991 的 nginx 段，改 `listen 443 ssl` + `proxy_pass http://127.0.0.1:8990`）。

首页顶部「政企家庭专项走访统计」卡片显示最后接收时间 + 下载按钮。原始表存 `runtime/zhengqi/`（git 不跟踪）。

命令行单独跑（不经服务）：

```bash
python -m zhengqi_visit.cli 输入.xlsx [输出.xlsx]
```

### 用 systemd 管理

参考 `scripts/morning-report.service`：

```bash
cp scripts/morning-report.service /etc/systemd/system/
# 按实际路径修改 WorkingDirectory 和 ExecStart
systemctl daemon-reload
systemctl enable --now morning-report.service
```

---

## 三、经营分析系统（端口 8991）

基于完美一单报表 + 营服业务通报表，对端州分公司政企部进行多维经营分析。

### 分析能力

| 页面 | 内容 |
|---|---|
| 🏠 总览 | KPI卡片 + 积分来源构成饼图 + 高套人员分布 |
| 📈 积分结构 | 基本面/双线/其他构成 + 健康度仪表盘（拆机/降值/到期占比）+ 全市县分对比 |
| 🎯 完成进度 | 时间进度对比 + 人员积分进度条（绿/黄/红三色）+ 月末线性预测 |
| 👥 人员效能 | 揽装积分×高套散点图 + 激励档位分布（129/169/199+）+ CP对完成率 |
| 🏆 县分对比 | 全市净增积分排名 + 基本面/双线/其他多维对比柱图 |
| ⚠️ 风险预警 | 自动触发拆机/降值/净增为负预警 + 历史趋势 |
| 📉 历史趋势 | 月度积分/高套趋势折线（随数据积累逐月丰富）|
| 🗄 数据快照 | 已入库的文件记录，支持手动上传历史月份数据 |

### 数据更新机制

- **自动**：8990 每处理一次报表，后台 `watcher` 在 30 秒内自动解析入库，8991 随即更新
- **手动**：点击右上角「⬆ 上传数据」，上传任意月份的完美一单 / 营服报表，自动识别类型并解析

---

## 四、企业知识库（前端 3030 / 后端 8994）

面向公司员工的内部知识库问答（RAG）。把公司制度、手册等文档入库后，员工在网页提问，系统检索相关内容并调用大模型作答，回答附带来源。详见 [company_kb/README.md](company_kb/README.md)。

### 架构

```
文档 → 切块 → 本地向量化(fastembed) → ChromaDB
浏览器(员工) → Nginx(3030) → 前端页 + /api/* 反代 → FastAPI(8994) → 检索 + 中转Chat(gpt-5.5)
```

- **Embedding**：本地 `bge-small-zh-v1.5`（量化 ONNX，约 400MB 内存，无需 GPU/PyTorch）
- **Chat**：yxkl 中转，默认 `gpt-5.5`，失败自动切 `claude-sonnet-5`
- **资源占用**：总内存 < 1GB，普通服务器即可

### 目录

```
company_kb/
├── config.py                    # 密钥/模型/切块检索参数（从 .env 读取）
├── ingest.py                    # 建库：文档→切块→本地向量化→ChromaDB
├── query.py                     # 命令行问答
├── api.py                       # FastAPI 后端（端口 8994，SSE 流式）
├── frontend/index.html          # 单页聊天界面（部署 3030）
├── documents/                   # 公司原始文档（不入库，自行放入）
├── .env.example                 # 配置模板（含中转密钥），复制为 .env
├── requirements.txt             # 依赖
├── deploy.sh                    # 一键部署/更新脚本
├── company-kb.service.example   # systemd 服务模板
└── nginx.conf.example           # Nginx 反代模板
```

### 本地使用

```bash
cd company_kb
pip install -r requirements.txt
cp .env.example .env          # 已内置中转密钥，可直接用
# 文档放进 documents/（txt/md/docx/pdf/xlsx），然后建库
python ingest.py
# 启动后端
python api.py                 # 监听 8994
```
本地开发直接双击 `frontend/index.html`（file:// 会自动直连 8994）即可聊天。

> 首次 `ingest.py` 会从 HuggingFace 下载 Embedding 模型（约 130MB），需能访问外网，下载后缓存。

服务器部署见下方「部署指南 → 四、企业知识库」。

---

## 部署指南

### 前置条件

服务器已安装：Python 3.10+、nginx、git

### 拉取代码

```bash
git clone git@github.com:sklmth/morning_report.git
cd morning_report
```

### 安装依赖

```bash
# 8990 日报服务依赖（已装可跳过）
pip install -r requirements.txt

# 经营分析额外依赖
pip install -r analytics_requirements.txt
```

### 配置 8990 服务

```bash
cp .env.example .env
# 编辑 .env，填写邮箱账号、微信发送目标等
```

---

### 配置 nginx（新增 8991 端口）

> **已有 nginx 且部署了其他页面**：只需新增一个 `server {}` 块，完全不影响其他服务。

**第一步：编辑 nginx 配置文件**

> 仓库内原先的 `nginx/analytics.conf` 已移除，请自行新建。把下面这段存为 `/etc/nginx/conf.d/analytics.conf`，并把 **两处** `root` 占位路径改为服务器实际绝对路径（如 `/home/ubuntu/morning_report/analytics/frontend`）。若 nginx 不 include `conf.d/*.conf`，直接追加到 `nginx.conf` 的 `http {}` 块末尾：
>
> ```nginx
> server {
>     listen 8991;
>     server_name _;
>     charset utf-8;
>
>     location / {
>         root /home/ubuntu/morning_report/analytics/frontend;  # ← 改为实际路径
>         try_files $uri $uri/ /index.html;
>         add_header Cache-Control "no-cache";
>     }
>
>     location ~* \.(js|css|png|ico)$ {
>         root /home/ubuntu/morning_report/analytics/frontend;  # ← 改为实际路径
>         expires 1h;
>     }
>
>     location /api/ {
>         proxy_pass         http://127.0.0.1:8992/api/;
>         proxy_http_version 1.1;
>         proxy_set_header   Host $host;
>         proxy_set_header   X-Real-IP $remote_addr;
>         proxy_read_timeout 120s;
>         client_max_body_size 50m;
>     }
>
>     location /health {
>         proxy_pass http://127.0.0.1:8992/health;
>     }
> }
> ```

**第二步：测试配置语法并热重载**

```bash
nginx -t           # 语法检查，有 error 不要继续
nginx -s reload    # 热重载，不中断现有连接和其他页面
```

**验证 nginx 是否生效：**

```bash
curl http://127.0.0.1:8991/health   # 此时 8992 还没启动，会 502，属正常
```

---

### 启动经营分析服务

```bash
# 临时后台运行（测试用）
nohup python run_analytics.py > runtime/analytics.log 2>&1 &
```

**用 systemd 管理（推荐，开机自启）：**

仓库已附模板 `scripts/morning-report-analytics.service`，复制改路径即可：

```bash
cp scripts/morning-report-analytics.service /etc/systemd/system/
# 编辑 WorkingDirectory / ExecStart / 日志路径为实际路径
```

模板内容（供参考）——新建 `/etc/systemd/system/morning-report-analytics.service`：

```ini
[Unit]
Description=Morning Report Analytics Service (port 8992)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/ubuntu/morning_report
ExecStart=/usr/bin/python3 run_analytics.py
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/ubuntu/morning_report/runtime/analytics.log
StandardError=append:/home/ubuntu/morning_report/runtime/analytics.log
Environment=ANALYTICS_HOST=127.0.0.1
Environment=ANALYTICS_PORT=8992

[Install]
WantedBy=multi-user.target
```

> ⚠️ `WorkingDirectory` 和日志路径改为服务器实际路径。

```bash
systemctl daemon-reload
systemctl enable --now morning-report-analytics.service

# 查看状态
systemctl status morning-report-analytics.service

# 实时日志
journalctl -u morning-report-analytics.service -f
```

**验证完整链路：**

```bash
# API 健康检查
curl http://127.0.0.1:8992/health
# → {"status":"ok"}

# 通过 nginx 访问前端
curl -I http://127.0.0.1:8991/
# → HTTP/1.1 200 OK
```

浏览器打开 `http://服务器IP:8991` 即可看到经营分析界面。

---

## 四、企业知识库部署（前端 3030 / 后端 8994）

> 与 8990、8991 完全独立，互不影响。后端只监听本地 8994，对外由 Nginx 的 3030 反代。

**第一步：配置与建库**

```bash
cd morning_report/company_kb
pip install -r requirements.txt          # 首次装依赖（含 fastapi/fastembed 等）
cp .env.example .env                     # 已内置中转密钥，如需改模型再编辑

# 把公司文档放进 documents/（txt/md/docx/pdf/xlsx），然后建库
python ingest.py                         # 首次会下载 Embedding 模型（约130MB，需外网）
```

**第二步：配置 systemd 守护后端**

参考 `company_kb/company-kb.service.example`，复制并改路径：

```bash
cp company_kb/company-kb.service.example /etc/systemd/system/company-kb.service
# 编辑 WorkingDirectory / ExecStart / 日志路径为服务器实际路径
systemctl daemon-reload
systemctl enable --now company-kb.service
systemctl status company-kb.service

# 验证后端（模型加载需约10秒）
curl http://127.0.0.1:8994/api/health
# → {"ok":true,"indexed":true,"chunks":N,"model":"gpt-5.5"}
```

**第三步：配置 Nginx（3030 端口）**

参考 `company_kb/nginx.conf.example`，存为 `/etc/nginx/conf.d/company_kb.conf`，把 `root` 改为 `frontend/` 绝对路径：

```nginx
server {
    listen 3030;
    server_name _;
    root /root/morning_report/company_kb/frontend;   # ← 改为实际路径
    index index.html;

    location / { try_files $uri $uri/ /index.html; }

    location /api/ {
        proxy_pass http://127.0.0.1:8994;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;              # SSE 流式必需
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
nginx -t && nginx -s reload
```

浏览器打开 `http://服务器IP:3030` 即可使用知识库问答。

> ⚠️ 云服务器安全组 / 防火墙需放行 **3030** 端口。

**更新（增量部署，很快）**

`deploy.sh` 会对比本次 git 变动，只做必要的事，不全量重来：

```bash
cd company_kb
bash deploy.sh                # 增量：自动判断
```

| 本次改了什么 | deploy.sh 的动作 |
|---|---|
| 只改前端 `frontend/` | 不重启，Nginx 直接生效（最快） |
| 改后端 `.py` | 只重启 8994 |
| 改 `requirements.txt` | 装依赖 + 重启 |
| 改了文档（需 `REBUILD=1`） | 重建向量库 + 重启 |
| 无相关变动 | 跳过，秒退 |

```bash
REBUILD=1 bash deploy.sh      # documents/ 文档有增删时，重建向量库
FORCE=1   bash deploy.sh      # 强制重启后端（排障用）
```

> 向量库不存在时会自动建库一次。文档是 gitignore 的、不随代码走，故文档更新靠 `REBUILD=1` 手动触发。

---

### 更新代码（统一增量部署）

一个脚本搞定所有模块，拉一次代码后**按各模块的实际变动**分别决定动作，不全量重来：

```bash
bash scripts/deploy.sh
```

它会自动判断：

| 本次改了什么 | 动作 |
|---|---|
| `src/**` 或 `requirements.txt` | 重启日报服务(8990)，依赖变才装 |
| `analytics/**` `run_analytics.py` 或 `analytics_requirements.txt` | 重启经营分析(8992)，依赖变才装 |
| `company_kb/**` 后端 `.py` | 重启知识库(8994) |
| 任意前端（`analytics/frontend/` `company_kb/frontend/`） | 不重启，Nginx 直接生效 |
| 纯文档 / 无相关变动 | 跳过，秒退 |

**只部署某个模块 / 特殊开关：**

```bash
bash scripts/deploy.sh main         # 只部署日报服务
bash scripts/deploy.sh analytics    # 只部署经营分析
bash scripts/deploy.sh kb           # 只部署知识库
KB_REBUILD=1 bash scripts/deploy.sh # 知识库文档有增删，重建向量库
FORCE=1 bash scripts/deploy.sh      # 强制重启所有服务（排障用）
```

> 服务名/路径可用环境变量覆盖（`SVC_MAIN` `SVC_ANALYTICS` `SVC_KB` `PYTHON_BIN` 等）。
> 旧脚本 `scripts/deploy_latest.sh` 仍保留（仅管 8990），推荐改用 `scripts/deploy.sh`。

---

### 历史数据导入

如需导入历史月份（如5月数据），在网页界面操作即可：

1. 打开 `http://服务器IP:8991`
2. 点击右上角「⬆ 上传数据」
3. 上传5月份的完美一单报表 + 营服业务通报表（两个文件一起上传）
4. 系统自动识别月份、解析入库，历史趋势图立即生效

---

## 命令行工具

```bash
# 直接处理本地文件（不收邮件）
python src/server.py --local A.xlsx B.xlsx

# OpenClaw 桥接
python src/openclaw_bridge.py latest               # 返回最新处理记录
python src/openclaw_bridge.py date 2026-06-25      # 返回指定日期记录
python src/openclaw_bridge.py ingest A.xlsx B.xlsx # 识别并处理入库
```

---

## 配置维护

| 配置项 | 文件 |
|---|---|
| 全光网关套餐配置 | `src/function.py` → `GATEWAY_CONFIG` |
| 政企客户经理名单 | `src/function.py` → `names`（同步更新 `analytics/config.py` → `NAMES`）|
| 高装人员名单 | `src/function.py` → `gaozhuang_names`（同步更新 `analytics/config.py` → `GAOZHUANG_NAMES`）|
| 积分预警阈值 | `analytics/config.py` → `RISK_THRESHOLDS` |
| 经营分析服务端口 | 环境变量 `ANALYTICS_PORT`（默认 8992）|
| watcher 检查间隔 | 环境变量 `WATCHER_INTERVAL`（默认 30 秒）|
| 知识库中转密钥/模型 | `company_kb/.env`（默认模型 gpt-5.5，备用 claude-sonnet-5）|
| 知识库切块/检索参数 | `company_kb/config.py`（CHUNK_SIZE / TOP_K 等）|

> **人员名单说明**：`src/function.py` 控制日报生成，`analytics/config.py` 控制经营分析，两处需同步修改。

---

## 端口总览

| 端口 | 服务 | 说明 |
|---|---|---|
| 8990 | 日报服务 | 收邮件→处理→微信推送（systemd: morning-report） |
| 8991 | 经营分析前端 | Nginx 托管，反代到 8992 |
| 8992 | 经营分析后端 | FastAPI（内部，systemd: morning-report-analytics） |
| 3030 | 企业知识库前端 | Nginx 托管，反代到 8994 |
| 8994 | 企业知识库后端 | FastAPI（内部，systemd: company-kb） |

> 各服务相互独立，可单独部署、重启，互不影响。对外需放行 8990/8991/3030。
