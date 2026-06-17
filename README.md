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
│   ├── image_render.py   # 服务器版：从结果 Excel 重算并渲染四张通报图（PIL）
│   ├── mail_client.py    # 服务器版：QQ 邮箱 IMAP 收件、下载附件
│   ├── wechat_sender.py  # 服务器版：调 OpenClaw 把图片发到微信
│   └── server.py         # 服务器版主程序（轮询邮件 → 处理 → 出图 → 发送）
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
  → 写入模板生成结果 Excel
  → 从结果 Excel 重算并渲染四张通报图：
       ① 完美一单积分完成通报
       ② 高装高套目标完成情况
       ③ 全光任务完成情况
       ④ 区县目标完成情况
  → 通过 OpenClaw 把四张图依次发到微信
```

> 出图说明：四张图对应模板「模板1」中的四块区域。服务器无 Excel 无法求值公式，
> 故 `image_render.py` 用 Python 复现模板口径，从结果各 sheet 直接重算后用 PIL 绘表成图。
> 图③的「主从网关数」「全光协同」与图④的日均折算口径，均与模板公式保持一致。

### 安装依赖

```bash
pip install -r requirements.txt
```

Linux 服务器需安装中文字体（任选其一），否则图片中文会变方块：

```bash
# Debian/Ubuntu
apt-get install -y fonts-wqy-microhei
# 或 Noto CJK
apt-get install -y fonts-noto-cjk
```

字体路径可在 `.env` 的 `REPORT_FONT_PATH` 显式指定。

### 配置

复制 `.env.example` 为 `.env` 并填写：

```ini
QQ_EMAIL=your_qq@example.com
QQ_EMAIL_PASSWORD=你的IMAP/SMTP授权码   # 不是登录密码
QQ_IMAP_HOST=imap.qq.com
QQ_IMAP_PORT=993
MAIL_POLL_SECONDS=300                   # 轮询间隔（秒）
REPORT_FONT_PATH=                        # 可选：指定中文字体文件
OPENCLAW_SEND_COMMAND=openclaw message send --media "{image}" --message "{caption}"
```

`OPENCLAW_SEND_COMMAND` 支持占位符 `{image}`（图片路径）、`{caption}`（图片标题），
按实际 OpenClaw 部署调整即可。

### 运行

```bash
python src/server.py              # 持续轮询（推荐配合 systemd / supervisor 常驻）
python src/server.py --once       # 只跑一轮后退出（适合定时任务 cron）
python src/server.py --local A.xlsx B.xlsx   # 跳过邮箱，直接处理本地文件（调试用）
```

中间产物（下载的附件、结果 Excel、生成的图）保存在 `runtime/` 目录（已被 .gitignore 忽略）。
若微信发送失败，图片仍保留在 `runtime/images/`，可手动补发或排查发送命令。

---

## 更新套餐配置

编辑 `src/function.py` 中的 `GATEWAY_CONFIG` 字典即可（GUI 版需重新打包）。

