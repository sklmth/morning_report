# 企业微信通知系统 - 使用说明

## 功能概述

企业微信通知系统已完成重大功能改造，新增以下功能：

### 1. 人员配置更新
- ✅ 高端装维：8人（程庆德、刘奇峻、龙家宝、罗紫杰、莫健铭、吴广仁、王洪明、陈梓铭）
- ✅ 智云工程师：7人（零樑、何而恒、魏垚晖、吴文懿、莫尧桂、郭剑鸿、梁钧鹏）
- ✅ 管理者：3人（钟俊杰正经理、张端副经理、梁天霖副经理）

### 2. 定时通知规则
- ✅ 客户经理提醒：18:00, 18:45, 19:15, 19:45, 20:15, 21:00, 22:00, 23:00（填了2户及以上不提醒）
- ✅ 第一个通报（简洁版）：
  - 张端副经理：18:30, 19:00, 20:00, 20:30, 21:00, 21:30
  - 钟俊杰经理：19:30, 20:30, 21:00, 21:30
  - 全部填了就不发送
- ✅ 第二个通报（详细版）：22:00发给所有管理者
- ✅ 最终数据收集：23:30（判断超时，不发送消息）

### 3. 累计统计功能
- ✅ 准时填报统计（19:30前完成至少2条）
- ✅ 超时填报统计（19:30-23:30之间完成）
- ✅ 漏填统计（23:30还没填的）
- ✅ Excel导出（参考早会五张表风格）

### 4. 提醒消息格式
- ✅ @客户经理
- ✅ 显示超时次数、漏填次数、今日提醒次数
- ✅ 使用emoji和温馨提醒

---

## 快速开始

### 1. 安装依赖

```bash
cd morning_report
pip install APScheduler>=3.10.0
```

### 2. 配置环境变量

在 `.env` 文件中配置企业微信webhook：

```bash
WECOM_NOTICE_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY
```

### 3. 启动服务

```bash
python wecom_notice/main.py
```

服务将运行在 `http://127.0.0.1:8996`

---

## API 使用指南

### 基础API

#### 1. 健康检查
```bash
GET /health
GET /api/health
```

#### 2. 获取人员配置
```bash
# 客户经理和管理者
GET /api/config/roster

# 预约交付人员（高端装维+智云工程师）
GET /api/config/delivery-staff
```

响应示例：
```json
{
  "gaozhuang": [
    {"name": "程庆德", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    ...
  ],
  "zhiyun": [
    {"name": "零樑", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    ...
  ]
}
```

### 数据上传API

#### 3. 金山文档数据上传
```bash
POST /api/airscript/upload
Content-Type: application/json

{
  "source": "ks_bitable",
  "report_version": "wecom_notice_v1",
  "file_name": "预约表",
  "sheet_id": "xxx",
  "rows": [
    {
      "fields": {
        "客户经理姓名": "麦海芬",
        "企业名称": "测试企业",
        "拜访对象姓名+职位": "张三",
        "预约上门日期": "2026-08-04",
        "预约时间段": "上午",
        "预约交付人员姓名": "程庆德"
      }
    }
  ]
}
```

### 统计查询API

#### 4. 查询累计统计
```bash
GET /api/statistics/cumulative?start_date=2026-01-01&end_date=2026-01-31
```

响应示例：
```json
{
  "on_time": [
    {
      "manager_name": "麦海芬",
      "count": 15,
      "dates": ["2026-01-10", "2026-01-11", ...],
      "details": [...]
    }
  ],
  "overtime": [...],
  "missing": [...],
  "summary": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "total_days": 20,
    "on_time_count": 45,
    "overtime_count": 10,
    "missing_count": 5,
    "on_time_rate": 0.75
  }
}
```

#### 5. 导出Excel
```bash
GET /api/statistics/export?start_date=2026-01-01&end_date=2026-01-31
```

返回Excel文件下载。

