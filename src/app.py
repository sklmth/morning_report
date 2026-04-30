import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, font
import pandas as pd

# 支持打包后找到内嵌资源
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# 导入自定义处理函数
try:
    sys.path.insert(0, resource_path("."))
    from function import (
        generate_gaotao_table, generate_quanguang_table,
        generate_wanmei_table, generate_honghuangpai_gaotao_table,
        generate_gaozhuang_gaotao_table, generate_shangji_table,
        GatewayConfigError
    )
except ImportError:
    messagebox.showerror("运行错误", "无法加载 function.py，请确保该文件与程序在同一目录。")

# ══════════════════════════════════════════════════════
#  DESIGN TOKENS — Refined Dark Editorial
# ══════════════════════════════════════════════════════
BG         = "#0C0F14"
SURFACE    = "#131820"
SURFACE2   = "#1A2030"
BORDER     = "#252D3D"
BORDER_LT  = "#2E3A50"
GOLD       = "#C8A96E"
GOLD_DIM   = "#8A7048"
TEAL       = "#4EC9B0"
GREEN      = "#3FB950"
RED        = "#F85149"
AMBER      = "#D29922"
TEXT       = "#E6EDF3"
TEXT2      = "#8B949E"
TEXT3      = "#484F58"
BTN_IDLE   = "#1F2937"
BTN_HOV    = "#263347"

FONT_HERO  = ("Microsoft YaHei UI", 20, "bold")
FONT_H2    = ("Microsoft YaHei UI", 11, "bold")
FONT_LABEL = ("Microsoft YaHei UI", 9, "bold")
FONT_BODY  = ("Microsoft YaHei UI", 9)
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_BTN   = ("Microsoft YaHei UI", 10, "bold")
FONT_MONO  = ("Consolas", 9)

# ══════════════════════════════════════════════════════
#  COMPONENTS
# ══════════════════════════════════════════════════════
class DropZone(tk.Frame):
    def __init__(self, parent, label, icon_char, callback, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self.callback  = callback
        self.file_path = None
        self._label    = label
        self._icon     = icon_char
        self._hover    = False
        self._build()

    def _build(self):
        self.card = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, cursor="hand2")
        self.card.pack(fill="both", expand=True)
        self.top_bar = tk.Frame(self.card, bg=BORDER, height=2)
        self.top_bar.pack(fill="x")
        inner = tk.Frame(self.card, bg=SURFACE, padx=14, pady=18)
        inner.pack(fill="both", expand=True)
        self.icon_lbl = tk.Label(inner, text=self._icon, font=("Segoe UI Emoji", 24), bg=SURFACE, fg=TEXT3)
        self.icon_lbl.pack(pady=(0, 8))
        self.name_lbl = tk.Label(inner, text=self._label, font=FONT_H2, bg=SURFACE, fg=TEXT2)
        self.name_lbl.pack()
        self.hint_lbl = tk.Label(inner, text="点击选择文件", font=FONT_SMALL, bg=SURFACE, fg=TEXT3, pady=4)
        self.hint_lbl.pack()
        self.file_lbl = tk.Label(inner, text="", font=FONT_SMALL, bg=SURFACE, fg=GOLD, wraplength=155)
        self.file_lbl.pack()

        for w in (self.card, inner, self.icon_lbl, self.name_lbl, self.hint_lbl, self.file_lbl):
            w.bind("<Button-1>", self._pick)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, e=None):
        if not self._hover:
            self._hover = True
            self.card.config(highlightbackground=BORDER_LT)
            if not self.file_path: self.name_lbl.config(fg=TEXT)

    def _on_leave(self, e=None):
        self._hover = False
        self.card.config(highlightbackground=BORDER if not self.file_path else GOLD_DIM)
        if not self.file_path: self.name_lbl.config(fg=TEXT2)

    def _pick(self, e=None):
        path = filedialog.askopenfilename(title=f"选择【{self._label}】文件", filetypes=[("Excel 文件", "*.xlsx *.xls")])
        if path: self.set_file(path)

    def set_file(self, path):
        self.file_path = path
        name = os.path.basename(path)
        if len(name) > 26: name = name[:23] + "…"
        self.file_lbl.config(text=name)
        self.hint_lbl.config(text="已载入 ✓", fg=TEAL)
        self.icon_lbl.config(fg=GOLD)
        self.name_lbl.config(fg=TEXT)
        self.top_bar.config(bg=GOLD)
        self.card.config(highlightbackground=GOLD_DIM, bg=SURFACE2)
        for w in self.card.winfo_children(): 
            if isinstance(w, tk.Frame): w.config(bg=SURFACE2)
        for lbl in (self.icon_lbl, self.name_lbl, self.hint_lbl, self.file_lbl): lbl.config(bg=SURFACE2)
        self.callback()

    def get(self): return self.file_path

    def reset(self):
        self.file_path = None
        self.file_lbl.config(text="")
        self.hint_lbl.config(text="点击选择文件", fg=TEXT3)
        self.icon_lbl.config(fg=TEXT3)
        self.name_lbl.config(fg=TEXT2)
        self.top_bar.config(bg=BORDER)
        self.card.config(highlightbackground=BORDER, bg=SURFACE)
        for w in self.card.winfo_children():
            if isinstance(w, tk.Frame): w.config(bg=SURFACE)
        for lbl in (self.icon_lbl, self.name_lbl, self.hint_lbl, self.file_lbl): lbl.config(bg=SURFACE)

