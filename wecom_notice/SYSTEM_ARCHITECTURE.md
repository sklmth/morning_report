# wecom_notice 企业微信通知系统架构文档

## 📋 目录

- [系统概述](#系统概述)
- [核心组件](#核心组件)
- [完整调度链路](#完整调度链路)
- [可用性保障机制](#可用性保障机制)
- [数据流转](#数据流转)
- [定时任务清单](#定时任务清单)
- [故障处理](#故障处理)
- [运维指南](#运维指南)

---

## 系统概述

**wecom_notice** 是一个基于 Python 的企业微信通知自动化系统，用于管理客户经理的预约填报提醒和统计通报。

### 核心功能

1. **定时提醒** - 向未达标的客户经理发送填报提醒
2. **管理通报** - 向管理者发送进度简报和详细报表
3. **数据同步** - 从金山文档自动拉取预约数据
4. **统计分析** - 生成准时率、超时率、漏填统计
5. **周期报告** - 周报、半月报、月报自动生成
6. **手动发送** - 支持前端预览、编辑、自定义发送

### 技术栈

| 组件 | 技术 | 版本要求 |
|------|------|---------|
| Web 框架 | FastAPI | 0.100+ |
| 调度器 | APScheduler | 3.10+ |
| 数据库 | SQLite | 3.35+ |
| HTTP 客户端 | urllib | 内置 |
| 前端 | Alpine.js | 3.x |

---

## 核心组件

### 1. FastAPI 后端 (`api.py`)

**职责：**
- 提供 REST API 接口
- 管理调度器生命周期（启动/停止/状态查询）
- 处理前端页面路由
- 接收金山文档数据上传
- 执行手动发送和预览

**关键端点：**

```python
# 健康检查
GET /health

# 调度器管理
GET  /api/scheduler/status
POST /api/scheduler/start
POST /api/scheduler/stop
POST /api/scheduler/trigger/{job_id}

# 数据上传
POST /api/airscript/upload

# 通知发送
POST /api/report/preview      # 预览通知内容
POST /api/report/send          # 发送通知
POST /api/report/send-custom   # 自定义消息

# 图片上传
POST /api/upload-pic

# 日志查询
GET /api/send-logs

# 统计查询
GET /api/statistics/cumulative
GET /api/statistics/export
```

### 2. APScheduler 调度器 (`scheduler.py`)

**职责：**
- 管理所有定时任务
- 协调数据同步与通知发送的时序
- 实现批次缓存机制
- 处理任务失败和重试

**调度策略：**

```python
BackgroundScheduler(job_defaults={
    "misfire_grace_time": 60,    # 60秒容错窗口
    "coalesce": True,            # 合并积压任务
    "max_instances": 1,          # 单实例运行
})
```

### 3. 数据同步模块 (`kingsoft_trigger.py`)

**职责：**
- 触发金山文档 AirScript 脚本
- 轮询等待数据回调
- 超时保护

**同步流程：**

```python
def sync_kingsoft_data():
    before = latest_airscript_upload()           # 记录当前时间戳
    trigger_kingsoft_data_sync()                 # 触发 webhook
    
    for elapsed in range(0, 30, 2):              # 最多等待30秒
        if latest_airscript_upload() != before:  # 检测数据到达
            break
    else:
        return False  # 超时失败
    
    build_final_data_collection()                # 更新统计表
    return True
```


### 4. SQLite 数据库 (`db.py`)

**数据表结构：**

| 表名 | 用途 |
|------|------|
| `visit_records` | 预约记录（从金山文档同步） |
| `notification_rules` | 通知规则配置 |
| `send_logs` | 发送日志（成功/失败） |
| `fill_statistics` | 填报统计（准时/超时/漏填） |
| `app_settings` | 应用设置（调度器开关等） |
| `reminder_logs` | 客户经理提醒日志 |

**关键索引：**
```sql
-- 按日期+经理快速查询预约
CREATE INDEX idx_visit_records_appointment ON visit_records(appointment_date, manager_name);
-- 按上传时间查询
CREATE INDEX idx_visit_records_uploaded_at ON visit_records(uploaded_at);
```

### 5. 企业微信发送模块 (`sender.py`)

**支持的消息类型：**

| 类型 | 函数 | 说明 |
|------|------|------|
| `text` | `send_text()` | 文本，支持 @人 |
| `markdown` | `send_markdown()` | Markdown 格式 |
| `image` | `send_image()` | Base64 图片 |
| `news` | `send_news()` | 图文消息 |
| `template_card` | `send_template_card()` | 模板卡片（文本通知/图文展示）|

**Webhook 调用：**
```python
def _send_webhook(payload: dict) -> dict:
    # POST 到企业微信 WEBHOOK_URL
    # 返回 {"errcode": 0, "errmsg": "ok"} 或错误信息
```

---

## 完整调度链路

### 服务启动链路

```
应用启动 (uvicorn)
    │
    ▼
lifespan() 钩子执行
    ├─ init_db()                        ← 建表、写入默认规则
    └─ get_setting("scheduler_enabled") ← 读持久化开关
           │
    ┌──────┴──────┐
  "true"       "false"
    │               │
    ▼               ▼
start_scheduler()  等待人工启动
    │
    ▼
BackgroundScheduler.start()
    │
    ▼
注册所有 CronTrigger 任务（共约20个）
    │
    ▼
调度器在后台线程持续运行
```

### 工作日通知链路（单个时间点）

```
CronTrigger 触发（如 18:15）
    │
    ▼
_run_notification_batch(timepoint="18:15", callback=_send_customer_manager_reminders)
    │
    ▼
_sync_for_timepoint("18:15")
    │
    ├─ cache_key = "2026-08-05 18:15"
    ├─ 已有缓存? ─── YES ──→ 直接返回 True（复用，不重复同步）
    │
    └─ NO ──→ sync_kingsoft_data()
                    │
                    ├─ 1. before = latest_airscript_upload()
                    ├─ 2. POST 金山 webhook (trigger_kingsoft_data_sync)
                    │         │
                    │      金山文档执行 AirScript
                    │         │
                    │      AirScript POST /api/airscript/upload
                    │         │
                    ├─ 3. 轮询 (每2s, 最多30s)
                    │         ├─ latest_upload() != before? ─YES→ break (数据已到)
                    │         └─ 超时 ─────────────────────────→ return False
                    │
                    ├─ 4. build_final_data_collection()  ← 更新填报统计
                    └─ 5. return True
    │
    ├─ 同步失败 ──→ add_send_log(failed) + 跳过本批次（不发送）
    │
    └─ 同步成功 ──→ callback()
                        │
                        ▼
            _send_customer_manager_reminders()
                    │
                    ├─ 获取 target_date（明天/下周一）
                    ├─ 逐一遍历 CUSTOMER_MANAGERS
                    │     │
                    │     ├─ build_customer_manager_reminder()
                    │     │     └─ 已达标? ──YES→ 跳过
                    │     │
                    │     ├─ send_text(message, recipients)
                    │     │     └─ POST 企业微信 webhook
                    │     │
                    │     ├─ add_send_log(success/failed)
                    │     │
                    │     └─ 经理间间隔 60s（防频控）
                    │
                    └─ 全部跳过时也记录一条日志
```


### 同一时间点多通报共享链路

```
18:30 触发两个任务（简洁通报-张端 + 客户经理提醒）

任务A：_run_notification_batch("18:30", _send_brief_notice_to_managers, ["张端"])
    └─ _sync_for_timepoint("18:30")
           └─ 缓存无 "2026-08-05 18:30" ──→ sync_kingsoft_data() ──→ 写入缓存

任务B：_run_notification_batch("18:30", _send_customer_manager_reminders)
    └─ _sync_for_timepoint("18:30")
           └─ 缓存有 "2026-08-05 18:30" ──→ 直接复用，跳过重复同步 ✅
```

### 手动发送链路

```
前端用户操作
    │
    ▼
POST /api/report/send
    │
    ├─ get_rule(rule_key)              ← 读取规则配置
    ├─ build_report(target_date, rule) ← 生成通知内容
    │
    ├─ 前端编辑过? ──YES→ 使用前端传入的 message
    │              NO──→ 使用报告生成的默认 message
    │
    ├─ 前端选了收件人? ──YES→ find_recipients(names) ← 查配置
    │                   NO──→ 使用报告默认收件人
    │
    ├─ send_text(message, recipients)
    │     └─ POST 企业微信 webhook
    │
    └─ add_send_log(success/failed)
```

### 自定义消息发送链路

```
POST /api/report/send-custom
    │
    ├─ message_type == "text"
    │     └─ send_text(text, recipients)       ← 直接支持 @
    │
    ├─ message_type == "markdown"
    │     ├─ send_markdown(content)            ← 不支持 @
    │     └─ 有收件人? ──→ send_text(mention_text, recipients) ← 额外发 @
    │
    ├─ message_type == "image"
    │     ├─ send_image(base64, md5)           ← 不支持 @
    │     └─ 有收件人? ──→ send_text(mention_text, recipients)
    │
    ├─ message_type == "news"
    │     ├─ send_news(articles)              ← 不支持 @
    │     └─ 有收件人? ──→ send_text(mention_text, recipients)
    │
    └─ message_type == "template_card"
          ├─ card_type in ["text_notice", "news_notice"]?
          │     NO──→ 400 Bad Request
          ├─ send_template_card(card_type, content)
          └─ 有收件人? ──→ send_text(mention_text, recipients)
```

### 图片上传链路

```
用户选择图片文件（前端）
    │
    ▼
FileReader.readAsDataURL(file)
    │
    ▼
data:image/png;base64,xxxxxxxx...
    │
    ├─ picPreview = dataUrl    ← 浏览器本地预览（不发给微信）
    │
    ▼
POST /api/upload-pic { data_url: "data:image/png;base64,..." }
    │
    ├─ 验证 MIME 类型（jpeg/png/gif/webp）
    ├─ base64 解码
    ├─ 检查大小 ≤ 10MB
    ├─ 保存为 frontend/uploads/{uuid}.png
    └─ 返回 { ok: true, url: "https://shanguantang.site/wecom-notice/uploads/{uuid}.png" }
    │
    ▼
picurl / image_url = res.url    ← 发给微信时使用公开 HTTP URL
```

---

## 可用性保障机制

### 1. 持久化开关 + 启动自愈

**目的：** 服务重启（部署/崩溃/断电）后无需人工操作，自动恢复调度。

```
app_settings 表
  key="scheduler_enabled" value="true"/"false"
          │
          ▼
服务启动时读取
  "true"  ──→ start_scheduler(enabled=True)  ← 自动恢复
  "false" ──→ 保持停止                       ← 尊重人工停止决定

POST /api/scheduler/start ──→ 启动 + 写 "true"
POST /api/scheduler/stop  ──→ 停止 + 写 "false"
```


### 2. 短期抖动补偿

**APScheduler 配置：**

```python
misfire_grace_time = 60     # 任务错过后60秒内仍可补发
coalesce = True             # 积压多次的任务合并为一次执行
max_instances = 1           # 同一任务不并发运行
```

**场景分析：**

| 停机时长 | 行为 | 说明 |
|---------|------|------|
| ≤ 60s | 补发所有错过的任务 | 短暂重启，任务不丢失 |
| > 60s | 丢弃错过的任务 | 避免集中补发过期通知 |

**为什么不补发过期通知？**
- 18:15 的提醒在 20:00 才补发已无意义
- 防止服务恢复后消息轰炸
- 下次触发时会基于最新数据重新判断

### 3. 数据同步超时保护

**轮询机制：**
```python
_POLL_INTERVAL = 2    # 每2秒检查一次
_TIMEOUT = 30         # 最多等待30秒

before = latest_airscript_upload()
trigger_kingsoft_data_sync()

for elapsed in range(0, _TIMEOUT, _POLL_INTERVAL):
    time.sleep(_POLL_INTERVAL)
    if latest_airscript_upload() != before:
        break  # 数据已到达 ✅
else:
    return False  # 超时 ❌
```

**失败处理：**
```python
if not _sync_for_timepoint(timepoint):
    logger.error("金山同步失败，本批次不使用旧数据发送")
    return  # 跳过本批次，不发送任何通知
```

**保障效果：**
- 金山文档故障时，**不用旧数据发送**
- 避免误报（如用昨天数据判断今天漏填）
- 记录失败日志，便于排查

### 4. 批次缓存与日期隔离

**缓存结构：**
```python
_SYNC_BATCH_RESULTS = {
    "2026-08-04 18:30": True,   # 昨天的缓存
    "2026-08-05 18:30": True,   # 今天 18:30 的同步结果
    "2026-08-05 19:00": True,   # 今天 19:00 的同步结果
}
```

**自动清理：**
```python
with _SYNC_LOCK:
    if cache_key in _SYNC_BATCH_RESULTS:
        return _SYNC_BATCH_RESULTS[cache_key]  # 命中缓存
    
    result = sync_kingsoft_data()
    _SYNC_BATCH_RESULTS[cache_key] = result
    
    # 清理过期日期的缓存
    today_prefix = f"{datetime.now().date().isoformat()} "
    for key in list(_SYNC_BATCH_RESULTS):
        if not key.startswith(today_prefix):
            del _SYNC_BATCH_RESULTS[key]
```

**保障效果：**
- 同一时间点多个通报共享一次同步（节省调用）
- 不同时间点独立同步（数据及时性）
- 跨日期自动清理（防内存泄漏）

### 5. 全流程日志记录

**日志维度：**

| 字段 | 说明 |
|------|------|
| `rule_key` | 任务标识（如 `customer_manager_reminder`）|
| `status` | `success` / `failed` |
| `message_text` | 发送的消息内容 |
| `mentioned` | @的收件人列表（JSON）|
| `record_ids` | 关联的预约记录 ID（JSON）|
| `webhook_response` | 企业微信返回的 JSON |
| `error` | 失败原因 |
| `created_at` | 时间戳 |

**查询接口：**
```python
GET /api/send-logs?limit=20&offset=0
# 返回分页日志 + 统计（总数/成功/失败）
```

### 6. 客户经理提醒间隔限流

**目的：** 避免企业微信频控限制（1分钟内发送过多消息会被限流）

**实现：**
```python
for manager_index, manager in enumerate(CUSTOMER_MANAGERS):
    # 发送提醒...
    if manager_index < total_managers - 1:
        logger.info("等待 60 秒后继续下一人")
        time.sleep(60)  # 每人间隔60秒
```

**场景分析：**
- 18个客户经理 → 最长耗时 18 × 60s = 18分钟
- 不影响下一时间点（如 18:15 发送到 18:33，18:45 仍按时触发）


### 7. 健康检查接口

```python
GET /health
GET /api/health
# 返回 {"status": "ok", "service": "wecom_notice"}
```

用于：
- 负载均衡器探活
- 监控系统（Uptime Robot / Prometheus）
- 容器编排健康检测（Docker healthcheck）

---

## 数据流转

### 完整数据流

```
金山文档（多维表格）
    │  用户填写预约记录
    ▼
AirScript 脚本（金山内置 JS 运行环境）
    │  读取表格数据，POST 到服务器
    ▼
POST /api/airscript/upload
    │  normalize_record() 字段标准化
    ▼
visit_records 表（SQLite）
    │  upsert（按 payload_hash 去重）
    ▼
build_final_data_collection()
    │  判断准时/超时/漏填
    ▼
fill_statistics 表
    │
    ├─── build_customer_manager_reminder()  → 提醒消息
    ├─── build_manager_brief_notice()       → 简洁通报
    ├─── build_manager_detailed_notice()    → 详细通报
    ├─── build_weekly_report()              → 周通报
    ├─── build_biweekly_report()            → 半月报
    └─── build_monthly_report()             → 月报
              │
              ▼
        send_text() / send_markdown() / ...
              │
              ▼
        企业微信 Webhook API
              │
              ▼
        企业微信群消息
```

### 填报统计判定逻辑

```
23:30 collect_final_data() 触发
    │
    ├─ 遍历所有客户经理
    │
    ├─ 每位经理在目标窗口内有预约记录?
    │       NO ──→ 漏填 (fill_status = "missing")
    │
    ├─ 最早一条记录的 uploaded_at ≤ 19:30?
    │       YES ──→ 准时 (fill_status = "on_time")
    │       NO  ──→ 超时 (fill_status = "late")
    │             ├─ uploaded_at ≤ 23:30?   YES ──→ 记超时
    │             └─ uploaded_at > 23:30?   YES ──→ 漏填（截止后补填）
    │
    └─ 写入 fill_statistics 表
```

---

## 定时任务清单

### 工作日任务（周一~周五）

| 时间 | 任务 ID | 任务名称 | 同步？|
|------|---------|---------|------|
| 18:15 | `cm_reminder_1815` | 客户经理提醒 18:15 | ✅ 独立同步 |
| 18:30 | `brief_张端_1830` | 简洁通报-张端 18:30 | ✅ 独立同步 |
| 18:45 | `cm_reminder_1845` | 客户经理提醒 18:45 | ✅ 独立同步 |
| 19:00 | `brief_张端_钟俊杰_1900` | 简洁通报-张端&钟俊杰 19:00 | ✅ 独立同步 |
| 19:15 | `cm_reminder_1915` | 客户经理提醒 19:15 | ✅ 独立同步 |
| 19:30 | `brief_张端_钟俊杰_1930` | 简洁通报-张端&钟俊杰 19:30 | ✅ 独立同步 |
| 20:00 | `brief_张端_2000` | 简洁通报-张端 20:00 | ✅ 独立同步 |
| 20:15 | `cm_reminder_2015` | 客户经理提醒 20:15 | ✅ 独立同步 |
| 20:50 | `cm_reminder_2050` | 客户经理提醒 20:50 | ✅ 独立同步 |
| 21:00 | `brief_张端_2100` | 简洁通报-张端 21:00 | ✅ 独立同步 |
| 21:30 | `brief_张端_钟俊杰_2130` | 简洁通报-张端&钟俊杰 21:30 | ✅ 独立同步 |
| 21:50 | `cm_reminder_2150` | 客户经理提醒 21:50 | ✅ 独立同步 |
| 22:00 | `detailed_notice_all` | 详细通报-所有管理者 22:00 | ✅ 独立同步 |
| 23:00 | `cm_reminder_2300` | 客户经理提醒 23:00 | ✅ 独立同步 |
| 23:30 | `final_data_collection` | 最终数据收集 23:30 | ✅ 独立同步 |

### 周期性任务

| 时间 | 任务 ID | 任务名称 | 备注 |
|------|---------|---------|------|
| 周三 12:15 | `weekly_report_wed` | 周通报 | 仅发通知，不同步数据 |
| 周日 12:00 | `weekly_report_sun` | 周通报 | 仅发通知，不同步数据 |
| 每月15日 12:00 | `biweekly_report` | 半月报 | 仅发通知，不同步数据 |
| 每月最后一天 12:00 | `monthly_report` | 月报（@all）| 仅发通知，不同步数据 |

### 周末任务（周六/周日）

| 时间 | 任务 ID | 任务名称 | 备注 |
|------|---------|---------|------|
| 12:00 | `weekend_sync_1200` | 周末数据同步 | 仅入库，不更新统计 |
| 18:00 | `weekend_sync_1800` | 周末数据同步 | 仅入库，不更新统计 |
| 22:00 | `weekend_sync_2200` | 周末数据同步 | 仅入库，不更新统计 |
| 23:30 | `weekend_sync_2330` | 周末数据同步 | 仅入库，不更新统计 |

> **注：** 周末填写的预约记录会存入数据库，但不计入准时/超时/漏填统计，
> 只有周一~周五 23:30 的 `collect_final_data` 才会更新统计指标。

---

## 故障处理

### 故障场景与应对

| 故障场景 | 系统行为 | 恢复方式 |
|---------|---------|---------|
| 服务重启（≤60s）| APScheduler 补发错过的任务 | 自动 |
| 服务重启（>60s）| 跳过过期任务，调度器自动恢复 | 自动 |
| 金山文档 webhook 超时 | 记录失败日志，跳过本批次通知 | 手动触发 `/api/kingsoft/trigger-sync` |
| 金山数据迟到（>30s）| 本批次跳过，下一时间点重新同步 | 等待下次触发或手动 |
| 企业微信 webhook 失败 | 记录失败日志（errcode/errmsg）| 查日志排查，手动补发 |
| 客户经理频控 | 每人间隔 60s，规避限频 | 自动 |
| 调度器崩溃 | 重启服务后自动拉起 | 自动 |
| SQLite 锁等待 | `check_same_thread=False` + 连接池 | 自动 |

### 手动补救操作

```bash
# 1. 查看调度器状态
curl https://shanguantang.site/wecom-notice/api/scheduler/status

# 2. 手动触发数据同步
curl -X POST https://shanguantang.site/wecom-notice/api/kingsoft/trigger-sync

# 3. 手动触发指定任务
curl -X POST https://shanguantang.site/wecom-notice/api/scheduler/trigger/cm_reminder_1815

# 4. 查看最近失败日志
curl "https://shanguantang.site/wecom-notice/api/send-logs?limit=50" | jq '.logs[] | select(.status=="failed")'

# 5. 重启调度器
curl -X POST https://shanguantang.site/wecom-notice/api/scheduler/stop
curl -X POST https://shanguantang.site/wecom-notice/api/scheduler/start
```

---

## 运维指南

### 日常检查清单

- [ ] 每日检查 `/api/send-logs` 是否有 `failed` 记录
- [ ] 每周确认调度器状态 `running: true`
- [ ] 定期备份 `wecom_notice.db`（含统计历史数据）
- [ ] 确认金山文档 webhook URL 有效（KINGSOFT_WEBHOOK_URL 环境变量）
- [ ] 确认企业微信 webhook 未过期（WECOM_WEBHOOK_URL 环境变量）

### 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `WECOM_WEBHOOK_URL` | 企业微信群 webhook 地址 | 必填 |
| `KINGSOFT_WEBHOOK_URL` | 金山文档触发 webhook | 必填 |
| `WECOM_NOTICE_PUBLIC_UPLOAD_BASE_URL` | 图片公开访问 URL 前缀 | `https://shanguantang.site/wecom-notice/uploads` |
| `DB_PATH` | SQLite 数据库路径 | `wecom_notice.db` |

### 部署命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（生产）
uvicorn wecom_notice.api:app --host 0.0.0.0 --port 8001

# 启动服务（开发）
uvicorn wecom_notice.api:app --reload --port 8001
```

### 关键日志关键字

```bash
# 查看调度器日志
grep "调度器" app.log

# 查看同步失败
grep "金山同步失败\|金山.*超时" app.log

# 查看发送失败
grep "发送.*失败" app.log

# 查看提醒发送记录
grep "成功发送提醒给" app.log
```

---

*文档生成时间：2026-08-05*
*代码版本：参见 git log（当前分支 master）*




