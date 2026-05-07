import pandas as pd
import numpy as np
from datetime import datetime

names = [
    "钟俊杰", "麦海芬", "黄淡妮", "邱海燕", "李东", 
    "王锦添", "黄观霞", "冯艺康", "谢卓和", "伍颖敏", 
    "潘观友", "李玉强", "张小敏", "具进康"
]

GATEWAY_CONFIG = {
    "智企云包2.0 2年合约 _60元/月": {"主网关数": 1, "从网关数": 1},
    "智企云包2.0FTTR促销优惠2年合约（混搭型）_80元": {"主网关数": 1, "从网关数": 2},
    "智企云包2.0FTTR促销优惠2年合约（混搭型）_100元": {"主网关数": 1, "从网关数": 2},
    "智企云包2.0FTTR促销优惠2年合约（混搭型）_180元": {"主网关数": 1, "从网关数": 3},
    "智企云包2.0FTTR促销优惠2年合约（混搭型）_250元": {"主网关数": 1, "从网关数": 3},
    "政商全光组网_FTTR调测分期套餐（主网关）_60元_24期": {"主网关数": 1, "从网关数": 0},
    "小翼全光网主网关月服务套餐（主网关_工业头端_2口主网关）（220元）": {"主网关数": 1, "从网关数": 0},
    "小翼全光网从网关24期月服务套餐（从网关_吸顶型）（40元）": {"主网关数": 0, "从网关数": 1}
}

class GatewayConfigError(Exception):
    pass

def points_to_gaotao(points):
    if points < 59: return 0
    if points < 129: return 0.5
    if points < 199: return 1.0
    if points < 299: return 1.5
    if points < 399: return 2.0
    if points < 499: return 2.5
    val = points / 200
    return round(min(val, 25.0), 2)


