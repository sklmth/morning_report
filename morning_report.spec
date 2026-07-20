# -*- mode: python ; coding: utf-8 -*-
# 使用方法：pyinstaller morning_report.spec

import os

block_cipher = None

a = Analysis(
    ['daily_report/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # 把 function.py 和 早会五张表.xlsx 打包进去
        ('daily_report/function.py', '.'),
        ('assets/早会五张表.xlsx', '.'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='早会数据处理系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不显示黑色命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # 如有图标取消注释
)
