# 小学四则混合运算练习系统 Spec

## Why
为小学生提供一个可离线运行、界面现代化的口算练习工具：自动出题、限时答题、即时判分、错题订正直到全对，并把每次成绩与错题沉淀到本地数据库，方便家长/老师跟踪学习效果。

## What Changes
- 新增基于 Python 的纯桌面应用（PyQt5 + PyQtWebEngine 直接加载本地前端资源，内置 Chromium 内核，通过 QWebChannel 桥接调用后端，不启动任何 HTTP 服务、不经浏览器、无需安装 WebView2 或任何外部运行时）。
- 项目采用 **pyproject.toml**（PEP 621）管理元数据、依赖与工具配置，src 布局，提供 `calcstar` 控制台入口与 `python -m calcstar` 运行方式；开发环境统一使用项目根目录下的 **venv**（`.venv`），所有命令（pytest、打包、运行）均通过 `.venv` 解释器执行。
- 新增 PyInstaller 打包流程，产出**单文件 `CalcStar.exe`，双击即运行，无控制台窗口、无需安装 Python、无需浏览器**。
- 新增"设置 → 做题 → 判分订正 → 返回设置"的完整闭环流程。
- 新增题库随机生成引擎（加／减／加减／乘／除／乘除／四则混合，可控数值范围、题量、是否含括号）。
- 新增 SQLite 持久化：练习记录、逐题作答明细、错题集。
- 新增历史成绩页与错题集页。
- 全部为新增能力，无 **BREAKING** 变更。

## Impact
- 影响能力：出题引擎、练习会话管理、判分与订正、成绩历史、错题本、桌面启动器与打包发布。
- 影响代码（新建）：`src/calcstar/` 下分层 Python 包（见技术方案）、`web/` 下前端静态资源、`pyproject.toml` 项目配置、`build.ps1` + `CalcStar.spec` 打包脚本，`tests/` 下各层测试。

## 技术方案（约定）
- Python 3.13 + **PyQt5 + PyQtWebEngine**（`QWebEngineView` + `QWebChannel`）作为桌面外壳。选择理由：QtWebEngine 自带完整 Chromium，目标机器**无需预装 WebView2 运行时、无需浏览器**，离线自包含，满足"零外部依赖"要求。前端资源随包内置于 `web/`，窗口直接加载本地文件。
- 开发环境：项目根目录创建 **venv**（`.venv`），文档与脚本统一使用 `.venv` 解释器路径（如 `.\.venv\Scripts\python.exe` / `.\.venv\Scripts\Activate.ps1`）；`python -m venv .venv` 建立后用其中 pip 安装 `-e .[dev]`。
- 前后端通信使用 `QWebChannel`：Python 侧注册桥接对象，前端加载内联的 `qwebchannel.js` 后调用 `bridge.<method>(payload, callback)`，后端返回 JSON 兼容对象。**不开放任何端口、不使用 HTTP、不支持浏览器访问**。
- 包名与分层（src 布局，层间单向依赖 `desktop → bridge → services → domain/data`，domain 与 data 不互相依赖、均不依赖 UI）：
  - `src/calcstar/config.py` — 路径解析（用户数据目录、数据库路径、资源目录）、参数枚举与默认值
  - `src/calcstar/domain/` — 领域层（纯逻辑、零 IO）：`models.py`（Question、PracticeConfig 等数据类）、`generator.py`（出题引擎）、`grading.py`（判分）
  - `src/calcstar/data/` — 数据层：`database.py`（SQLite 连接与建表）、`repositories.py`（会话/题目/错题仓储查询）
  - `src/calcstar/services/` — 应用服务层（业务编排）：`practice_service.py`（创建/提交/订正）、`stats_service.py`（历史/错题集）
  - `src/calcstar/bridge/` — 桥接层：`api.py`（暴露给前端的方法集，统一包装 `{"ok": bool, "data"/"error": ...}`）
  - `src/calcstar/desktop/` — 桌面壳：`window.py`（QWebEngineView 窗口、QWebChannel 注册、应用入口）
