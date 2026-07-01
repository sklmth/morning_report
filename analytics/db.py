"""
经营分析 SQLite 数据库层
数据库文件: runtime/analytics.db (与8990的 morning_report.db 独立)
"""

import sqlite3
import json
import os
from datetime import datetime, date
from typing import Optional, Any

# 默认数据库路径，可通过环境变量覆盖
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime", "analytics.db"
)

SCHEMA_SQL = """
-- 数据快照记录（每次处理的元数据）
CREATE TABLE IF NOT EXISTS data_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    data_date     TEXT NOT NULL,           -- 数据日期 e.g. '2026-06-28'
    month         TEXT NOT NULL,           -- '2026-06'
    year          INTEGER NOT NULL,
    source_type   TEXT NOT NULL,           -- 'wanmei' | 'yingfu'
    source_file   TEXT NOT NULL,           -- 原始文件名
    processed_at  TEXT NOT NULL,           -- ISO时间戳
    trigger_by    TEXT NOT NULL DEFAULT 'manual',  -- 'auto'|'upload'|'watch'
    morning_report_id INTEGER,             -- 关联8990的reports.id (可空)
    UNIQUE(data_date, source_type, source_file)
);

-- 揽装人月累数据（完整积分结构，来自完美一单 揽装人维度（月累））
CREATE TABLE IF NOT EXISTS person_monthly_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    name                  TEXT NOT NULL,
    district              TEXT,            -- 区县
    team                  TEXT,            -- 部门/团队
    -- 高套（总体揽装口径）
    new_gaotao            REAL DEFAULT 0,  -- 新增高套
    stock_gaotao          REAL DEFAULT 0,  -- 存量升高套
    -- 高套（政企责任田认领口径）
    new_gaotao_zq         REAL DEFAULT 0,
    stock_gaotao_zq       REAL DEFAULT 0,
    -- 双线高套（总体）
    new_gaotao_twin       REAL DEFAULT 0,
    stock_gaotao_twin     REAL DEFAULT 0,
    -- 增量积分
    inc_pts_total         REAL DEFAULT 0,  -- 全业务增量积分
    inc_pts_base          REAL DEFAULT 0,  -- 基本面
    inc_pts_mobile        REAL DEFAULT 0,  -- 其中：移动
    inc_pts_bb            REAL DEFAULT 0,  -- 其中：宽带
    inc_pts_phone         REAL DEFAULT 0,  -- 其中：固话
    inc_pts_twin          REAL DEFAULT 0,  -- 双线
    inc_pts_inet          REAL DEFAULT 0,  -- 其中：互联网专线
    inc_pts_net           REAL DEFAULT 0,  -- 其中：组网专
    inc_pts_other         REAL DEFAULT 0,  -- 其他业务
    -- 新增积分
    new_pts_total         REAL DEFAULT 0,  -- 全业务新增积分
    new_pts_base          REAL DEFAULT 0,
    new_pts_twin          REAL DEFAULT 0,
    -- 存量积分
    stock_pts_total       REAL DEFAULT 0,
    stock_pts_base        REAL DEFAULT 0,
    stock_pts_twin        REAL DEFAULT 0,
    -- 全光组网
    gateway_count         REAL DEFAULT 0,  -- 主从网关数
    UNIQUE(month, name, snapshot_id)
);

-- 揽装人日数据（用于日均进度计算，来自 揽装人维度（日））
CREATE TABLE IF NOT EXISTS person_daily_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    name                  TEXT NOT NULL,
    district              TEXT,
    team                  TEXT,
    new_gaotao            REAL DEFAULT 0,
    stock_gaotao          REAL DEFAULT 0,
    inc_pts_total         REAL DEFAULT 0,
    inc_pts_base          REAL DEFAULT 0,
    inc_pts_twin          REAL DEFAULT 0,
    new_pts_total         REAL DEFAULT 0,
    UNIQUE(data_date, name, snapshot_id)
);

-- 区县责任田月累积分（来自完美一单 区县责任田积分(月）和 认领局向纬度（月累））
CREATE TABLE IF NOT EXISTS district_monthly_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    district              TEXT NOT NULL,   -- 县分名称
    -- 净增积分（= 增量 - 到期 - 拆机 - 降值）
    net_pts               REAL DEFAULT 0,
    -- 增量积分及各分项
    inc_pts               REAL DEFAULT 0,
    base_pts              REAL DEFAULT 0,  -- 基本面
    base_mobile           REAL DEFAULT 0,  -- 移动
    base_bb               REAL DEFAULT 0,  -- 宽带
    base_phone            REAL DEFAULT 0,  -- 固话
    base_itv              REAL DEFAULT 0,  -- ITV
    base_smart            REAL DEFAULT 0,  -- 智家
    -- 流失相关（负值）
    base_expire           REAL DEFAULT 0,  -- 基本面到期积分
    base_decline          REAL DEFAULT 0,  -- 存量降值积分
    base_churn            REAL DEFAULT 0,  -- 基本面拆机积分
    -- 双线
    twin_pts              REAL DEFAULT 0,
    twin_inet             REAL DEFAULT 0,  -- 互联网专线
    twin_net              REAL DEFAULT 0,  -- 组网专
    twin_decline          REAL DEFAULT 0,  -- 双线降值
    twin_churn            REAL DEFAULT 0,  -- 双线拆机
    -- 其他业务
    other_pts             REAL DEFAULT 0,
    other_cloud           REAL DEFAULT 0,  -- 云
    other_iot             REAL DEFAULT 0,  -- 物联网
    pts_completion_rate   REAL DEFAULT 0,  -- 增量积分落格率（揽装局向维度G8）
    UNIQUE(month, district, snapshot_id)
);

-- 区县责任田日积分
CREATE TABLE IF NOT EXISTS district_daily_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    district              TEXT NOT NULL,
    net_pts               REAL DEFAULT 0,
    inc_pts               REAL DEFAULT 0,
    base_pts              REAL DEFAULT 0,
    twin_pts              REAL DEFAULT 0,
    other_pts             REAL DEFAULT 0,
    UNIQUE(data_date, district, snapshot_id)
);

-- 营服人员效能（来自营服 中心人员效能 sheet）
CREATE TABLE IF NOT EXISTS staff_efficiency (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    name                  TEXT NOT NULL,
    center                TEXT,            -- 营服中心
    role                  TEXT,            -- 人员角色
    -- 效能指标
    predicted_incentive   REAL DEFAULT 0,  -- 预计激励（元）
    total_gaotao          REAL DEFAULT 0,  -- 综合高套（含存量）
    new_gaotao            REAL DEFAULT 0,  -- 高套（新装）
    stock_gaotao          REAL DEFAULT 0,  -- 存量高套
    device_pts            REAL DEFAULT 0,  -- 揽装积分
    incentive_pts         REAL DEFAULT 0,  -- 激励积分
    gaotao_pts            REAL DEFAULT 0,  -- 高套积分
    stock_gaotao_pts      REAL DEFAULT 0,  -- 存量高套积分
    fttr                  INTEGER DEFAULT 0,
    contract              INTEGER DEFAULT 0,
    mobile                INTEGER DEFAULT 0,
    UNIQUE(data_date, name, snapshot_id)
);

-- 人员激励档位构成（来自营服 中心人员预计酬金 sheet）
CREATE TABLE IF NOT EXISTS staff_incentive_tier (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    name                  TEXT NOT NULL,
    center                TEXT,
    cp_group              TEXT,            -- CP组编号
    device_pts            REAL DEFAULT 0,  -- 揽装积分
    tier_129_pts          REAL DEFAULT 0,  -- 高套129-168 积分
    tier_169_pts          REAL DEFAULT 0,  -- 高套169-198 积分
    tier_199_pts          REAL DEFAULT 0,  -- 高套199+ 积分
    bastion_托收_low      REAL DEFAULT 0,  -- 托收堡垒60以下
    bastion_托收_high     REAL DEFAULT 0,  -- 托收堡垒60以上
    bastion_非托收_low    REAL DEFAULT 0,  -- 非托收堡垒60以下
    bastion_非托收_high   REAL DEFAULT 0,  -- 非托收堡垒60以上
    pure_new_pts          REAL DEFAULT 0,  -- 纯新非高套积分
    stock_non_bastion_pts REAL DEFAULT 0,  -- 存量非堡垒积分
    dev_incentive         REAL DEFAULT 0,  -- 发展酬金（元）
    UNIQUE(data_date, name, snapshot_id)
);

-- CP对效能（来自营服 服务工资计算 sheet）
CREATE TABLE IF NOT EXISTS cp_pair_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    center                TEXT,
    cp_group              TEXT,
    sales_name            TEXT,            -- 营销人员
    install_name          TEXT,            -- 装维人员1
    install_name2         TEXT,            -- 装维人员2（可空）
    cp_target             REAL DEFAULT 0,  -- CP组积分目标
    sales_target          REAL DEFAULT 0,  -- 营销目标
    install_target        REAL DEFAULT 0,  -- 装维目标
    sales_pts_actual      REAL DEFAULT 0,  -- 营销实际积分
    install_pts_actual    REAL DEFAULT 0,  -- 装维实际积分
    cp_pts_total          REAL DEFAULT 0,  -- CP总积分
    sales_service_wage    REAL DEFAULT 0,  -- 营销服务工资（元）
    install_coeff         REAL DEFAULT 0,  -- 装维计件系数
    install_gap           REAL DEFAULT 0,  -- 装维积分缺口
    cp_gap                REAL DEFAULT 0,  -- CP总积分缺口
    UNIQUE(data_date, center, cp_group, snapshot_id)
);

-- 包区承包收入（来自营服 016-包区各指标汇总表）
CREATE TABLE IF NOT EXISTS area_contract_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    area_id               TEXT,            -- 包区ID
    area_name             TEXT NOT NULL,   -- 包区名称
    center                TEXT,            -- 营服中心
    area_type             TEXT,            -- 包区大类/小类
    contractor            TEXT,           -- 承包人
    income_target         REAL DEFAULT 0,  -- 承包收入目标
    income_actual         REAL DEFAULT 0,  -- 当月收入
    income_yoy            REAL DEFAULT 0,  -- 同比
    income_mom            REAL DEFAULT 0,  -- 环比
    income_cum            REAL DEFAULT 0,  -- 累计收入
    time_progress         REAL DEFAULT 0,  -- 时间进度
    cum_progress          REAL DEFAULT 0,  -- 累计完成进度
    pts_target            REAL DEFAULT 0,  -- 当月积分目标
    pts_actual            REAL DEFAULT 0,  -- 当月积分完成
    UNIQUE(data_date, area_id, snapshot_id)
);

-- 网点月发展（来自完美一单 网点月发展 sheet）
CREATE TABLE IF NOT EXISTS outlet_monthly_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id           INTEGER NOT NULL REFERENCES data_snapshots(id),
    data_date             TEXT NOT NULL,
    month                 TEXT NOT NULL,
    district              TEXT,
    outlet_name           TEXT NOT NULL,   -- 网点名称
    outlet_code           TEXT,
    all_dev_count         INTEGER DEFAULT 0,  -- 全业务发展数
    all_inc_pts           REAL DEFAULT 0,     -- 全业务增量积分
    all_net_pts           REAL DEFAULT 0,     -- 全业务净增积分
    all_churn_pts         REAL DEFAULT 0,     -- 拆机积分
    mobile_dev_count      INTEGER DEFAULT 0,
    mobile_inc_pts        REAL DEFAULT 0,
    bb_dev_count          INTEGER DEFAULT 0,
    bb_inc_pts            REAL DEFAULT 0,
    UNIQUE(data_date, outlet_name, snapshot_id)
);

-- 分析任务记录（用于追踪哪些快照已被分析）
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id   INTEGER NOT NULL REFERENCES data_snapshots(id),
    status        TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'done'|'error'
    error_msg     TEXT,
    started_at    TEXT,
    finished_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_person_monthly_month ON person_monthly_metrics(month);
CREATE INDEX IF NOT EXISTS idx_person_monthly_name  ON person_monthly_metrics(name);
CREATE INDEX IF NOT EXISTS idx_district_monthly     ON district_monthly_metrics(month, district);
CREATE INDEX IF NOT EXISTS idx_staff_eff_month      ON staff_efficiency(month);
CREATE INDEX IF NOT EXISTS idx_snapshots_month      ON data_snapshots(month, source_type);
"""


