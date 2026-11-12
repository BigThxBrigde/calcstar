# Tasks

- [x] Task 0: 初始化 Git 仓库
  - [x] SubTask 0.1: 执行 `git init`，编写适配 Python/PyInstaller 的 `.gitignore`（`__pycache__`、`.venv`、`.pytest_cache`、`build/`、`dist/`、`*.db`、`*.egg-info` 等）
  - [x] SubTask 0.2: 确认仓库状态干净（`git status`），后续每个任务完成后按需提交

- [ ] Task 1: pyproject 工程骨架与桌面壳
  - [ ] SubTask 1.1: 创建 `pyproject.toml`（setuptools + src 布局）：元数据、运行依赖 `PyQt6`/`PyQt6-WebEngine`、dev 依赖组（pytest、pytest-cov、pyinstaller）、`[project.scripts] calcstar`、pytest/覆盖率配置（`--cov=calcstar --cov-fail-under=85`）；更新 `.gitignore`
  - [ ] SubTask 1.2: 创建 `src/calcstar/` 分层骨架：`config.py`、`domain/`（models/generator/grading）、`data/`（database/repositories）、`services/`（practice_service/stats_service）、`bridge/`（api）、`desktop/`（window），各层 `__init__.py`；提供 `python -m calcstar` 入口（`__main__.py`）
  - [ ] SubTask 1.3: 实现 `config.py`：用户数据目录与数据库路径（`%APPDATA%\CalcStar`，支持 `CALCSTAR_DB` 覆盖）、开发态/打包态资源目录解析、参数枚举与默认值
  - [ ] SubTask 1.4: 实现 `desktop/window.py`：QWebEngineView 主窗口 1024×720、加载本地 `web/index.html`、QWebChannel 注册桥接对象、关闭窗口即退出进程
  - [ ] SubTask 1.5: `pip install -e .[dev]` 安装后验证 `calcstar` 命令与 `python -m calcstar` 均能启动空窗口
  - [ ] SubTask 1.6: 编写 `CalcStar.spec` 与 `build.ps1`（PyInstaller `--onefile --windowed`，内置 web 资源与 QtWebEngine 运行时），产出 `dist\CalcStar.exe`

- [ ] Task 2: 领域层——出题引擎 `domain/`
  - [ ] SubTask 2.1: `domain/models.py`：Question、PracticeConfig 等数据类（表达式文本、正确答案、运算符序列、练习参数）
  - [ ] SubTask 2.2: `domain/generator.py`：加法／减法／加减法／乘法／除法／乘除法生成器，遵守数值范围、整除、非负约束
  - [ ] SubTask 2.3: `domain/generator.py`：四则混合运算生成器（2–3 个运算符、运算优先级、可选括号、整除步骤、中间结果约束）
  - [ ] SubTask 2.4: 批量生成与去重（同批不重复，空间不足时放宽组合）
  - [ ] SubTask 2.5: 编写 `tests/domain/test_generator.py`，覆盖各类别约束、整除性、去重、参数边界

- [ ] Task 3: 数据层 `data/`
  - [ ] SubTask 3.1: `data/database.py`：SQLite 连接管理与建表 `sessions`（参数、时间、得分、用时、订正轮次、状态、是否通过）
  - [ ] SubTask 3.2: 建表 `questions`（所属练习、序号、表达式、正确答案、用户答案、是否正确、订正次数）与 `wrong_book`（表达式+答案聚合的错题集，错误次数、最近时间、类别、范围）
  - [ ] SubTask 3.3: `data/repositories.py`：会话创建、提交判分落库、订正更新、错题集聚合与查询、历史列表与明细查询
  - [ ] SubTask 3.4: 编写 `tests/data/test_repositories.py`，覆盖建表、判分写入、错题聚合与重复错误累计

- [ ] Task 4: 服务层与桥接层
  - [ ] SubTask 4.1: `services/practice_service.py` 创建练习：校验参数 → 生成题目 → 写入会话 → 返回题目（含分页元数据）与限时信息
  - [ ] SubTask 4.2: `services/practice_service.py` 提交练习：判分（复用 `domain/grading.py`）→ 返回得分、用时、错题清单
  - [ ] SubTask 4.3: 提交订正：更新错题答案与轮次，全部正确则标记通过并返回结果
  - [ ] SubTask 4.4: `services/stats_service.py`：历史成绩列表、单次练习明细、错题集（类别筛选与排序）
  - [ ] SubTask 4.5: 用错题生成新练习的接口；`bridge/api.py` 统一包装返回值与错误为 `{"ok": bool, "data"/"error": ...}` 并注册到 QWebChannel
  - [ ] SubTask 4.6: 编写 `tests/services/` 与 `tests/bridge/` 测试，覆盖：非法参数、未作答判分、订正多轮至全对、超时提交、历史分页与明细、错题聚合/筛选/排序、桥接层错误封装

