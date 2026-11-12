# CalcStar ⭐

一个为小学生打造的四则混合运算练习桌面应用。双击即用、离线运行、界面活泼，让孩子在闯关式的"做题 → 订正 → 全对通过"闭环中练好口算。

## 特性

- **七类运算自由配**：加法 / 减法 / 加减法 / 乘法 / 除法 / 乘除法 / 四则混合运算
- **难度可控**：10～1000 以内数值范围、题量（1–200）、可选括号、允许负数
- **限时挑战**：5/10/15/30 分钟或自定义时长，倒计时归零自动交卷；不限时则正向计时
- **自动判分订正**：提交即判分，错题逐题订正，直到全部答对才算通关
- **错题本**：按"表达式 + 正确答案"聚合错题，累计错误次数，支持筛选排序与一键重练
- **历史成绩**：每次练习的时间、类别、用时、得分、通过状态全部留档
- **数据本地化**：SQLite 存储，数据不出机器

## 技术栈

| 层 | 技术 |
|---|---|
| 桌面壳 | Python 3.13 + PyQt5 / PyQtWebEngine（内置 Chromium，无需浏览器或 WebView2） |
| 前后端通信 | QWebChannel 桥接，无 HTTP、无端口 |
| 前端 | 原生 HTML / CSS / JS，儿童活泼风设计系统 |
| 持久化 | SQLite |
| 构建 | pyproject.toml（src 布局）+ PyInstaller 单文件 exe |

## 快速开始（开发）

```powershell
# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装项目与开发依赖
pip install -e .[dev]

# 3. 启动应用
calcstar          # 或 python -m calcstar

# 4. 运行测试
pytest --cov=calcstar --cov-fail-under=85
```

## 打包发布

```powershell
.\build.ps1      # 产出 dist\CalcStar.exe，双击即可运行
```

打包产物为单文件 exe，内置 Python 运行时、QtWebEngine 内核与全部前端资源，目标机器无需安装任何组件。

## 数据存储

数据库位于用户数据目录（Windows：`%APPDATA%\CalcStar\calcstar.db`），可通过环境变量 `CALCSTAR_DB` 自定义路径。

## License

本项目基于 [MIT License](LICENSE) 开源。
