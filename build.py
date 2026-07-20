"""
打包脚本（备用方案）
如果 build_windows.bat 无法运行，请在 morning_report 目录下执行：
    python build.py
"""

import os
import sys
import subprocess

def run(cmd, desc=""):
    print(f"\n{'─'*50}")
    if desc:
        print(f"▶ {desc}")
    print(f"  命令: {cmd}")
    print('─'*50)
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n❌ 失败！返回码: {result.returncode}")
        sys.exit(1)
    return result

def main():
    # 确保在正确目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"工作目录: {script_dir}")

    # 检查必要文件
    checks = [
        ("daily_report/app.py", "主程序"),
        ("daily_report/function.py", "处理逻辑"),
        ("assets/早会五张表.xlsx", "Excel模板"),
        ("morning_report.spec", "打包配置"),
    ]
    print("\n[检查文件]")
    for path, name in checks:
        exists = os.path.exists(path)
        status = "✓" if exists else "✗ 缺失"
        print(f"  {status}  {name}: {path}")
        if not exists:
            if "早会五张表" in path:
                print("\n  ⚠️  请将带公式的模板Excel放入 assets/ 目录！")
            sys.exit(1)

    # 安装依赖
    run("pip install pyinstaller pandas openpyxl", "安装依赖")

    # 打包
    run("pyinstaller morning_report.spec --clean --noconfirm", "打包中（请耐心等待）")

    print("\n" + "="*50)
    print("✅ 打包完成！")
    print(f"   输出文件: {os.path.join(script_dir, 'dist', '早会数据处理系统.exe')}")
    print("="*50)
    os.startfile(os.path.join(script_dir, "dist"))

if __name__ == "__main__":
    main()
