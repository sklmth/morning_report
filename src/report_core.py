"""
报表生成核心（GUI 版与服务器版共用）。

把原本写在 app.py 里的「读取输入 Excel → 调用 function.py 各处理函数 → 写入模板」逻辑
抽离成与界面无关的纯函数，供：
  - src/app.py        （本机 GUI / exe 版）
  - src/server.py     （云服务器无界面版）
共同调用，保证两端处理逻辑完全一致。
"""

import os
import sys
import shutil

import pandas as pd

# 兼容打包后从内嵌资源加载
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


sys.path.insert(0, resource_path("."))
from function import (  # noqa: E402
    generate_gaotao_table, generate_quanguang_table,
    generate_wanmei_table, generate_honghuangpai_gaotao_table,
    generate_gaozhuang_gaotao_table, generate_shangji_table,
    generate_yingfu_table, generate_yingfu_gaotao_for_gaozhuang,
    generate_jifen_table, GatewayConfigError,
)

# 模板文件名（位于 assets/ 或打包内嵌目录）
TEMPLATE_NAME = "早会五张表.xlsx"


def find_template():
    """定位模板文件，依次尝试：内嵌资源 → assets/ 目录。"""
    candidates = [
        resource_path(TEMPLATE_NAME),
        os.path.join(os.path.dirname(resource_path(".")), "assets", TEMPLATE_NAME),
        os.path.join(os.getcwd(), "assets", TEMPLATE_NAME),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"未找到模板文件 {TEMPLATE_NAME}，请确认 assets/ 目录下存在该文件。")


def classify_inputs(file_paths):
    """
    根据文件名把若干输入 Excel 归类为「营服报表」「完美一单」「商机管控」「红黄牌」。
    服务器版一次可能收到 1~多个附件，名称带日期/版本号，故按关键字模糊匹配。

    返回 dict：{ "yingfu": path, "wanmei": path, "shangji": path, "honghuangpai": path }
    匹配不到的键不出现。
    """
    result = {}
    for path in file_paths:
        name = os.path.basename(path)
        low = name.lower()
        # 完美一单：文件名含「完美一单」或「政企完美一单」
        if "完美一单" in name:
            result.setdefault("wanmei", path)
        # 营服报表：含「营服」「业务通报」
        elif ("营服" in name) or ("业务通报" in name):
            result.setdefault("yingfu", path)
        # 商机管控
        elif "商机" in name:
            result.setdefault("shangji", path)
        # 红黄牌
        elif ("红黄牌" in name) or ("红黄" in name):
            result.setdefault("honghuangpai", path)
        else:
            # 名称无法判定时，回退用内容探测
            kind = _detect_by_content(path)
            if kind:
                result.setdefault(kind, path)
    return result


def _detect_by_content(path):
    """名称无法判定时，按 sheet 名特征探测文件类型。"""
    try:
        xls = pd.ExcelFile(path)
        sheets = "".join(xls.sheet_names)
    except Exception:
        return None
    if "揽装人维度" in sheets:
        return "wanmei"
    if "071人员统计" in sheets or "人员统计" in sheets:
        return "yingfu"
    if "政企商机管控表" in sheets or "商机" in sheets:
        return "shangji"
    return None