def generate_shangji_table(data):
    sheets_to_load = [s for s in data.keys() if "政企商机管控表" in s]
    all_dfs = []

    for s in sheets_to_load:
        df_tmp = data[s].copy()

        row0 = df_tmp.iloc[0].tolist()
        row1 = df_tmp.iloc[1].tolist()

        # M-R 列（索引 12-17）用第二行列名覆盖
        for i in range(12, 18):
            if i < len(row1) and pd.notna(row1[i]) and str(row1[i]).strip():
                row0[i] = row1[i]

        # ✅ 修复：对重复/空列名去重，避免 InvalidIndexError
        seen = {}
        unique_cols = []
        for col in row0:
            col_str = str(col) if pd.notna(col) else "__unnamed"
            if col_str in seen:
                seen[col_str] += 1
                unique_cols.append(f"{col_str}_{seen[col_str]}")
            else:
                seen[col_str] = 0
                unique_cols.append(col_str)

        df_tmp.columns = unique_cols
        df_tmp = df_tmp.iloc[2:].reset_index(drop=True)
        all_dfs.append(df_tmp)

    if not all_dfs:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.concat(all_dfs, ignore_index=True)

    # 列名映射
    df = df.rename(columns={
        "客户经理": "name",
        "商机类型": "type",
        "目前进度": "status",
        "商机金额": "amount",
        "双线新增积分（月租型）": "pts_n",
        "基本面增量积分（月租型）": "pts_o",
        "高套数": "gaotao_val",
        "预计转化时间": "date"
    })

    # 基础过滤
    df["name"] = (
    df["name"]
    .astype(str)
    .str.strip()
    .str.replace(" ", "")   # 去掉所有空格
    )
    df = df[df["name"].isin(names)]  # 只保留名单内人员
    df = df[df["type"].astype(str).str.strip() != "产数项目"]
    df = df[~df["status"].astype(str).str.strip().isin(["失败", "已受理"])]

    # 计算积分
    df["pts_n"] = pd.to_numeric(df["pts_n"], errors="coerce")
    df["pts_o"] = pd.to_numeric(df["pts_o"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    df["final_points"] = df.apply(
        lambda r: np.nansum([r["pts_n"], r["pts_o"]])
        if np.nansum([r["pts_n"], r["pts_o"]]) > 0
        else r["amount"],
        axis=1
    )

    # 计算高套
    df["gaotao_val"] = pd.to_numeric(df["gaotao_val"], errors="coerce")
    df["final_gaotao"] = df.apply(
        lambda r: r["gaotao_val"] if pd.notnull(r["gaotao_val"])
        else points_to_gaotao(r["final_points"]),
        axis=1
    )

    # 时间判断
    current_month = datetime.now().strftime("%Y-%m")
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df["is_current"] = df["date_dt"].dt.strftime("%Y-%m") == current_month

    # 聚合函数
    def aggregate_data(target_df):
        grp = target_df.groupby("name").agg(
            户数=("name", "count"),
            高套累计=("final_gaotao", "sum"),
            积分累计=("final_points", "sum")
        ).reset_index()

        res = pd.DataFrame({"姓名": names})
        res = res.merge(grp, left_on="姓名", right_on="name", how="left").drop(columns=["name"])
        res = res.fillna(0)
    
        # ✅ 按高套累计降序排序（核心）
        res = res.sort_values(by="高套累计", ascending=False).reset_index(drop=True)

        return res

    df_all = aggregate_data(df)
    df_month = aggregate_data(df[df["is_current"] == True])

    return df_month, df_all


def generate_gaotao_table(data):
    """
    从完美一单揽装人维度（月累）中提取政企高套数据。
    前5行为表头，E列(idx=4)为姓名，H列(idx=7)为新增高套，I列(idx=8)为存量升高套。
    高套数 = 新增高套 + 存量升高套
    """
    df = data["揽装人维度（月累)"].copy()
    temp = df.iloc[5:, [4, 7, 8]].copy()
    temp.columns = ["姓名", "新增高套", "存量升高套"]
    temp["姓名"] = temp["姓名"].astype(str).str.strip()
    temp = temp[temp["姓名"].isin(names)].copy()
    temp["新增高套"] = pd.to_numeric(temp["新增高套"], errors="coerce").fillna(0)
    temp["存量升高套"] = pd.to_numeric(temp["存量升高套"], errors="coerce").fillna(0)
    temp["高套数"] = temp["新增高套"] + temp["存量升高套"]
    summary = temp.groupby("姓名")["高套数"].sum().reset_index()
    result = pd.DataFrame({"姓名": names})
    result = result.merge(summary, on="姓名", how="left")
    result["高套数"] = result["高套数"].fillna(0)
    return result[["姓名", "高套数"]]

def generate_honghuangpai_gaotao_table(data):
    """
    从完美一单揽装人维度（月累）中提取红黄牌高套数据。
    前5行为表头，E列(idx=4)为姓名，F列(idx=5)为新装高套，G列(idx=6)为存量升高套。
    高套数 = 新装高套 + 存量升高套
    """
    df = data["揽装人维度（月累)"].copy()
    temp = df.iloc[5:, [4, 5, 6]].copy()
    temp.columns = ["姓名", "新装高套", "存量升高套"]
    temp["姓名"] = temp["姓名"].astype(str).str.strip()
    temp = temp[temp["姓名"].isin(names)].copy()
    temp["新装高套"] = pd.to_numeric(temp["新装高套"], errors="coerce").fillna(0)
    temp["存量升高套"] = pd.to_numeric(temp["存量升高套"], errors="coerce").fillna(0)
    temp["高套数"] = temp["新装高套"] + temp["存量升高套"]
    summary = temp.groupby("姓名")["高套数"].sum().reset_index()
    result = pd.DataFrame({"姓名": names})
    result = result.merge(summary, on="姓名", how="left")
    result["高套数"] = result["高套数"].fillna(0)
    return result[["姓名", "高套数"]]


def get_gateway_count(package_name, key):
    if package_name not in GATEWAY_CONFIG:
        raise GatewayConfigError(f"❌ 未识别套餐：{package_name}")
    return GATEWAY_CONFIG[package_name][key]

def generate_quanguang_table(data):
    """
    从完美一单数据中生成全光组网表。
    - 揽装人维度（月累）sheet：从第6行起，E列=姓名，AP列=主从网关数
    - 认领局向纬度（月累）sheet：筛出D列='端州分公司'的行，取AW列作为主从网关数，追加为最后一行
    列索引说明（0-based）：
      E列 = 4，AP列 = 41，D列 = 3，AW列 = 48
    """
    # ── 揽装人维度（月累）──
    df_lz = data["揽装人维度（月累)"].copy()
    # 从第6行起（iloc[5:]），取 E列(4) 和 AP列(41)
    temp = df_lz.iloc[5:, [4, 41]].copy()
    temp.columns = ["姓名", "主从网关数"]
    temp["姓名"] = temp["姓名"].astype(str).str.strip()
    temp = temp[temp["姓名"].isin(names)].copy()
    temp["主从网关数"] = pd.to_numeric(temp["主从网关数"], errors="coerce").fillna(0)
    summary = temp.groupby("姓名")["主从网关数"].sum().reset_index()

    result = pd.DataFrame({"姓名": names})
    result = result.merge(summary, on="姓名", how="left")
    result["主从网关数"] = result["主从网关数"].fillna(0)

    # ── 认领局向纬度（月累）—— 端州分公司 ──
    df_jx = data["认领局向纬度（月累）"].copy()
    # D列=3，AW列=48
    temp_jx = df_jx.iloc[:, [3, 48]].copy()
    temp_jx.columns = ["机构", "主从网关数"]
    temp_jx["机构"] = temp_jx["机构"].astype(str).str.strip()
    dz_rows = temp_jx[temp_jx["机构"] == "端州分公司"]
    dz_val = pd.to_numeric(dz_rows["主从网关数"], errors="coerce").fillna(0).sum()

    dz_row = pd.DataFrame({"姓名": ["端州"], "主从网关数": [dz_val]})
    result = pd.concat([result, dz_row], ignore_index=True)

    return result[["姓名", "主从网关数"]]

def generate_wanmei_table(data):
    df = data["揽装人维度（月累)"].copy()
    temp = df.iloc[5:, [4, 5, 6, 13, 22]].copy()
    temp.columns = ["姓名", "新增高套", "存量升高套", "积分完成", "新增积分（全业务）"]
    temp["姓名"] = temp["姓名"].astype(str).str.strip()
    temp = temp[temp["姓名"].isin(names)].copy()
    for col in temp.columns[1:]:
        temp[col] = pd.to_numeric(temp[col], errors="coerce").fillna(0)
    temp["高套"] = temp["新增高套"] + temp["存量升高套"]
    summary = temp.groupby("姓名")[["高套", "积分完成", "新增积分（全业务）"]].sum().reset_index()
    return pd.DataFrame({"姓名": names}).merge(summary, on="姓名", how="left").fillna(0)

gaozhuang_names = [
    "陈梓铭", "程庆德", "刘奇峻", "龙家宝",
    "罗紫杰", "莫健铭", "吴广仁", "王洪明"
]

def generate_gaozhuang_gaotao_table(data):
    """
    从完美一单揽装人维度（月累）中提取高装高套数据。
    前5行为表头，E列(idx=4)为姓名，F列(idx=5)为新装高套，G列(idx=6)为存量升高套。
    高套数 = 新装高套 + 存量升高套
    """
    df = data["揽装人维度（月累)"].copy()
    temp = df.iloc[5:, [4, 5, 6]].copy()
    temp.columns = ["姓名", "新装高套", "存量升高套"]
    temp["姓名"] = temp["姓名"].astype(str).str.strip()
    temp = temp[temp["姓名"].isin(gaozhuang_names)].copy()
    temp["新装高套"] = pd.to_numeric(temp["新装高套"], errors="coerce").fillna(0)
    temp["存量升高套"] = pd.to_numeric(temp["存量升高套"], errors="coerce").fillna(0)
    temp["高套数"] = temp["新装高套"] + temp["存量升高套"]
    summary = temp.groupby("姓名")["高套数"].sum().reset_index()
    result = pd.DataFrame({"姓名": gaozhuang_names})
    result = result.merge(summary, on="姓名", how="left")
    result["高套数"] = result["高套数"].fillna(0)
    return result[["姓名", "高套数"]]
