# wecom_notice 数据库结构文档

## 📋 目录

- [概览](#概览)
- [表结构详解](#表结构详解)
  - [visit_records — 预约记录](#visit_records--预约记录)
  - [fill_statistics — 填报统计](#fill_statistics--填报统计)
  - [reminder_logs — 提醒日志](#reminder_logs--提醒日志)
  - [send_logs — 发送日志](#send_logs--发送日志)
  - [notification_rules — 通知规则](#notification_rules--通知规则)
  - [app_settings — 应用设置](#app_settings--应用设置)
- [表关系图](#表关系图)
- [关键机制](#关键机制)
- [常用查询](#常用查询)

---

## 概览

wecom_notice 使用 **SQLite** 单文件数据库，路径由环境变量 `DB_PATH` 配置（默认 `wecom_notice.db`）。

数据库在服务启动时由 `init_db()` 自动创建，所有表使用 `CREATE TABLE IF NOT EXISTS`，支持零停机升级（新表自动建立，旧数据不影响）。

| 表名 | 数据类型 | 写入方 | 读取方 |
|------|---------|-------|-------|
| `visit_records` | 预约记录（原始业务数据） | AirScript 上传 | 报告生成、统计查询 |
| `fill_statistics` | 每日填报结果（准时/超时/漏填）| 23:30 自动统计 | 周报/月报/通报 |
| `reminder_logs` | 每次提醒的快照记录 | 调度器 | 查询接口 |
| `send_logs` | 所有发送操作的日志 | 发送函数 | 前端日志页 |
| `notification_rules` | 通知规则配置 | `init_db()` + 前端 | 手动发送、自动调度 |
| `app_settings` | KV 应用设置 | API + 调度器 | 启动恢复、开关查询 |

---

## 表结构详解

### visit_records — 预约记录

**数据来源：** 金山文档 AirScript 脚本通过 `POST /api/airscript/upload` 写入。

**去重策略：**
- 以 `source_record_id` 为主键唯一标识（金山文档行 ID）
- 以 `payload_hash`（字段内容 MD5）检测内容变更
- 同一 `source_record_id` 内容不变 → `skipped`
- 同一 `source_record_id` 内容变更 → `updated`
- 新记录 → `inserted`

```sql
CREATE TABLE visit_records (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    source_record_id     TEXT UNIQUE,          -- 金山文档行 ID，全局唯一
    payload_hash         TEXT NOT NULL UNIQUE, -- 字段内容 MD5，用于检测变更
    uploaded_at          TEXT NOT NULL,        -- 本次上传时间（ISO 8601）
    updated_at           TEXT NOT NULL,        -- 最后更新时间

    -- 业务字段
    manager_name         TEXT,   -- 客户经理姓名
    object_type          TEXT,   -- 走访对象类型（个人/企业等）
    company_name         TEXT,   -- 企业/客户名称
    contact_name_title   TEXT,   -- 联系人姓名+职务
    contact_mobile       TEXT,   -- 联系人手机

    appointment_date     TEXT,   -- 预约走访日期 (YYYY-MM-DD)
    appointment_slot     TEXT,   -- 预约时段（上午/下午/全天）
    need_dispatch        TEXT,   -- 是否需要交付（是/否）
    delivery_staff_name  TEXT,   -- 配套交付人员姓名

    opportunity_type     TEXT,   -- 商机类型
    opportunity_type_extra TEXT, -- 商机类型补充
    opportunity_content  TEXT,   -- 商机内容描述

    cockpit_sent         TEXT,   -- 是否已推送驾驶舱
    doubao_beik_sent     TEXT,   -- 是否已推送豆包/贝壳

    visit_result         TEXT,   -- 走访结果
    actual_visit_date    TEXT,   -- 实际走访日期
    visit_situation      TEXT,   -- 走访情况描述
    images_json          TEXT,   -- 走访图片 URL 列表（JSON 数组）
    conversion_status    TEXT,   -- 转化状态

    opportunity_points   REAL NOT NULL DEFAULT 0, -- 商机积分
    gaotao_count         REAL NOT NULL DEFAULT 0, -- 高潮次数

    planned_accept_time  TEXT,   -- 计划受理时间
    reschedule_time      TEXT,   -- 改约时间
    reschedule_reason    TEXT,   -- 改约原因
    raw_json             TEXT NOT NULL  -- 原始 JSON（保留全部字段，便于排查）
);

-- 按日期+经理快速查询（最常用查询条件）
CREATE INDEX idx_visit_records_appointment ON visit_records(appointment_date, manager_name);
-- 按上传时间查询（用于统计最新数据到达时间）
CREATE INDEX idx_visit_records_uploaded_at ON visit_records(uploaded_at);
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_record_id` | TEXT UNIQUE | 金山多维表格行 ID，可为 NULL（旧数据）|
| `payload_hash` | TEXT UNIQUE | 业务字段拼接后的 MD5，内容不变则 hash 不变 |
| `appointment_date` | TEXT | `YYYY-MM-DD` 格式，与 `fill_statistics.date` 对应 |
| `images_json` | TEXT | JSON 数组字符串，如 `["https://...", "https://..."]` |
| `raw_json` | TEXT | 完整原始行数据，字段扩展时不需要加列 |


---

### fill_statistics — 填报统计

**数据来源：** 每个工作日 23:30 由 `build_final_data_collection()` 写入，周末不写。

**唯一约束：** `UNIQUE(date, manager_name)` — 每位经理每天只有一条统计记录，重复调用自动覆盖（upsert）。

```sql
CREATE TABLE fill_statistics (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,         -- 统计执行日 = date.today()（填报当天，不是预约日期）
    manager_name   TEXT NOT NULL,         -- 客户经理姓名
    fill_status    TEXT NOT NULL,         -- 填报状态（见下方枚举）
    fill_time      TEXT,                  -- 最早一条预约的 uploaded_at
    fill_count     INTEGER DEFAULT 0,     -- 当日预约条数
    reminder_count INTEGER DEFAULT 0,     -- 当日被提醒次数
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,

    UNIQUE(date, manager_name)            -- 每人每天唯一，支持 upsert
);

CREATE INDEX idx_fill_stats_date   ON fill_statistics(date);
CREATE INDEX idx_fill_stats_status ON fill_statistics(fill_status);
```

**`fill_status` 枚举值：**

| 值 | 含义 | 判定条件 |
|----|------|---------|
| `pending` | 待统计 | 提醒时临时创建，23:30 前未正式统计 |
| `on_time` | 准时 | 条数 ≥ required(2) **且** 最晚一条 `uploaded_at` ≤ 当日 19:30 |
| `overtime` | 超时 | 条数 ≥ required(2) 但最晚一条 `uploaded_at` > 19:30 |
| `missing` | 漏填 | 窗口内条数 < required(2)（含 0 条）|

> 判定取**最晚**一条记录的 `uploaded_at`（`max`），因为要求填满 2 户，最后一户填完才算完成。
> 时间戳解析失败时兜底为 `overtime`。实习期人员（`exclude_reminder=True`）直接跳过，不入统计。

**下午茶基金计算依据：**
```
本月漏填次数  → 每次扣 10 元
本月超时次数  → 累计每满 5 次扣 10 元
```

**统计起始基线（2026年8月特殊处理）：**
```python
# 2026-08-04 为系统启用日，整天按准时处理
# 8月统计从 08-05 起算，进入下月后恢复按自然月第一天
statistics_start = "2026-08-05" if month_start == "2026-08-01" else month_start
```

---

### reminder_logs — 提醒日志

**数据来源：** 每次调度器向客户经理发送提醒时，由 `add_reminder_log()` 写入一条快照。

**用途：** 记录每次提醒时经理的当前预约数量和历史违规累计，便于复盘和调试。

```sql
CREATE TABLE reminder_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,         -- 提醒针对的目标日期 (YYYY-MM-DD)
    manager_name      TEXT NOT NULL,         -- 被提醒的客户经理
    reminded_at       TEXT NOT NULL,         -- 提醒发出时间（ISO 8601）
    current_count     INTEGER DEFAULT 0,     -- 提醒时该经理的当前预约条数
    reminder_sequence INTEGER DEFAULT 1,     -- 本日第几次提醒（1, 2, 3...）
    overtime_count    INTEGER DEFAULT 0,     -- 本月累计超时次数（快照）
    missing_count     INTEGER DEFAULT 0      -- 本月累计漏填次数（快照）
);

CREATE INDEX idx_reminder_logs_date ON reminder_logs(date, manager_name);
```

**典型数据示例：**

```
id | date       | manager_name | reminded_at         | current_count | sequence | overtime | missing
 1 | 2026-08-05 | 张三         | 2026-08-04T18:15:32 |      0        |    1     |    2     |   1
 2 | 2026-08-05 | 张三         | 2026-08-04T18:45:11 |      1        |    2     |    2     |   1
 3 | 2026-08-05 | 张三         | 2026-08-04T19:15:03 |      1        |    3     |    2     |   1
```

> `current_count=1` 表示到 18:45 时张三已填写了 1 条预约，但未达到目标数量，继续提醒。

---

### send_logs — 发送日志

**数据来源：** 每次发送操作（成功或失败）都由 `add_send_log()` 写入。

**用途：** 运维排查、前端日志页展示、发送统计。

```sql
CREATE TABLE send_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key         TEXT NOT NULL,    -- 任务标识（见下方常见值）
    sent_at          TEXT NOT NULL,    -- 发送时间（ISO 8601）
    status           TEXT NOT NULL,    -- 'success' | 'failed'
    message_text     TEXT NOT NULL,    -- 发送的消息正文
    mentioned_json   TEXT NOT NULL DEFAULT '[]',  -- @的人员列表（JSON）
    record_ids_json  TEXT NOT NULL DEFAULT '[]',  -- 关联预约记录 ID（JSON）
    webhook_response TEXT NOT NULL DEFAULT '',    -- 企业微信返回的响应
    error            TEXT NOT NULL DEFAULT ''     -- 失败原因（成功时为空）
);

CREATE INDEX idx_send_logs_sent_at ON send_logs(sent_at);
```

**`rule_key` 常见值：**

| rule_key | 触发场景 |
|----------|---------|
| `customer_manager_reminder` | 客户经理提醒 |
| `brief_notice_张端` | 简洁通报-张端 |
| `brief_notice_张端_钟俊杰` | 简洁通报-多人 |
| `detailed_notice_all` | 详细通报-所有管理者 |
| `weekly_report` | 周通报 |
| `biweekly_report` | 半月报 |
| `monthly_report` | 月报 |
| `kingsoft_data_sync` | 金山文档数据同步 |
| `final_data_collection` | 最终统计表更新 |
| `custom_text` | 手动发送文本 |
| `custom_markdown` | 手动发送 Markdown |
| `custom_image` | 手动发送图片 |
| `custom_news` | 手动发送图文 |
| `custom_template_card_text_notice` | 手动发送模板卡片-文本通知 |
| `custom_template_card_news_notice` | 手动发送模板卡片-图文展示 |
| `rules_introduction` | 发送规则介绍 |

**`mentioned_json` 格式：**
```json
[
  {"name": "张三", "wecom_userid": "zhangsan", "mobile": "13800000000"},
  {"name": "李四", "wecom_userid": "lisi"}
]
```


---

### notification_rules — 通知规则

**数据来源：** 服务启动时由 `init_db()` 从 `config.py` 的 `DEFAULT_RULES` 写入，前端可通过 `PUT /api/config/rules/{rule_key}` 更新部分字段。

**更新策略：**
- 首次启动：`INSERT OR IGNORE`（不覆盖已有配置）
- 每次启动：强制同步 `recipient_policy_json`（收件人范围由代码控制，不保留手动改动）
- 前端可修改：`enabled`、`name`、`cron_expr`、`filter`、`template_key`

```sql
CREATE TABLE notification_rules (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key             TEXT NOT NULL UNIQUE,  -- 规则唯一标识（见下方示例）
    name                 TEXT NOT NULL,          -- 规则显示名称
    enabled              INTEGER NOT NULL DEFAULT 0,  -- 0=禁用 1=启用
    trigger_type         TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'scheduled'
    cron_expr            TEXT NOT NULL DEFAULT '',        -- cron 表达式（scheduled 时使用）
    filter_json          TEXT NOT NULL DEFAULT '{}',      -- 过滤条件（JSON）
    recipient_policy_json TEXT NOT NULL DEFAULT '{}',     -- 收件人策略（JSON）
    template_key         TEXT NOT NULL,          -- 消息模板标识
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
```

**`filter_json` 示例：**
```json
{
  "appointment_date": "tomorrow",
  "booking_status": "missing"
}
```

**`recipient_policy_json` 示例：**
```json
{
  "groups": ["customer_managers"],
  "include_managers": true
}
```

**注意：** `recipient_policy_json` 在每次服务启动时会被 `config.py` 的值覆盖，确保代码变更生效，不需要手动修改数据库。

---

### app_settings — 应用设置

**数据来源：** 由 `save_setting()` 写入，`get_setting()` 读取，键值对结构，无外键依赖。

```sql
CREATE TABLE app_settings (
    key        TEXT PRIMARY KEY,       -- 设置键名
    value      TEXT NOT NULL DEFAULT '', -- 设置值（均为字符串）
    updated_at TEXT NOT NULL
);
```

**内置键名清单：**

| key | 说明 | 可能值 |
|-----|------|-------|
| `scheduler_enabled` | 调度器开关 | `"true"` / `"false"` |
| `last_airscript_upload_at` | 金山文档最后一次上传时间 | ISO 8601 时间戳 |
| `fine_enabled` | 是否在提醒中显示本月应扣金额 | `"true"` / `"false"` |
| `fine_rules_enabled` | 是否在提醒中附上基金规则警示 | `"true"` / `"false"` |

**`scheduler_enabled` 关键作用：**
```
服务启动 → 读取此值
  "true"  → 自动拉起调度器（重启自愈）
  "false" → 保持停止（尊重人工停止决定）

POST /api/scheduler/start → 写 "true"  + 启动调度器
POST /api/scheduler/stop  → 写 "false" + 停止调度器
```

**`last_airscript_upload_at` 关键作用：**
```
金山同步前：before = get_setting("last_airscript_upload_at")
等待数据：轮询直到值变化（说明 /api/airscript/upload 被 AirScript 回调）
数据到达：after != before → 同步成功
超时30s：after == before → 同步失败，跳过本批次
```


---

## 表关系图

```
visit_records                    fill_statistics
──────────────                   ───────────────
id                               id
source_record_id (UNIQUE)        date ──────────────┐
payload_hash (UNIQUE)            manager_name       │
uploaded_at ◄──────────────┐    fill_status        │
appointment_date ───────────┼──► fill_time          │
manager_name ───────────────┼──► fill_count         │
...                         │    reminder_count ◄───┤
raw_json                    │    UNIQUE(date,        │
                            │         manager_name)  │
                            │                        │
app_settings                │   reminder_logs        │
────────────                │   ─────────────        │
key (PK)                    │   id                   │
  scheduler_enabled         │   date ───────────────┘
  last_airscript_upload_at◄─┘   manager_name
  fine_enabled                  reminded_at
  fine_rules_enabled            current_count
value                           reminder_sequence
updated_at                      overtime_count
                                missing_count

notification_rules              send_logs
──────────────────              ─────────
id                              id
rule_key (UNIQUE)               rule_key  (非外键，仅约定字符串)
name                            sent_at
enabled                         status
trigger_type                    message_text
cron_expr                       mentioned_json
filter_json                     record_ids_json
recipient_policy_json           webhook_response
template_key                    error
```

> 注：SQLite 无强制外键约束（未开启 `PRAGMA foreign_keys`），表间关联通过业务逻辑维护。

---

## 关键机制

### 1. 去重写入（upsert_records）

```
AirScript 上传 rows[]
        │
        ▼
normalize_record(row)      ← 字段标准化、计算 payload_hash
        │
        ▼
每条记录查询：
  SELECT WHERE source_record_id=? OR payload_hash=?
        │
  ┌─────┼──────────────────────────┐
  │     │                          │
不存在  payload_hash 未变         payload_hash 已变
  │     │                          │
  ▼     ▼                          ▼
INSERT  skipped（跳过）          UPDATE 更新字段
  │                                │
inserted++                      updated++
```

**为什么用 `payload_hash` 去重？**
- 金山文档每次同步会发送全量数据（不只增量）
- `payload_hash` = 所有业务字段拼接后的 MD5
- 内容不变则 hash 不变 → 避免重复写入，减少 I/O

### 2. 填报统计判定（23:30 触发）

```python
# build_final_data_collection(target_date, required=2) 的核心逻辑
records = records_in_window(target_date)               # 按预约日期窗口取记录
counts  = Counter(r["manager_name"] for r in records)
today_str = date.today().isoformat()                   # 注意：写入用今天，不是 target_date

for manager in CUSTOMER_MANAGERS:
    if manager.get("exclude_reminder"):                # 实习期人员不计入统计
        continue

    count = counts[manager["name"]]

    if count < required:                               # 不足 2 户 → 漏填
        upsert_fill_statistics(today_str, name, "missing", "", count)
    else:
        mgr_records = [r for r in records if r["manager_name"] == name]
        last = max(mgr_records, key=lambda r: r["uploaded_at"])   # 取最晚一条
        fill_dt = datetime.fromisoformat(last["uploaded_at"])
        cutoff  = datetime.combine(fill_dt.date(), time(19, 30))

        status = "on_time" if fill_dt <= cutoff else "overtime"
        upsert_fill_statistics(today_str, name, status, last["uploaded_at"], count)
```

**两个日期不是一回事：**
- `target_date` — 预约的走访日期，用来**筛选** `visit_records`（周五时是下周一）
- `today_str` — `date.today()`，用来**写入** `fill_statistics.date`（填报发生的当天）

所以周五 23:30 那次统计，筛的是下周一的预约，但记在周五那一行。查月度违规次数时按 `fill_statistics.date` 走，对应的是「哪天没填」，不是「哪天要走访」。

**周五跨周末窗口（特殊处理）：**
```python
# 目标日是周一（周五发通报） → 窗口为周六~周一
def target_window(target_date):
    target = date.fromisoformat(target_date)
    if target.weekday() == 0 and (target - date.today()).days > 1:
        return (target - timedelta(days=2)).isoformat(), target.isoformat()
    return target_date, target_date
```
周末两天填写的预约都算入周一的考核窗口。

### 3. 提醒次数追踪

```
每次调度器发送提醒：
  1. add_reminder_log()        → 记录本次提醒快照到 reminder_logs
  2. increment_reminder_count() → fill_statistics.reminder_count + 1

查询经理今日被提醒几次：
  SELECT reminder_count FROM fill_statistics
  WHERE date=? AND manager_name=?
```

### 4. 并发安全

- SQLite 默认序列化写入，不存在写并发冲突
- `db.py` 的 `connection()` 上下文管理器：每次操作独立连接，用完即关
- APScheduler `max_instances=1` 防止同一任务并发运行
- `_SYNC_LOCK = threading.Lock()` 保护批次缓存字典的读写

---

## 常用查询

### 查看今日填报情况

```sql
SELECT manager_name, fill_status, fill_time, fill_count, reminder_count
FROM fill_statistics
WHERE date = '2026-08-05'
ORDER BY fill_status, manager_name;
```

### 查看本月漏填次数排行

```sql
SELECT manager_name,
       SUM(CASE WHEN fill_status = 'missing'  THEN 1 ELSE 0 END) AS missing_count,
       SUM(CASE WHEN fill_status = 'overtime' THEN 1 ELSE 0 END) AS overtime_count,
       SUM(CASE WHEN fill_status = 'on_time'  THEN 1 ELSE 0 END) AS on_time_count
FROM fill_statistics
WHERE date >= '2026-08-01'
GROUP BY manager_name
ORDER BY missing_count DESC, overtime_count DESC;
```

### 查看最近发送失败的日志

```sql
SELECT rule_key, sent_at, error, message_text
FROM send_logs
WHERE status = 'failed'
ORDER BY sent_at DESC
LIMIT 20;
```

### 查看金山文档最后同步时间

```sql
SELECT value AS last_sync, updated_at
FROM app_settings
WHERE key = 'last_airscript_upload_at';
```

### 查看某经理某日的所有预约记录

```sql
SELECT id, appointment_date, appointment_slot, company_name,
       opportunity_type, uploaded_at
FROM visit_records
WHERE manager_name = '张三'
  AND appointment_date = '2026-08-05'
ORDER BY uploaded_at;
```

### 查看今日提醒历史

```sql
SELECT manager_name, reminded_at, current_count,
       reminder_sequence, overtime_count, missing_count
FROM reminder_logs
WHERE date = '2026-08-05'
ORDER BY manager_name, reminded_at;
```

### 查看调度器当前开关状态

```sql
SELECT key, value, updated_at
FROM app_settings
WHERE key IN ('scheduler_enabled', 'last_airscript_upload_at', 'fine_enabled');
```

---

## 维护说明

### 数据保留策略

当前没有自动清理逻辑，数据永久保留。以下是各表的增长估算：

| 表 | 每日新增 | 1年数据量估算 |
|----|---------|------------|
| `visit_records` | ~20-50 条 | ~7,000-18,000 条 |
| `fill_statistics` | ~18 条（每位经理1条） | ~4,700 条 |
| `reminder_logs` | ~50-100 条 | ~13,000-26,000 条 |
| `send_logs` | ~30-60 条 | ~8,000-16,000 条 |

SQLite 轻松支撑百万行，预计数年内无需考虑清理或分库。

### 备份建议

```bash
# 直接复制数据库文件（服务运行中也可以，SQLite WAL 模式下安全）
cp wecom_notice.db wecom_notice.db.bak_$(date +%Y%m%d)

# 或通过 sqlite3 导出 SQL
sqlite3 wecom_notice.db .dump > backup_$(date +%Y%m%d).sql
```

### 手动修复数据

```bash
# 进入 SQLite 交互模式
sqlite3 wecom_notice.db

# 重置某经理某日的填报状态（如误判需要修正）
UPDATE fill_statistics
SET fill_status = 'on_time', updated_at = datetime('now', 'localtime')
WHERE date = '2026-08-05' AND manager_name = '张三';

# 删除测试发送日志
DELETE FROM send_logs WHERE rule_key LIKE 'custom_%' AND sent_at < '2026-08-01';
```

---

*文档生成时间：2026-08-05*
*对应代码文件：[db.py](db.py)*



