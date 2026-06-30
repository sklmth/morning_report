# 早会数据处理系统

本仓库包含两种运行形态，**共用同一套数据处理逻辑**（`src/function.py` + `src/report_core.py`）：

- **本机 GUI / exe 版**：人工选文件、出结果 Excel（`src/app.py`）
- **云服务器无界面版**：收邮件 → 自动处理 → 出四张图 → 微信推送（`src/server.py`）
- **经营分析系统**（端口 8991，新增）：积分结构、人员效能、进度预测、风险预警、县分横向对比、历史趋势，独立部署，不影响 8990

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
│   └── server.py / web_server.py
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
│   └── api/
│       └── server.py       # FastAPI（11个端点，内部端口 8992）
├── analytics-frontend/     # ── 经营分析前端 ──────────────────────
│   ├── index.html          # 8个Tab单页应用
│   ├── css/style.css
│   └── js/
│       ├── api.js          # API封装
│       ├── charts.js       # ECharts 14种图表
│       └── app.js          # Tab切换、数据加载、上传弹窗
├── nginx/
│   └── analytics.conf      # nginx server块配置（8991端口）
├── scripts/
│   ├── deploy_latest.sh    # 拉最新代码并重启服务
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

推荐把配置单独存为一个文件（便于维护）：

```bash
cp nginx/analytics.conf /etc/nginx/conf.d/analytics.conf
nano /etc/nginx/conf.d/analytics.conf
```

找到 **两处** `root` 行，把占位路径改为服务器上的实际绝对路径：

```nginx
# 改前
root /path/to/morning_report/analytics-frontend;

# 改后（示例）
root /home/ubuntu/morning_report/analytics-frontend;
```

> 如果你的 nginx 不 include `conf.d/*.conf`，也可以直接把下面这段内容追加到 `nginx.conf` 的 `http {}` 块末尾：
>
> ```nginx
> server {
>     listen 8991;
>     server_name _;
>     charset utf-8;
>
>     location / {
>         root /home/ubuntu/morning_report/analytics-frontend;  # ← 改为实际路径
>         try_files $uri $uri/ /index.html;
>         add_header Cache-Control "no-cache";
>     }
>
>     location ~* \.(js|css|png|ico)$ {
>         root /home/ubuntu/morning_report/analytics-frontend;  # ← 改为实际路径
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

新建 `/etc/systemd/system/morning-report-analytics.service`：

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

### 更新代码

**常规更新**（8990 日报服务）：

```bash
scripts/deploy_latest.sh
```

**同时更新经营分析服务**，在 `deploy_latest.sh` 执行后额外运行：

```bash
pip install -r analytics_requirements.txt
systemctl restart morning-report-analytics.service
systemctl status morning-report-analytics.service
```

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

> **人员名单说明**：`src/function.py` 控制日报生成，`analytics/config.py` 控制经营分析，两处需同步修改。
