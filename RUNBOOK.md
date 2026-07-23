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

## gaotao_stats · 客户经理高套清单

**功能**：读取营服报表 xlsx，提取客户经理的新增高套（③高套清单）与存量高套（④存量高套清单），生成含两 sheet 的 Excel，风格对齐「早会五张表」。

```bash
python -m gaotao_stats.cli \
  "<营服报表.xlsx>" \
  "gaotao_stats/output/客户经理高套清单.xlsx"
```

- 输入：营服报表（业务通报）；不传输出路径时默认在源文件同目录生成 `<源名>_客户经理高套清单.xlsx`
- 输出两 sheet：`新增高套` / `存量高套`，列均为 接入号 / 客户经理 / 竣工日期 / 积分 / 高套数
- 仅保留 `NAMES` 名单内客户经理（沿用 daily_report.function.names）
- 列映射（0-based，header=None 读取，首行表头跳过）：
  - ③高套清单：接入号 N=13，客户经理 AM=38，竣工日期 I=8，积分 BL=63，高套数 BR=69
  - ④存量高套清单：接入号 E=4，客户经理 BX=75，竣工时间 CU=98，积分 AK=36，高套系数 CS=96（作为高套数）
- 依赖：`openpyxl`, `pandas`

---

## daily_report · 早会日报

> TODO：补充运行命令

## analytics · 经营分析

> TODO：补充运行命令

## company_kb · 企业知识库 RAG

> TODO：补充运行命令