- 前端为无构建步骤的原生 HTML/CSS/JS，界面使用现代卡片式布局、柔和渐变、圆角、轻量动效，响应式适配 1024×640 及以上窗口。
- 构建：`pyproject.toml`（setuptools 后端）声明依赖（`PyQt5`、`PyQtWebEngine`）、开发依赖（pytest、pytest-cov、pyinstaller）与 `[project.scripts]` 入口；pytest/覆盖率配置同样写入 pyproject.toml。
- 打包：PyInstaller `--onefile --windowed`，前端资源与图标内置；产物为单个 `dist/CalcStar.exe`。QtWebEngine 运行时随包打包，目标机器无需安装任何额外组件。
- 数据存放于用户数据目录（Windows：`%APPDATA%\CalcStar\calcstar.db`），也可通过环境变量 `CALCSTAR_DB` 覆盖；exe 无安装、可整体复制迁移。

## ADDED Requirements

### Requirement: 设置页面（欢迎界面）
系统 SHALL 在启动后展示设置页面，允许用户配置本次练习的全部参数。

#### Scenario: 配置练习参数
- **WHEN** 用户打开应用
- **THEN** 页面展示：运算类别（加法／减法／加减法／乘法／除法／乘除法／四则混合运算）、数值范围（10／20／30／50／100，支持自定义正整数）、题目数量（20／50／100，支持自定义 1–200）、限时（不限时／5 分钟／10 分钟／15 分钟／30 分钟，或自定义 1–180 分钟）、是否允许负数结果（默认不允许）、四则混合时是否包含括号、每页题目数（5／10／20）
- **WHEN** 用户点击"开始练习"
- **THEN** 系统按所选参数生成题目并进入做题页面

#### Scenario: 参数校验
- **WHEN** 用户输入非法参数（如范围为 0、题量超限）
- **THEN** 页面显示友好提示且不进入做题页面

### Requirement: 题目生成引擎
系统 SHALL 依据运算类别与数值范围生成符合小学口算规范、结果唯一的可判定题目。

#### Scenario: 加减法
- **WHEN** 类别为加法／减法／加减法，范围为 N
- **THEN** 操作数与结果均在 `[0, N]` 内；减法结果不为负（除非用户显式允许负数）；不出现无意义的 `+0`／`-0` 作为唯一形式

#### Scenario: 乘除法
- **WHEN** 类别为乘法／除法／乘除法，范围为 N
- **THEN** 乘法两因数与结果均不超过 N；除法必须整除且商与被除数均不超过 N，除数不为 0

#### Scenario: 四则混合运算
- **WHEN** 类别为四则混合运算
- **THEN** 表达式含 2–3 个运算符，严格遵循先乘除后加减的运算顺序；除法步骤必须整除；任意中间结果非负且不超过 N（除非允许负数）；是否含括号由设置决定

#### Scenario: 题量去重
- **WHEN** 生成 total 道题
- **THEN** 同一份练习内表达式不重复；当可生成空间不足时，适度放宽数值组合而不是重复题目

### Requirement: 做题页面
系统 SHALL 提供只含题目与必要操作的做题界面。

#### Scenario: 题目呈现与分页
- **WHEN** 题目数量超过每页数量
- **THEN** 题目按行×列网格排列并分页，提供上一页／下一页与页码指示，翻页不丢失已填写内容

#### Scenario: 倒计时与自动提交
- **WHEN** 用户设置了限时
- **THEN** 右上角显示倒计时；倒计时归零时系统自动提交当前答案，未作答题目按错误计
- **WHEN** 用户未设置限时
- **THEN** 右上角改为正向计时显示，不自动提交

#### Scenario: 手动提交
- **WHEN** 用户点击"提交"
- **THEN** 系统校验所有已填答案，未作答题目按错误计，进入结果页面

