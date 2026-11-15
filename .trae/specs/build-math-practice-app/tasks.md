# Tasks

- [x] Task 0: 初始化 Git 仓库
  - [x] SubTask 0.1: 执行 `git init`，编写适配 Python/PyInstaller 的 `.gitignore`（`__pycache__`、`.venv`、`.pytest_cache`、`build/`、`dist/`、`*.db`、`*.egg-info` 等）
  - [x] SubTask 0.2: 确认仓库状态干净（`git status`），后续每个任务完成后按需提交

- [x] Task 1: venv 环境与 pyproject 工程骨架、桌面壳
  - [x] SubTask 1.0: `python -m venv .venv` 创建虚拟环境；后续所有命令均使用 `.\.venv\Scripts\python.exe` / `pip`
  - [x] SubTask 1.1: 创建 `pyproject.toml`（setuptools + src 布局）：元数据、运行依赖 `PyQt5`/`PyQtWebEngine`、dev 依赖组（pytest、pytest-cov、pyinstaller）、`[project.scripts] calcstar`、pytest/覆盖率配置（`--cov=calcstar --cov-fail-under=85`）；更新 `.gitignore`；在 venv 内 `pip install -e .[dev]`
  - [x] SubTask 1.2: 创建 `src/calcstar/` 分层骨架：`config.py`、`domain/`（models/generator/grading）、`data/`（database/repositories）、`services/`（practice_service/stats_service）、`bridge/`（api）、`desktop/`（window），各层 `__init__.py`；提供 `python -m calcstar` 入口（`__main__.py`）
  - [x] SubTask 1.3: 实现 `config.py`：用户数据目录与数据库路径（`%APPDATA%\CalcStar`，支持 `CALCSTAR_DB` 覆盖）、开发态/打包态资源目录解析、参数枚举与默认值
  - [x] SubTask 1.4: 实现 `desktop/window.py`：QWebEngineView 主窗口 1024×720、加载本地 `web/index.html`、QWebChannel 注册桥接对象、关闭窗口即退出进程
  - [x] SubTask 1.5: 验证 venv 内 `calcstar` 命令与 `python -m calcstar` 均能启动空窗口
  - [x] SubTask 1.6: 编写 `CalcStar.spec` 与 `build.ps1`（PyInstaller `--onefile --windowed`，使用 venv 解释器运行 PyInstaller，内置 web 资源与 QtWebEngine 运行时），产出 `dist\CalcStar.exe`

- [x] Task 2: 领域层——出题引擎 `domain/`
  - [x] SubTask 2.1: `domain/models.py`：Question、PracticeConfig 等数据类（表达式文本、正确答案、运算符序列、练习参数）
  - [x] SubTask 2.2: `domain/generator.py`：加法／减法／加减法／乘法／除法／乘除法生成器，遵守数值范围、整除、非负约束
  - [x] SubTask 2.3: `domain/generator.py`：四则混合运算生成器（2–3 个运算符、运算优先级、可选括号、整除步骤、中间结果约束）
  - [x] SubTask 2.4: 批量生成与去重（同批不重复，空间不足时放宽组合）
  - [x] SubTask 2.5: 编写 `tests/domain/test_generator.py`，覆盖各类别约束、整除性、去重、参数边界

- [x] Task 3: 数据层 `data/`
  - [x] SubTask 3.1: `data/database.py`：SQLite 连接管理与建表 `sessions`（参数、时间、得分、用时、订正轮次、状态、是否通过）
  - [x] SubTask 3.2: 建表 `questions`（所属练习、序号、表达式、正确答案、用户答案、是否正确、订正次数）与 `wrong_book`（表达式+答案聚合的错题集，错误次数、最近时间、类别、范围）
  - [x] SubTask 3.3: `data/repositories.py`：会话创建、提交判分落库、订正更新、错题集聚合与查询、历史列表与明细查询
  - [x] SubTask 3.4: 编写 `tests/data/test_repositories.py`，覆盖建表、判分写入、错题聚合与重复错误累计