#### 6. 查询填报统计明细
```bash
GET /api/statistics/details?manager=麦海芬&fill_status=on_time
```

#### 7. 查询提醒日志
```bash
GET /api/reminders/logs?date=2026-01-15&manager=麦海芬
```

### 调度器管理API

#### 8. 查询调度器状态
```bash
GET /api/scheduler/status
```

响应示例：
```json
{
  "enabled": true,
  "jobs": [
    {
      "id": "cm_reminder_1800",
      "name": "客户经理提醒 18:00",
      "next_run_time": "2026-08-03T18:00:00"
    },
    ...
  ],
  "count": 20
}
```

#### 9. 启动调度器
```bash
POST /api/scheduler/start
```

响应：
```json
{
  "ok": true,
  "message": "调度器已启动",
  "job_count": 20
}
```

#### 10. 停止调度器
```bash
POST /api/scheduler/stop
```

#### 11. 手动触发任务
```bash
POST /api/scheduler/trigger/cm_reminder_1800
```

手动触发指定任务（用于测试）。

### 通报预览和发送API

#### 12. 预览通报
```bash
POST /api/report/preview
Content-Type: application/json

{
  "rule_key": "customer_manager_reminder",
  "target_date": "2026-08-04"
}
```

#### 13. 发送通报
```bash
POST /api/report/send
Content-Type: application/json

{
  "rule_key": "manager_detailed_notice",
  "target_date": "2026-08-04"
}
```

---

## 定时任务配置

所有定时任务已自动配置，启动调度器后自动运行。

### 任务列表

| 任务ID | 任务名称 | 执行时间 | 说明 |
|--------|---------|---------|------|
| cm_reminder_1800 | 客户经理提醒 | 18:00 | 提醒未达标的客户经理 |
| cm_reminder_1845 | 客户经理提醒 | 18:45 | 第2次提醒 |
| cm_reminder_1915 | 客户经理提醒 | 19:15 | 第3次提醒 |
| cm_reminder_1945 | 客户经理提醒 | 19:45 | 第4次提醒 |
| cm_reminder_2015 | 客户经理提醒 | 20:15 | 第5次提醒 |
| cm_reminder_2100 | 客户经理提醒 | 21:00 | 第6次提醒 |
| cm_reminder_2200 | 客户经理提醒 | 22:00 | 第7次提醒 |
| cm_reminder_2300 | 客户经理提醒 | 23:00 | 第8次提醒 |
| brief_zhang_1830 | 简洁通报-张端 | 18:30 | 发给张端副经理 |
| brief_zhang_1900 | 简洁通报-张端 | 19:00 | 第2次 |
| brief_zhang_2000 | 简洁通报-张端 | 20:00 | 第3次 |
| brief_zhang_2030 | 简洁通报-张端 | 20:30 | 第4次 |
| brief_zhang_2100 | 简洁通报-张端 | 21:00 | 第5次 |
| brief_zhang_2130 | 简洁通报-张端 | 21:30 | 第6次 |
| brief_zhong_1930 | 简洁通报-钟俊杰 | 19:30 | 发给钟俊杰经理 |
| brief_zhong_2030 | 简洁通报-钟俊杰 | 20:30 | 第2次 |
| brief_zhong_2100 | 简洁通报-钟俊杰 | 21:00 | 第3次 |
| brief_zhong_2130 | 简洁通报-钟俊杰 | 21:30 | 第4次 |
| detailed_notice_all | 详细通报-所有管理者 | 22:00 | 发给所有管理者 |
| final_data_collection | 最终数据收集 | 23:30 | 更新统计表 |

---

## 测试功能

### 1. 运行测试脚本

```bash
python test_wecom_notice.py
```

### 2. 手动测试单个功能