### Requirement: 判分与订正闭环
系统 SHALL 对提交结果判分，并要求用户改正全部错题后本次练习才算通过。

#### Scenario: 首次判分
- **WHEN** 用户提交答案
- **THEN** 系统逐题判定对错，展示得分（正确数／总数、百分制分数）与用时，并列出所有错题（题目、你的答案、正确答案）

#### Scenario: 订正直到全对
- **WHEN** 结果页存在错题
- **THEN** 错题以可编辑输入框展示，用户可重新填写并点击"提交订正"
- **WHEN** 订正后仍有错误
- **THEN** 保留错误项继续订正，并累计订正轮次
- **WHEN** 所有错题订正正确
- **THEN** 标记本次练习"已通过"，成绩与错题写入数据库，展示"完成"按钮返回设置页面

### Requirement: 成绩历史
系统 SHALL 持久化并展示每次练习记录。

#### Scenario: 查看历史成绩
- **WHEN** 用户进入"历史成绩"页面
- **THEN** 以列表展示每次练习的开始时间、运算类别、数值范围、题量、用时、正确率、得分、是否通过，按时间倒序
- **WHEN** 用户点击某条记录
- **THEN** 展示该次练习的逐题明细（题目、你的答案、正确答案、是否错误）

### Requirement: 错题集
系统 SHALL 基于历史错题生成错题集。

#### Scenario: 自动汇总错题
- **WHEN** 一次练习产生错题
- **THEN** 系统按"表达式 + 正确答案"聚合，累计错误次数、最近错误时间与所属类别／范围

#### Scenario: 浏览与复习错题
- **WHEN** 用户进入"错题集"页面
- **THEN** 列表展示错题表达式、正确答案、错误次数，支持按类别筛选与按错误次数排序
- **WHEN** 用户点击错题集中的"重新练习错题"
- **THEN** 以选中错题生成一份新的练习（题量与限时沿用默认设置），完成后按上述闭环判分

### Requirement: 桌面套壳与本地数据
系统 SHALL 以纯本地桌面应用形式运行，不依赖浏览器、不依赖 WebView2 等外部运行时、不开放网络端口，数据仅保存在本地。

#### Scenario: 桌面启动
- **WHEN** 用户双击 `CalcStar.exe`（或开发态运行 `calcstar` / `python -m calcstar`）
- **THEN** 直接打开 1024×720 起步的原生窗口加载应用界面，无控制台窗口、无浏览器标签页、无本地端口监听，首次运行自动建库建表
- **WHEN** 用户关闭窗口
- **THEN** 进程完全退出，无残留后台进程

#### Scenario: 零外部运行时依赖
- **WHEN** 在全新 Win10/11 机器（未安装 WebView2、未装任何浏览器）上运行
- **THEN** 应用正常启动并渲染界面——Chromium 内核随程序自带，不提示任何"缺少组件"或引导外部下载

#### Scenario: 数据持久化
- **WHEN** 应用重启
- **THEN** 历史成绩与错题集仍可查看，数据文件位于用户数据目录

### Requirement: 独立可执行文件
系统 SHALL 能打包为零依赖的单文件可执行程序供分发。

#### Scenario: 打包产物
- **WHEN** 执行 `.\build.ps1`
- **THEN** 生成 `dist\CalcStar.exe` 单文件（内置前端资源、Python 运行时与 QtWebEngine/Chromium 内核），双击即可运行，无需安装 Python 或任何第三方库
- **WHEN** 用户把该 exe 拷贝到另一台 Win10/11 机器
- **THEN** 双击可正常运行并新建自己的本地数据库

#### Scenario: 体积与启动
- **WHEN** 双击运行 exe
- **THEN** 窗口在数秒内出现，界面为本地加载（不请求任何外网资源，图标/字体不依赖 CDN）

### Requirement: 界面风格（儿童活泼风）
系统 SHALL 提供统一、活泼但不杂乱的儿童化界面，全部视觉资源本地内联，不依赖外网字体或图片。