- [x] Task 4: 服务层与桥接层
  - [x] SubTask 4.1: `services/practice_service.py` 创建练习：校验参数 → 生成题目 → 写入会话 → 返回题目（含分页元数据）与限时信息
  - [x] SubTask 4.2: `services/practice_service.py` 提交练习：判分（复用 `domain/grading.py`）→ 返回得分、用时、错题清单
  - [x] SubTask 4.3: 提交订正：更新错题答案与轮次，全部正确则标记通过并返回结果
  - [x] SubTask 4.4: `services/stats_service.py`：历史成绩列表、单次练习明细、错题集（类别筛选与排序）
  - [x] SubTask 4.5: 用错题生成新练习的接口；`bridge/api.py` 统一包装返回值与错误为 `{"ok": bool, "data"/"error": ...}` 并注册到 QWebChannel
  - [x] SubTask 4.6: 编写 `tests/services/` 与 `tests/bridge/` 测试，覆盖：非法参数、未作答判分、订正多轮至全对、超时提交、历史分页与明细、错题聚合/筛选/排序、桥接层错误封装

- [x] Task 5: 前端公共框架与设置页面（儿童活泼风设计系统）
  - [x] SubTask 5.1: 实现 `web/index.html` + `web/css/style.css` 设计令牌与组件（奶油色背景、橙/黄/绿/蓝/紫配色、24px 圆角卡片、胶囊按钮、彩色柔和投影、内联 SVG 星星/奖杯装饰、Toast 与焦点环、`prefers-reduced-motion` 降级）
  - [x] SubTask 5.2: 实现 `web/js/qwebchannel.js`（Qt 资源内联）与 `web/js/api.js`（等待 QWebChannel 就绪、调用 `bridge.*`、统一错误提示）、页面切换路由、Toast 组件
  - [x] SubTask 5.3: 实现设置页面：运算类别、数值范围（预设+自定义）、题量（预设+自定义）、限时（预设+自定义/不限）、允许负数、含括号、每页题数
  - [x] SubTask 5.4: 实现参数校验与"开始练习"调用创建接口并跳转做题页

- [x] Task 6: 前端做题页面
  - [x] SubTask 6.1: 题目网格布局与分页控件、页码指示，翻页保留已填答案
  - [x] SubTask 6.2: 右上角倒计时（超时自动提交）/ 正向计时（不限时）
  - [x] SubTask 6.3: 输入框交互（自动聚焦下一题、回车跳转、数字键盘限制、未答提示）
  - [x] SubTask 6.4: 底部提交按钮与提交中状态

- [x] Task 7: 前端结果与订正页面
  - [x] SubTask 7.1: 展示得分、正确率、用时、是否超时
  - [x] SubTask 7.2: 错题列表（题目、你的答案、正确答案）与可编辑订正输入
  - [x] SubTask 7.3: 订正提交循环，直至全对后显示"已通过"与"返回首页"，刷新历史/错题集缓存状态

- [x] Task 8: 前端历史成绩与错题集页面
  - [x] SubTask 8.1: 历史成绩列表与单次明细查看
  - [x] SubTask 8.2: 错题集列表、类别筛选、按错误次数排序、空状态
  - [x] SubTask 8.3: 错题集"重新练习"入口生成新练习并进入做题页

- [x] Task 9: 端到端验证与打包验收
  - [x] SubTask 9.1: 运行 `pytest --cov=calcstar --cov-fail-under=85`，全部用例通过且覆盖率达标
  - [x] SubTask 9.2: 开发态运行 `calcstar` 验证完整流程：设置 → 做题（分页/计时）→ 提交判分 → 订正全对 → 返回首页 → 历史成绩 → 错题集
  - [x] SubTask 9.3: 验证超时自动提交与数据持久化（重启后历史仍在）
  - [x] SubTask 9.4: 按设计规范核对界面：配色、圆角卡片、胶囊按钮、动效、焦点环、960×640 最小尺寸与 3–4 列网格
  - [x] SubTask 9.5: 执行 `build.ps1` 打包，确认 `dist\CalcStar.exe` 为单文件、双击可启动、无控制台窗口、无端口监听、不依赖浏览器与 WebView2

- [x] Task 10: 算式形式扩展——三目链式算式与可变填空位置
  - [x] SubTask 10.1: `config.py` 新增 `blank_position`（固定末尾/位置不定）与 `operand_count`（两个数/三个数/随机）参数枚举与 `validate_params` 校验；`domain/models.py` 扩展 `PracticeConfig` 与 `Question`（`blank_index`/`paren_pos`）
  - [x] SubTask 10.2: `domain/generator.py` 三目链式生成器（加/减/乘/除及加减/乘除混合链，从左到右求值，中间结果越界与整除约束）与 `_blank_question` 填空位置处理（隐藏操作数、括号相邻回退）
  - [x] SubTask 10.3: 扩展生成器测试覆盖三目链式与填空位置；服务层与 `bridge/api.py` 透传新参数
  - [x] SubTask 10.4: 设置页新增「算式形式」卡片（算式目数、填空位置芯片选择与提示文案）；更新 `docs/运行说明.md`