```python
# 测试客户经理提醒
from wecom_notice.reporter import build_customer_manager_reminder
report = build_customer_manager_reminder("2026-08-04", "麦海芬")
print(report["message"])

# 测试Excel导出
from wecom_notice.reporter import build_cumulative_statistics
from wecom_notice.excel_export import export_cumulative_stats
stats = build_cumulative_statistics()
export_cumulative_stats(stats, "test.xlsx", "2026-01")
```

---

## 数据库结构

### 新增表

#### fill_statistics - 填报统计表
```sql
CREATE TABLE fill_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                -- 统计日期
    manager_name TEXT NOT NULL,        -- 客户经理姓名
    fill_status TEXT NOT NULL,         -- on_time/overtime/missing
    fill_time TEXT,                    -- 填报时间
    fill_count INTEGER DEFAULT 0,      -- 填报户数
    reminder_count INTEGER DEFAULT 0,  -- 提醒次数
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(date, manager_name)
);
```

#### reminder_logs - 提醒日志表
```sql
CREATE TABLE reminder_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    reminded_at TEXT NOT NULL,
    current_count INTEGER DEFAULT 0,
    reminder_sequence INTEGER DEFAULT 1,
    overtime_count INTEGER DEFAULT 0,
    missing_count INTEGER DEFAULT 0
);
```

---

## 配置企业微信通知

### 1. 获取Webhook URL

1. 在企业微信群聊中，点击右上角...
2. 选择"群机器人" -> "添加机器人"
3. 选择"Webhook机器人"，获取webhook地址

### 2. 配置手机号或UserID（可选）

为了实现@功能，需要在 `wecom_notice/config.py` 中配置：

```python
CUSTOMER_MANAGERS = [
    {"name": "麦海芬", "team": "党政军团队", 
     "mobile": "13800138000",  # 配置手机号
     "wecom_userid": "MaiHaiFen",  # 或配置企业微信UserID
     "role": "customer_manager"},
    ...
]
```

---

## 常见问题

### Q1: 如何手动触发一次提醒？
A: 使用API手动触发：
```bash
curl -X POST http://127.0.0.1:8996/api/scheduler/trigger/cm_reminder_1800
```

### Q2: 如何查看某位客户经理的历史记录？
A: 使用统计明细API：
```bash
curl "http://127.0.0.1:8996/api/statistics/details?manager=麦海芬"
```

### Q3: Excel导出的风格是什么样的？
A: 参考了早会五张表的风格：
- 微软雅黑字体
- 蓝色标题条（#4874CB）
- 浅蓝表头（#D6E0F5）
- 准时/超时/漏填分别用绿/黄/红背景色

### Q4: 调度器会自动启动吗？
A: 不会。需要调用API手动启动：
```bash
curl -X POST http://127.0.0.1:8996/api/scheduler/start
```

### Q5: 如何修改提醒时间？
A: 修改 `wecom_notice/scheduler.py` 中的时间配置，然后重启服务。

---

## 文件结构

```
wecom_notice/
├── __init__.py
├── main.py              # 服务入口
├── api.py               # API接口
├── config.py            # 配置（人员名单等）
├── db.py                # 数据库操作
├── parser.py            # 数据解析
├── reporter.py          # 通报构建器
├── sender.py            # 消息发送
├── scheduler.py         # 定时调度器
└── excel_export.py      # Excel导出
```

---

## 更新日志

### v2.0.0 (2026-08-03)
- ✅ 新增高端装维和智云工程师人员配置
- ✅ 更新管理者名单
- ✅ 实现复杂定时通知规则（8+6+4+1+1=20个定时任务）
- ✅ 新增累计统计功能（准时/超时/漏填）
- ✅ 实现Excel导出功能
- ✅ 优化提醒消息格式（@功能、历史记录、emoji）
- ✅ 新增调度器管理API
- ✅ 完善数据库结构

---

## 技术支持

如有问题，请查看：
- API文档：启动服务后访问 http://127.0.0.1:8996/docs
- 测试脚本：`test_wecom_notice.py`
- 实施计划：`.plan/wecom_notice_enhancement.md`