#### Scenario: 设计规范落地
- **WHEN** 用户使用任意页面
- **THEN** 界面遵循以下设计令牌：
  - 背景：暖奶油底 `#FFF9F2`，叠加天空蓝 `#E8F4FF` 与淡黄 `#FFF3D6` 的柔和分区色块
  - 主色：活力橙 `#FF8A3D`；辅助色：阳光黄 `#FFC93C`、草绿 `#4CC38A`、天蓝 `#4FA8FF`、葡萄紫 `#9B7BF7`；语义色：正确 `#2FBF71`、错误 `#FF5A5F`
  - 字体：系统圆润字体栈（`"Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif`），标题 700–800 字重、正文 500，数字加粗并适度放大
  - 形状：卡片圆角 24px、按钮全圆角胶囊、输入框 16px 圆角，柔和彩色投影（如 `0 8px 24px rgba(255,138,61,.18)`）
  - 装饰：用内联 SVG/CSS 绘制星星、奖杯、铅笔、橡皮等小插画与背景圆点，不使用外链图片
- **WHEN** 用户与控件交互
- **THEN** 按钮悬停上浮 2px 并加深阴影、按下缩放至 0.97，卡片与页面切换有 150–250ms 淡入上滑动效，答对时打勾图标弹跳、得分数字滚动计数；所有动效可通过 `prefers-reduced-motion` 关闭

#### Scenario: 页面布局
- **WHEN** 窗口宽度 ≥ 960px
- **THEN** 设置页为左右分区（左侧参数卡片、右侧卡通预览/开始按钮），做题页为 3–4 列自适应题目网格，结果页为上方得分徽章 + 下方错题卡片列表，历史/错题集为表格化卡片列表；窗口最小支持 960×640

#### Scenario: 反馈与可达性
- **WHEN** 出现校验错误、提交成功、超时等状态
- **THEN** 使用页内 Toast/横幅与元素高亮反馈，不用阻塞式弹窗；所有可交互元素有清晰 `:focus-visible` 焦点环，文字与背景对比度符合可读性要求

### Requirement: 工程化与自动化测试
系统 SHALL 以 pyproject.toml 管理构建配置、以 Git 仓库管理源码，并以 pytest 覆盖后端核心逻辑。

#### Scenario: pyproject 构建
- **WHEN** 检查仓库根目录
- **THEN** 存在 `pyproject.toml`（PEP 621）：含项目元数据、运行依赖 `PyQt6`/`PyQt6-WebEngine`、可选开发依赖组 `dev`（pytest、pytest-cov、pyinstaller）、`[project.scripts]` 提供 `calcstar` 命令、pytest 与覆盖率配置；pytest/覆盖率配置不再散落在 ini 文件
- **WHEN** 开发者初始化环境
- **THEN** 在项目根目录执行 `python -m venv .venv` 创建虚拟环境，再用 venv 内的 pip 执行 `pip install -e .[dev]`；之后 `pytest`、`calcstar`、打包均通过 `.venv` 环境运行（venv 目录不入库，已被 `.gitignore` 忽略）

#### Scenario: 仓库初始化
- **WHEN** 项目开始开发
- **THEN** 已执行 `git init`，提供适配 src 布局/PyInstaller 的 `.gitignore`（忽略 `__pycache__`、`.venv`、`build/`、`dist/`、`*.egg-info`、覆盖率产物、本地数据库文件等），并完成首次提交

#### Scenario: 测试覆盖
- **WHEN** 运行 `pytest`
- **THEN** 全部用例通过，且 `src/calcstar/` 包语句覆盖率不低于 85%
- **WHEN** 检查测试内容
- **THEN** 至少覆盖：各运算类别的范围/非负/整除/括号与优先级约束、批量去重与可生成空间不足的降级、参数校验边界（0、负数、超上限）、落库与持久化、判分与未作答处理、订正多轮至全对的状态流转、错题集聚合与重复错误累计、历史分页与明细、超时自动提交、桥接层统一错误返回