def get_db_path() -> str:
    return os.environ.get("ANALYTICS_DB_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """创建所有表（若不存在）"""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def upsert_snapshot(conn: sqlite3.Connection, data_date: str, source_type: str,
                    source_file: str, trigger_by: str = "manual",
                    morning_report_id: Optional[int] = None) -> int:
    """插入或忽略快照记录，返回 id"""
    month = data_date[:7]   # 'YYYY-MM'
    year = int(data_date[:4])
    now = datetime.utcnow().isoformat(timespec="seconds")
    cur = conn.execute("""
        INSERT INTO data_snapshots
            (data_date, month, year, source_type, source_file, processed_at, trigger_by, morning_report_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(data_date, source_type, source_file) DO UPDATE SET
            processed_at=excluded.processed_at,
            trigger_by=excluded.trigger_by,
            morning_report_id=COALESCE(excluded.morning_report_id, morning_report_id)
    """, (data_date, month, year, source_type, source_file, now, trigger_by, morning_report_id))
    conn.commit()
    # 返回刚插入或已存在的id
    row = conn.execute(
        "SELECT id FROM data_snapshots WHERE data_date=? AND source_type=? AND source_file=?",
        (data_date, source_type, source_file)
    ).fetchone()
    return row["id"]


def bulk_insert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> int:
    """批量插入，忽略冲突（ON CONFLICT IGNORE）"""
    if not rows:
        return 0
    keys = list(rows[0].keys())
    placeholders = ",".join("?" * len(keys))
    col_str = ",".join(keys)
    sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"
    data = [[r.get(k) for k in keys] for r in rows]
    conn.executemany(sql, data)
    conn.commit()
    return len(rows)


def query_json(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    """执行查询，返回 dict 列表"""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_latest_snapshot_date(conn: sqlite3.Connection, source_type: str = "wanmei") -> Optional[str]:
    """获取最新的数据日期"""
    row = conn.execute(
        "SELECT MAX(data_date) as d FROM data_snapshots WHERE source_type=?",
        (source_type,)
    ).fetchone()
    return row["d"] if row else None


def get_available_months(conn: sqlite3.Connection) -> list[str]:
    """获取已有数据的月份列表"""
    rows = conn.execute(
        "SELECT DISTINCT month FROM data_snapshots ORDER BY month DESC"
    ).fetchall()
    return [r["month"] for r in rows]


from contextlib import contextmanager

@contextmanager
def db_conn(db_path: Optional[str] = None):
    """上下文管理器，自动关闭连接"""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()