def build_report(inputs, out_path):
    """
    根据归类后的输入文件生成结果 Excel（写入模板，保留模板公式）。

    参数：
        inputs   : classify_inputs() 的返回值（dict）
        out_path : 输出 xlsx 路径
    返回：
        sheet 名 → 是否写入 的字典（用于日志）
    """
    sheet_results = {}
    shangji_dfs = None
    written = {}

    # 1. 营服报表 → 激励；同时提取高装人员兜底数据
    yf_path = inputs.get("yingfu")
    yf_gaotao = {}
    if yf_path:
        yf_data = pd.read_excel(yf_path, sheet_name=None, header=None)
        sheet_results["激励"] = generate_yingfu_table(yf_data)
        yf_gaotao = generate_yingfu_gaotao_for_gaozhuang(yf_data)
        written["激励"] = True

    # 2. 完美一单 → 完美一单/全光组网/高套/红黄牌高套/高装高套
    wm_path = inputs.get("wanmei")
    if wm_path:
        wm_data = pd.read_excel(wm_path, sheet_name=None)
        sheet_results["完美一单"] = generate_wanmei_table(wm_data)
        sheet_results["全光组网"] = generate_quanguang_table(wm_data)
        sheet_results["高套"] = generate_gaotao_table(wm_data)
        sheet_results["红黄牌高套"] = generate_honghuangpai_gaotao_table(wm_data)
        sheet_results["高装高套"] = generate_gaozhuang_gaotao_table(wm_data)
        sheet_results["积分"] = generate_jifen_table(wm_path)
        for k in ("完美一单", "全光组网", "高套", "红黄牌高套", "高装高套", "积分"):
            written[k] = True

    # 兜底：完美一单无数据的高装人员从营服报表补充
    if yf_gaotao:
        gz_df = sheet_results.get("高装高套")
        if gz_df is not None:
            for i, row in gz_df.iterrows():
                if row["高套数"] == 0 and row["姓名"] in yf_gaotao:
                    gz_df.at[i, "高套数"] = yf_gaotao[row["姓名"]]["高套数"]
        wm_df = sheet_results.get("完美一单")
        if wm_df is not None:
            from function import gaozhuang_names
            for i, row in wm_df.iterrows():
                if row["姓名"] in gaozhuang_names and row["积分完成"] == 0 and row["姓名"] in yf_gaotao:
                    wm_df.at[i, "积分完成"] = yf_gaotao[row["姓名"]]["积分"]

    # 3. 商机管控
    sj_path = inputs.get("shangji")
    if sj_path:
        sj_data = pd.read_excel(sj_path, sheet_name=None, header=None)
        df_month, df_all = generate_shangji_table(sj_data)
        shangji_dfs = (df_month, df_all)
        written["商机统计"] = True

    if not sheet_results and not shangji_dfs:
        raise ValueError("未检测到有效的输入文件（完美一单 / 营服报表 / 商机管控）。")

    # 4. 写入模板
    template_path = find_template()
    shutil.copy2(template_path, out_path)

    # 高装高套、积分单独按单元格写（保留模板公式列）
    gaozhuang_df = sheet_results.pop("高装高套", None)
    jifen_vals   = sheet_results.pop("积分", None)

    with pd.ExcelWriter(out_path, engine="openpyxl", mode="a",
                        if_sheet_exists="replace") as writer:
        for s_name, df in sheet_results.items():
            df.to_excel(writer, sheet_name=s_name, index=False)

        if jifen_vals is not None:
            if "积分" not in writer.book.sheetnames:
                writer.book.create_sheet("积分")
            ws_jf = writer.book["积分"]
            for c_idx, val in enumerate(jifen_vals):
                if val is not None:
                    ws_jf.cell(row=2, column=1 + c_idx, value=val)

        if gaozhuang_df is not None:
            if "高装高套" not in writer.book.sheetnames:
                writer.book.create_sheet("高装高套")
            ws_gz = writer.book["高装高套"]
            for r_idx, row_vals in enumerate(gaozhuang_df[["姓名", "高套数"]].values.tolist()):
                ws_gz.cell(row=2 + r_idx, column=1, value=row_vals[0])
                ws_gz.cell(row=2 + r_idx, column=2, value=row_vals[1])

        if shangji_dfs:
            df_month, df_all = shangji_dfs
            if "商机统计" not in writer.book.sheetnames:
                writer.book.create_sheet("商机统计")
            ws = writer.book["商机统计"]
            for r_idx, row_vals in enumerate(df_month.values.tolist()):
                for c_idx, val in enumerate(row_vals):
                    ws.cell(row=2 + r_idx, column=1 + c_idx, value=val)
            for r_idx, row_vals in enumerate(df_all.values.tolist()):
                for c_idx, val in enumerate(row_vals):
                    ws.cell(row=2 + r_idx, column=6 + c_idx, value=val)

    return written
