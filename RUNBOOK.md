# 操作手册 · 常用命令速查

> 本文件记录项目中各模块的实际运行命令，避免每次重新推导。
> 工作目录：`C:\Users\小辰\Desktop\代码实现\早会五张表\morning_report_project (新UI)\morning_report`

---

## zhengqi_visit_stats · 政企走访统计处理

**功能**：读取政企标准化信息收集 xlsx，生成家庭专项走访统计表。

```bash
python -m zhengqi_visit_stats.cli \
  "assets/(政企标准化信息收集V2)表格视图.xlsx" \
  "zhengqi_visit_stats/output/家庭专项走访统计.xlsx"
```

- 输入：`assets/` 目录下的政企信息收集原始表（支持 V1/V2 命名）
- 输出：`zhengqi_visit_stats/output/家庭专项走访统计.xlsx`
- 依赖：`openpyxl`, `pandas`（已安装）
- 模块名经命名规范化后为 `zhengqi_visit_stats`（旧名 `zhengqi_visit` 已废弃）

**统计口径**（见 processor.py）：
- 仅统计 `拜访对象类型 == 企业员工-进企业做家庭专项`
- **今周动态过滤**：只统计 `预约上门日期` 落在“运行当天所在自然周（周一~周日）”内的记录
- 每位客户经理今周目标固定 5 户；`拜访结果 == 已拜访` 计入走访数

⚠️ **常见坑**：若输出全为 0，多半是输入表数据不属于本周（如导出的是上一周的旧快照）。
先确认 `预约上门日期` 是否覆盖本周，需要时重新导出最新表格视图。

---

## daily_report · 早会日报

> TODO：补充运行命令

## analytics · 经营分析

> TODO：补充运行命令

## company_kb · 企业知识库 RAG

> TODO：补充运行命令