class PillButton(tk.Label):
    def __init__(self, parent, text, command, primary=False, **kwargs):
        self._primary = primary
        bg_idle = GOLD if primary else BTN_IDLE
        fg_idle = "#0C0F14" if primary else TEXT2
        super().__init__(parent, text=text, font=FONT_BTN if primary else FONT_H2, bg=bg_idle, fg=fg_idle,
                         padx=28 if primary else 18, pady=9, cursor="hand2", **kwargs)
        self._cmd, self._bg_i, self._fg_i = command, bg_idle, fg_idle
        self._bg_h = "#D4B47A" if primary else BTN_HOV
        self._fg_h = "#0C0F14" if primary else TEXT
        self._active = True
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)
        self.bind("<Button-1>", self._click)

    def _hover_on(self, e=None):
        if self._active: self.config(bg=self._bg_h, fg=self._fg_h)
    def _hover_off(self, e=None):
        self.config(bg=self._bg_i if self._active else BTN_IDLE, fg=self._fg_i if self._active else TEXT3)
    def _click(self, e=None):
        if self._active and self._cmd: self._cmd()
    def set_active(self, val: bool):
        self._active = val
        self.config(bg=self._bg_i if val else BTN_IDLE, fg=self._fg_i if val else TEXT3, cursor="hand2" if val else "")
    def set_text(self, t): self.config(text=t)