- [x] Task 11: 成绩单导出与设置页布局微调
  - [x] SubTask 11.1: 设置页「更多选项」卡片改单行横向布局（允许负数／包含括号／每页题数一行排布，元素间 3px margin，可换行）
  - [x] SubTask 11.2: 新增 `services/report_service.py`：由会话明细构建自包含成绩单 HTML（成绩概览 + 逐题明细表，错题/未作答标红）
  - [x] SubTask 11.3: 新增 `desktop/report_exporter.py`：离屏 QWebEnginePage 加载报告 HTML 并 `printToPdf` 输出 A4 PDF；`desktop/window.py` 注入导出器（QFileDialog 选择保存路径，取消返回 None）
  - [x] SubTask 11.4: `bridge/api.py` 新增 `export_report_pdf` 槽（payload `{session_id, path?}`，统一信封；导出器缺席/取消/失败分别处理）
  - [x] SubTask 11.5: 前端成绩页新增"导出成绩单"按钮（含导出中状态、成功/取消/失败 Toast，空状态隐藏）
  - [x] SubTask 11.6: 编写 `tests/services/test_report_service.py` 与 `tests/bridge` 导出用例；运行 `pytest` 全绿且覆盖率达标

- [x] Task 12: 历史页清空历史
  - [x] SubTask 12.1: `repositories.clear_history`（删 sessions/questions，保留错题本，返回删除会话数）+ `StatsService.clear_history` + `bridge/api.py` `clear_history` 槽
  - [x] SubTask 12.2: 历史页列表底部"清空历史"按钮（4 秒二次确认，确认态红色脉冲动效；空列表隐藏），清空后 Toast 提示数量并刷新
  - [x] SubTask 12.3: data 层与桥接层测试（删除计数、保留错题本、空库幂等）；spec/checklist 同步

- [x] Task 13: 应用图标设计与打包内置
  - [x] SubTask 13.1: 设计卡通星形计算器图标，生成多尺寸 `assets/calcstar.ico`（16–256px，圆角透明）与 `assets/calcstar.png`
  - [x] SubTask 13.2: `config.get_icon_path()` 定位图标（打包态 _MEIPASS/assets，开发态仓库 assets）；`window.py` 设置窗口/任务栏图标
  - [x] SubTask 13.3: `CalcStar.spec` 图标随包内置（datas）并写入 exe 资源（icon 参数）；重新打包验证

- [x] Task 14: 更多选项恢复竖排布局与设置持久化
  - [x] SubTask 14.1: 撤销单行布局，恢复"更多选项"纵向排布（option-row + 说明文案），移除 more-row/more-item 样式
  - [x] SubTask 14.2: 新增 `data/settings_store.py`（JSON 白名单持久化 + 原子写入 + 损坏容错）与 `services/settings_service.py`；bridge 新增 `get_settings`/`save_settings` 槽
  - [x] SubTask 14.3: 前端启动时回填上次设置（预设命中/自定义展开），开始练习时静默保存
  - [x] SubTask 14.4: data/services/bridge 三层测试；spec/checklist 同步

- [x] Task 15: 成绩单导出修复（卡死/崩溃）与历史行级导出
  - [x] SubTask 15.1: 弃用离屏 QWebEnginePage 渲染，改用 QTextDocument + QPrinter 同步导出（A4 纵向、彩色表格 Qt 富文本子集），不再启动第二渲染进程
  - [x] SubTask 15.2: report_service 重写为 Qt 富文本兼容 HTML（内联配色、错题标红、√/× 判定），报告测试重写
  - [x] SubTask 15.3: 历史列表每行新增"导出"按钮（同一导出能力、防并发、导出中状态），导出测试覆盖真实 PDF 生成
  - [x] SubTask 15.4: spec/checklist/README 同步并重新打包验证

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
- Task 10 依赖 Task 9（在已完成闭环基础上扩展生成器与设置页），其中 10.1/10.2 先行、10.3 依赖前两者、10.4 依赖 10.3
- Task 11 依赖 Task 9（成绩页与历史明细数据已就绪）：11.1 独立可并行；11.2 先行，11.3 依赖 11.2，11.4 依赖 11.2/11.3，11.5 依赖 11.4，11.6 收尾