- [ ] Task 5: 前端公共框架与设置页面（儿童活泼风设计系统）
  - [ ] SubTask 5.1: 实现 `web/index.html` + `web/css/style.css` 设计令牌与组件（奶油色背景、橙/黄/绿/蓝/紫配色、24px 圆角卡片、胶囊按钮、彩色柔和投影、内联 SVG 星星/奖杯装饰、Toast 与焦点环、`prefers-reduced-motion` 降级）
  - [ ] SubTask 5.2: 实现 `web/js/qwebchannel.js`（Qt 资源内联）与 `web/js/api.js`（等待 QWebChannel 就绪、调用 `bridge.*`、统一错误提示）、页面切换路由、Toast 组件
  - [ ] SubTask 5.3: 实现设置页面：运算类别、数值范围（预设+自定义）、题量（预设+自定义）、限时（预设+自定义/不限）、允许负数、含括号、每页题数
  - [ ] SubTask 5.4: 实现参数校验与"开始练习"调用创建接口并跳转做题页

- [ ] Task 6: 前端做题页面
  - [ ] SubTask 6.1: 题目网格布局与分页控件、页码指示，翻页保留已填答案
  - [ ] SubTask 6.2: 右上角倒计时（超时自动提交）/ 正向计时（不限时）
  - [ ] SubTask 6.3: 输入框交互（自动聚焦下一题、回车跳转、数字键盘限制、未答提示）
  - [ ] SubTask 6.4: 底部提交按钮与提交中状态

- [ ] Task 7: 前端结果与订正页面
  - [ ] SubTask 7.1: 展示得分、正确率、用时、是否超时
  - [ ] SubTask 7.2: 错题列表（题目、你的答案、正确答案）与可编辑订正输入
  - [ ] SubTask 7.3: 订正提交循环，直至全对后显示"已通过"与"返回首页"，刷新历史/错题集缓存状态

- [ ] Task 8: 前端历史成绩与错题集页面
  - [ ] SubTask 8.1: 历史成绩列表与单次明细查看
  - [ ] SubTask 8.2: 错题集列表、类别筛选、按错误次数排序、空状态
  - [ ] SubTask 8.3: 错题集"重新练习"入口生成新练习并进入做题页

- [ ] Task 9: 端到端验证与打包验收
  - [ ] SubTask 9.1: 运行 `pytest --cov=calcstar --cov-fail-under=85`，全部用例通过且覆盖率达标
  - [ ] SubTask 9.2: 开发态运行 `calcstar` 验证完整流程：设置 → 做题（分页/计时）→ 提交判分 → 订正全对 → 返回首页 → 历史成绩 → 错题集
  - [ ] SubTask 9.3: 验证超时自动提交与数据持久化（重启后历史仍在）
  - [ ] SubTask 9.4: 按设计规范核对界面：配色、圆角卡片、胶囊按钮、动效、焦点环、960×640 最小尺寸与 3–4 列网格
  - [ ] SubTask 9.5: 执行 `build.ps1` 打包，确认 `dist\CalcStar.exe` 为单文件、双击可启动、无控制台窗口、无端口监听、不依赖浏览器与 WebView2

# Task Dependencies
- Task 0 已完成
- Task 1 最先执行（pyproject 与分层骨架是其余任务的基础）
- Task 2 与 Task 3 可并行（领域层与数据层互不依赖）
- Task 4 依赖 Task 2、Task 3；Task 4.6 依赖 Task 2.5、Task 3.4
- Task 5 依赖 Task 4（设置页需创建练习接口）；Task 5.1 可与 Task 4 并行推进
- Task 6 依赖 Task 5 与 Task 4.1
- Task 7 依赖 Task 6 与 Task 4.2、4.3
- Task 8 依赖 Task 5 与 Task 4.4、4.5
- Task 9 依赖 Task 1–8 全部完成