# ══════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        if "Cascadia Code" in tk.font.families():
            global FONT_MONO
            FONT_MONO = ("Cascadia Code", 9)
        self.title("早会数据处理系统")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(1020, 780)
        self._build_ui()

    def _center(self, w, h):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build_ui(self):
        self._build_header()
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self._build_step_labels(content)
        right = tk.Frame(content, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_file_section(right)
        self._build_output_section(right)
        self._build_action_row(right)
        self._build_log_section(right)
        self._log("系统就绪 — 请载入文件并指定保存路径。", "info")

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(22, 16))
        left = tk.Frame(hdr, bg=BG)
        left.pack(side="left", fill="y")
        tk.Frame(left, bg=GOLD, width=3).pack(side="left", fill="y", padx=(0, 14))
        title_block = tk.Frame(left, bg=BG)
        title_block.pack(side="left")
        tk.Label(title_block, text="早会数据处理系统", font=FONT_HERO, bg=BG, fg=TEXT).pack(anchor="w")
        sub_row = tk.Frame(title_block, bg=BG)
        sub_row.pack(anchor="w")
        tk.Label(sub_row, text="Morning Report Automation", font=FONT_BODY, bg=BG, fg=TEXT2).pack(side="left")
        tk.Label(sub_row, text="  v1.1", font=FONT_SMALL, bg=BG, fg=GOLD_DIM).pack(side="left")
        self._status_dot = tk.Label(hdr, text="● 就绪", font=FONT_LABEL, bg=BG, fg=GREEN)
        self._status_dot.pack(side="right", padx=4)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=28, pady=(0, 10))

    def _build_step_labels(self, parent):
        col = tk.Frame(parent, bg=BG, width=64)
        col.pack(side="left", fill="y", padx=(0, 16))
        col.pack_propagate(False)
        for s_num, s_lab, p_top in [("①", "载入\n文件", 60), ("②", "保存\n路径", 180), ("③", "处理\n日志", 120)]:
            blk = tk.Frame(col, bg=BG, pady=p_top)
            blk.pack(fill="x")
            tk.Label(blk, text=s_num, font=("Microsoft YaHei UI", 16, "bold"), bg=BG, fg=GOLD).pack()
            tk.Label(blk, text=s_lab, font=FONT_SMALL, bg=BG, fg=TEXT2, justify="center").pack()

    def _build_file_section(self, parent):
        sec = tk.Frame(parent, bg=BG, pady=4)
        sec.pack(fill="x")
        
        # 第一行文件区
        row1 = tk.Frame(sec, bg=BG)
        row1.pack(fill="x", pady=(0, 6))
        zones1 = [("高套数据", "📊"), ("完美一单数据", "✨")]
        attrs1 = ["zone_gaotao", "zone_wanmei"]
        for i, ((label, icon), attr) in enumerate(zip(zones1, attrs1)):
            z = DropZone(row1, label, icon, self._on_file_change)
            z.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))
            setattr(self, attr, z)
            
        # 第二行文件区
        row2 = tk.Frame(sec, bg=BG)
        row2.pack(fill="x")
        zones2 = [("红黄牌高套", "🏷"), ("商机管控表", "💼")]
        attrs2 = ["zone_honghuangpai", "zone_shangji"]
        for i, ((label, icon), attr) in enumerate(zip(zones2, attrs2)):
            z = DropZone(row2, label, icon, self._on_file_change)
            z.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))
            setattr(self, attr, z)

    def _build_output_section(self, parent):
        sec = tk.Frame(parent, bg=BG, pady=14)
        sec.pack(fill="x")
        path_frame = tk.Frame(sec, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        path_frame.pack(fill="x")
        self.out_var = tk.StringVar(value="")
        self.path_entry = tk.Entry(path_frame, textvariable=self.out_var, font=FONT_BODY, bg=SURFACE, fg=TEXT2,
                                   insertbackground=GOLD, relief="flat", bd=10, state="readonly")
        self.path_entry.pack(side="left", fill="both", expand=True)
        browse = tk.Label(path_frame, text="选择路径", font=FONT_LABEL, bg=SURFACE2, fg=GOLD_DIM, padx=16, pady=10, cursor="hand2")
        browse.pack(side="right")
        browse.bind("<Button-1>", lambda e: self._pick_output())
        browse.bind("<Enter>", lambda e: browse.config(fg=GOLD, bg=BTN_HOV))
        browse.bind("<Leave>", lambda e: browse.config(fg=GOLD_DIM, bg=SURFACE2))

    def _build_action_row(self, parent):
        row = tk.Frame(parent, bg=BG, pady=12)
        row.pack(fill="x")
        self.run_btn = PillButton(row, text="▶  开始处理", command=self._start_process, primary=True)
        self.run_btn.pack(side="left")
        self.run_btn.set_active(False)
        self.reset_btn = PillButton(row, text="↺  重置", command=self._reset)
        self.reset_btn.pack(side="left", padx=(10, 0))
        self._prog_lbl = tk.Label(row, text="", font=FONT_SMALL, bg=BG, fg=TEAL)
        self._prog_lbl.pack(side="left", padx=14)

    def _build_log_section(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(2, 10))
        log_hdr = tk.Frame(parent, bg=BG)
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="处理日志", font=FONT_LABEL, bg=BG, fg=TEXT2).pack(side="left")
        clear_btn = tk.Label(log_hdr, text="清空", font=FONT_SMALL, bg=BG, fg=TEXT3, cursor="hand2", padx=4)
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self._clear_log())
        log_wrap = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        log_wrap.pack(fill="both", expand=True, pady=(6, 0))
        sb = tk.Scrollbar(log_wrap, bg=SURFACE, troughcolor=SURFACE)
        sb.pack(side="right", fill="y")
        self.log_text = tk.Text(log_wrap, font=FONT_MONO, bg=SURFACE, fg=TEXT2, relief="flat", bd=10, wrap="word",
                                state="disabled", yscrollcommand=sb.set, height=7)
        self.log_text.pack(fill="both", expand=True)
        sb.config(command=self.log_text.yview)
        for tag, color in [("info", TEXT2), ("success", GREEN), ("error", RED), ("warn", AMBER), ("accent", GOLD), ("dim", TEXT3)]:
            self.log_text.tag_config(tag, foreground=color)

    # ══════════════════════════════════════════════════
    #  INTERACTION LOGIC
    # ══════════════════════════════════════════════════
    def _on_file_change(self):
        has_any_file = any([
            self.zone_gaotao.get(), self.zone_wanmei.get(),
            self.zone_honghuangpai.get(), self.zone_shangji.get()
        ])
        if has_any_file and self.out_var.get():
            self.run_btn.set_active(True)
        elif has_any_file:
            self._log("文件已就绪 — 请指定保存路径。", "warn")

    def _pick_output(self):
        path = filedialog.asksaveasfilename(title="另存为", defaultextension=".xlsx", initialfile="早会五张表.xlsx", filetypes=[("Excel 文件", "*.xlsx")])
        if path:
            self.out_var.set(path)
            self.path_entry.config(fg=TEXT)
            self._on_file_change()

    def _reset(self):
        for z in (self.zone_gaotao, self.zone_wanmei, self.zone_honghuangpai, self.zone_shangji): z.reset()
        self.out_var.set(""); self.path_entry.config(fg=TEXT3); self.run_btn.set_active(False)
        self._status_dot.config(text="● 就绪", fg=GREEN); self._prog_lbl.config(text="")
        self._log("─" * 40, "dim"); self._log("已重置。", "info")

    def _clear_log(self):
        self.log_text.config(state="normal"); self.log_text.delete("1.0", "end"); self.log_text.config(state="disabled")

    def _log(self, msg, tag="info"):
        self.log_text.config(state="normal"); self.log_text.insert("end", msg + "\n", tag); self.log_text.see("end"); self.log_text.config(state="disabled")

    def _set_progress(self, text): self._prog_lbl.config(text=text)

    # ══════════════════════════════════════════════════
    #  PROCESSING LOGIC
    # ══════════════════════════════════════════════════
    def _start_process(self):
        self.run_btn.set_active(False); self.run_btn.set_text("处理中…")
        self._status_dot.config(text="● 处理中", fg=AMBER)
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self):
        out_path = self.out_var.get()
        tasks = [
            (self.zone_gaotao,      "高套数据", generate_gaotao_table,             "高套"),
            (self.zone_honghuangpai,"红黄牌",   generate_honghuangpai_gaotao_table, "红黄牌高套"),
            (self.zone_honghuangpai,"红黄牌(高装高套)", generate_gaozhuang_gaotao_table, "高装高套"),
        ]

        try:
            self.after(0, lambda: self._log("─" * 40, "dim"))
            self.after(0, lambda: self._log("开始执行数据处理...", "accent"))

            sheet_results = {}
            processed_count = 0

            # 1. 循环处理普通表格（高套、红黄牌）
            for zone, label, proc_func, sheet_name in tasks:
                f_path = zone.get()
                if not f_path: continue

                self.after(0, lambda l=label: (self._set_progress(f"计算 {l}…"), self._log(f"  ⚙  处理 {l}…", "info")))
                data = pd.read_excel(f_path, sheet_name=None)
                sheet_results[sheet_name] = proc_func(data)
                self.after(0, lambda: self._log(f"    ✓ 完成", "success"))
                processed_count += 1

            # 2. 处理完美一单（同时生成完美一单表和全光组网表）
            wm_path = self.zone_wanmei.get()
            if wm_path:
                self.after(0, lambda: (self._set_progress("计算 完美一单 & 全光组网…"), self._log("  ⚙  处理 完美一单数据…", "info")))
                wm_data = pd.read_excel(wm_path, sheet_name=None)
                sheet_results["完美一单"] = generate_wanmei_table(wm_data)
                self.after(0, lambda: self._log("    ✓ 完美一单 完成", "success"))
                self.after(0, lambda: self._log("  ⚙  处理 全光组网（来自完美一单数据）…", "info"))
                sheet_results["全光组网"] = generate_quanguang_table(wm_data)
                self.after(0, lambda: self._log("    ✓ 全光组网 完成", "success"))
                processed_count += 1

            # 3. 处理商机管控表
            sj_path = self.zone_shangji.get()
            shangji_dfs = None
            if sj_path:
                self.after(0, lambda: (self._set_progress("计算 商机管控…"), self._log(f"  ⚙  处理 商机管控表…", "info")))
                sj_data = pd.read_excel(sj_path, sheet_name=None, header=None)
                df_month, df_all = generate_shangji_table(sj_data)
                shangji_dfs = (df_month, df_all)
                self.after(0, lambda: self._log(f"    ✓ 完成 (商机统计)", "success"))
                processed_count += 1

            if not sheet_results and not shangji_dfs:
                raise Exception("未检测到有效的输入文件。")

            # 4. 写入文件
            self.after(0, lambda: (self._set_progress("写入文件…"), self._log("  📝 正在生成输出 Excel…", "info")))
            template_path = resource_path("早会五张表.xlsx")

            if os.path.exists(template_path):
                shutil.copy2(template_path, out_path)

            # 将「高装高套」从普通写入列表中分离出来，单独用单元格方式写入
            gaozhuang_df = sheet_results.pop("高装高套", None)

            with pd.ExcelWriter(out_path, engine="openpyxl",
                                mode="a" if os.path.exists(template_path) else "w",
                                if_sheet_exists="replace" if os.path.exists(template_path) else None) as writer:

                # 写入普通表（不含高装高套）
                for s_name, df in sheet_results.items():
                    df.to_excel(writer, sheet_name=s_name, index=False)

                # 写入高装高套：只写姓名(A列)和高套数(B列)，保留 sheet 中其他列（目标、完成率等）
                if gaozhuang_df is not None:
                    if "高装高套" not in writer.book.sheetnames:
                        writer.book.create_sheet("高装高套")
                    ws_gz = writer.book["高装高套"]
                    for r_idx, row_vals in enumerate(gaozhuang_df[["姓名", "高套数"]].values.tolist()):
                        ws_gz.cell(row=2 + r_idx, column=1, value=row_vals[0])  # 姓名 → A列
                        ws_gz.cell(row=2 + r_idx, column=2, value=row_vals[1])  # 高套数 → B列

                # 写入商机统计：两个表写入同一 sheet，用 openpyxl 直接操作单元格避免覆盖
                if shangji_dfs:
                    df_month, df_all = shangji_dfs

                    # 确保 sheet 存在
                    if "商机统计" not in writer.book.sheetnames:
                        writer.book.create_sheet("商机统计")
                    ws = writer.book["商机统计"]

                    # 当月商机统计 → A2:D15（row=2, col=1）
                    for r_idx, row_vals in enumerate(df_month.values.tolist()):
                        for c_idx, val in enumerate(row_vals):
                            ws.cell(row=2 + r_idx, column=1 + c_idx, value=val)

                    # 所有商机统计 → F2:I15（row=2, col=6）
                    for r_idx, row_vals in enumerate(df_all.values.tolist()):
                        for c_idx, val in enumerate(row_vals):
                            ws.cell(row=2 + r_idx, column=6 + c_idx, value=val)

            self.after(0, lambda: (
                self._log(f"  ✅ 处理完成！", "success"),
                self._log(f"  💾 保存路径：{out_path}", "dim"),
                self._log("─" * 40, "dim"),
                self._set_progress(""),
                self._status_dot.config(text="● 完成", fg=GREEN),
                messagebox.showinfo("处理完成", f"任务已结束！\n文件已成功保存。")
            ))

        except GatewayConfigError as e:
            self._handle_error("配置错误", str(e))
        except Exception as e:
            self._handle_error("处理失败", f"{type(e).__name__}: {e}")
        finally:
            self.after(0, lambda: (self.run_btn.set_active(True), self.run_btn.set_text("▶  开始处理")))

    def _handle_error(self, title, msg):
        self.after(0, lambda: (
            self._log(f"⛔ {title}：{msg}", "error"),
            self._set_progress(""),
            self._status_dot.config(text="● 错误", fg=RED),
            messagebox.showerror(title, msg)
        ))

if __name__ == "__main__":
    app = App()
    app.mainloop()
