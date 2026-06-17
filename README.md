# 早会数据处理系统

本仓库包含两种运行形态，**共用同一套数据处理逻辑**（`src/function.py` + `src/report_core.py`）：

- **本机 GUI / exe 版**：人工选文件、出结果 Excel（`src/app.py`）
- **云服务器无界面版**：收邮件 → 自动处理 → 出四张图 → 微信推送（`src/server.py`）

## 项目结构

```
morning_report/
├── src/
│   ├── app.py            # 本机 GUI 主程序
│   ├── function.py       # 数据处理逻辑（两版共用）
│   ├── report_core.py    # 输入归类 + 写模板生成结果 Excel（两版共用）
│   ├── excel_to_image.py # 服务器版：LibreOffice 按模板1 四区域导出四张 PNG（首选）
│   ├── image_render.py   # 服务器版：PIL 自绘四张图（LibreOffice 不可用时回退）
│   ├── text_report.py    # 服务器版：按模板1 口径动态生成文字通报
│   ├── mail_client.py    # 服务器版：QQ 邮箱 IMAP 收件、下载附件
│   ├── wechat_sender.py  # 服务器版：调 OpenClaw 发图/发文字到微信
│   └── server.py         # 服务器版主程序（轮询邮件 → 处理 → 出图+通报 → 发送）
├── assets/
│   └── 早会五张表.xlsx    # ⚠️ 模板文件（带公式），必须放在这里
├── requirements.txt      # 服务器版依赖
├── .env.example          # 服务器版配置样例（复制为 .env 填写）
├── morning_report.spec   # PyInstaller 打包配置（GUI 版）
├── build_windows.bat     # 一键打包脚本（Windows）
└── README.md
```

---

## 一、本机 GUI / exe 版

### 打包成 exe

双击运行 `build_windows.bat`，完成后 exe 位于 `dist/早会数据处理系统.exe`，可直接分发给同事，无需安装 Python。

### 功能

- 选择输入文件（营服报表 / 完美一单 / 红黄牌高套 / 商机管控表）
- 指定输出路径，处理结果写入模板对应 Sheet，**保留模板公式**
- 遇到未配置的套餐名称会立即终止并提示

---

## 二、云服务器无界面版

无 GUI，部署在已配好 QQ 邮箱（IMAP/SMTP 已连通）的服务器上，全自动运行。

### 流程

```
轮询 QQ 邮箱未读邮件
  → 下载 Excel 附件（1 个或多个均可，按文件名/内容自动归类）
  → 仅当附件含『完美一单』或『营服报表』之一/全部时才触发处理
  → 写入模板生成结果 Excel
  → 从结果 Excel「模板1」sheet 导出四张通报图：
       ① 完美一单积分完成通报（A1:R21）
       ② 高装高套目标完成情况（A33:F43）
       ③ 全光任务完成情况（J33:N46）
       ④ 区县目标完成情况（P33:T44）
  → 动态生成文字通报（数值按「模板1」公式口径实时重算）
  → 通过 OpenClaw 先发四张图、再发文字通报到微信
```

> **出图方式**：四张图对应「模板1」中的四块区域。优先用 **LibreOffice**（headless）
> 加载结果 Excel、求值公式并按原样式导出 PNG —— 颜色/边框/合并/数字格式/数据条
> 与原 Excel 完全一致。若服务器无 LibreOffice，自动回退到 `image_render.py` 的
> PIL 自绘方案（样式简化，数值口径一致）。
>
> **文字通报**：`text_report.py` 按「模板1」大表（完美一单积分完成通报区域）的
> 公式口径动态重算各数值后填入固定话术模板。已与真实通报逐项核对一致
> （含邱海燕 6 月特批 +2500、团队对标全光贡献率等口径）。

### 安装依赖

```bash
pip install -r requirements.txt
```

**LibreOffice（强烈推荐，用于精确出图）**：

```bash
# Debian/Ubuntu
apt-get install -y libreoffice-calc python3-uno poppler-utils fonts-wqy-microhei
# 或 Noto CJK 字体
apt-get install -y fonts-noto-cjk
```

> **出图链路**：LibreOffice（headless+UNO）加载结果 Excel → 重算公式 →
> 把「模板1」每个区域设为打印区域 → 导出单页 PDF → 用 `pdftoppm`(poppler-utils)
> 转 PNG → 自动裁白边。比「复制到 Draw 再导出」稳定，且能正确渲染公式与样式。
>
> **重要：`_xlfn.XLOOKUP` 兼容**。模板用了 XLOOKUP，openpyxl 写出时带 `_xlfn.`
> 前缀，部分 LibreOffice 版本求值会得 `#NAME?`。程序在出图前会自动用
> `xlsx_fix.py` 把 `_xlfn.XLOOKUP` → `XLOOKUP`，使 LibreOffice 能正常求值。
>
> 务必装 `python3-uno`（确保运行 server.py 的 Python 能 `import uno`）与
> `poppler-utils`（提供 pdftoppm）。未装 LibreOffice 时回退 PIL 自绘，此时需中文字体。

### 配置

复制 `.env.example` 为 `.env` 并按注释填写。**若服务器已用 OpenClaw 的
`QQ_MAIL_*` 邮箱配置**，无需重填账号——程序会自动从 `MAIL_ENV_FILE` 指向的
`.env`（默认 `/root/.openclaw/tools/qq-mail-mcp/.env`）读取
`QQ_MAIL_USER` / `QQ_MAIL_PASS` / `QQ_MAIL_IMAP_HOST` / `QQ_MAIL_IMAP_PORT`。

发送命令 `OPENCLAW_SEND_COMMAND`（发图）与 `OPENCLAW_SEND_TEXT_COMMAND`
（发文字）按实际 OpenClaw 部署调整。

### 运行

```bash
python src/server.py              # 持续轮询（推荐配合 systemd / supervisor 常驻）
python src/server.py --once       # 只跑一轮后退出（适合定时任务 cron）
python src/server.py --local A.xlsx B.xlsx   # 跳过邮箱，直接处理本地文件（调试用）
```

中间产物（附件、结果 Excel、四张图、`通报.txt`）保存在 `runtime/`（已忽略）。
若微信发送失败，图片与通报仍保留在 `runtime/images/<时间戳>/`，可手动补发。

---

## 更新套餐配置

编辑 `src/function.py` 中的 `GATEWAY_CONFIG` 字典即可（GUI 版需重新打包）。

