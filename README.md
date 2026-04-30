# 早会数据处理系统

## 项目结构

```
morning_report/
├── src/
│   ├── app.py           # GUI 主程序
│   └── function.py      # 数据处理逻辑
├── assets/
│   └── 早会五张表.xlsx   # ⚠️ 请将模板文件放在这里
├── morning_report.spec  # PyInstaller 打包配置
├── build_windows.bat    # 一键打包脚本（Windows）
└── README.md
```

## 准备工作

1. 将你的 **早会五张表.xlsx**（带公式的模板）放入 `assets/` 目录
2. 确保 Windows 上已安装 Python 3.8+

## 打包成 exe

双击运行 `build_windows.bat`，等待完成后，exe 文件位于：

```
dist/早会数据处理系统.exe
```

直接将这个 exe 分发给同事，无需安装 Python。

## 功能说明

- 选择三个输入文件：高套数据、全光组网数据、完美一单数据
- 指定输出路径（默认文件名：早会五张表.xlsx）
- 处理结果会写入到模板的对应 Sheet，**保留模板中原有的公式**
- 如果遇到未配置的套餐名称，会立即终止并显示详细提示

## 更新套餐配置

编辑 `src/function.py` 中的 `GATEWAY_CONFIG` 字典，然后重新打包即可。
