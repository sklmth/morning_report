@echo off
chcp 65001 >nul
title 早会数据处理系统 - 打包工具

echo ================================================
echo   早会数据处理系统 - 打包脚本
echo ================================================
echo.

:: ── 诊断：当前目录 ──────────────────────────────
echo [诊断] 当前工作目录：
cd
echo.

:: ── 诊断：Python ────────────────────────────────
echo [1/4] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo.
    echo [错误] 未找到 Python！
    echo 请先安装 Python 3.8+，并勾选"Add Python to PATH"
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 显示 pip 路径
echo [诊断] pip 路径：
where pip
echo.

:: ── 安装依赖 ────────────────────────────────────
echo [2/4] 安装依赖包（pyinstaller pandas openpyxl）...
echo       如果网络较慢请耐心等待...
echo.
pip install pyinstaller pandas openpyxl
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败！
    echo 请检查网络连接，或尝试使用国内镜像：
    echo   pip install pyinstaller pandas openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    pause
    exit /b 1
)
echo.
echo   依赖安装完成
echo.

:: ── 检查资源文件 ─────────────────────────────────
echo [3/4] 检查必要文件...

if not exist "src\app.py" (
    echo [错误] 未找到 src\app.py
    echo 请确认解压后在 morning_report 文件夹内运行此脚本！
    echo.
    pause
    exit /b 1
)
echo   ✓ src\app.py

if not exist "src\function.py" (
    echo [错误] 未找到 src\function.py
    echo.
    pause
    exit /b 1
)
echo   ✓ src\function.py

if not exist "assets\早会五张表.xlsx" (
    echo.
    echo [错误] 未找到 assets\早会五张表.xlsx
    echo 请将带公式的模板 Excel 放入 assets 文件夹后重试！
    echo 当前 assets 目录内容：
    dir assets\ 2>nul || echo   （assets 目录为空或不存在）
    echo.
    pause
    exit /b 1
)
echo   ✓ assets\早会五张表.xlsx
echo.

:: ── 开始打包 ─────────────────────────────────────
echo [4/4] 开始打包（约需 2-5 分钟，请勿关闭窗口）...
echo.

pyinstaller morning_report.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ================================================
    echo   [失败] 打包过程出现错误，请查看上方红色提示
    echo ================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   打包成功！
echo   输出位置：dist\早会数据处理系统.exe
echo ================================================
echo.

:: 自动打开输出目录
explorer dist

pause
