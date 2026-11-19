# 代码规范整改计划（PEP8 / PEP20 / ES 标准）

## 背景与目标

对 CalcStar 全仓 Python 与前端 JS 做规范审查并分批修复。

- Python 基线：`pycodestyle --max-line-length=79 src tests` 共 **105 处 E501**（src 65 / tests 40），另有若干 PEP20（The Zen of Python）可读性问题与潜在运行时缺陷。
- JS 基线：无 ESLint 配置（`js_tests/package.json` 仅 Jest + jsdom），代码已普遍使用 `"use strict"`、IIFE 命名空间、`let/const`、`async/await`；无 `var`/`eval`/尾随逗号滥用。存在 2 个 Major（桥接 Promise 永久失败缓存、aria-label XSS）与若干 ES6+ 可用而未用的改进点。
- 项目无 linter 配置，PEP8 采用官方默认 **79 字符**行宽。

## 范围

- Python：`src/calcstar/**/*.py`（21 文件）、`tests/**/*.py`（15 文件）
- JS：`web/js/**/*.js`（10 文件）
- 不改行为契约：所有修复以等价重构为主；涉及错误处理的修复以“补日志/可重试”方式增强，不改变返回枚举与数据结构。

## 批次划分（每批一个提交）

### Batch 1 — Python 正确性与 PEP20（src）
- `stats_service.py`：`_DBPath = Union[str, "os.PathLike[str]"]` 未导入 `os`，前向引用无法解析；改用具名 `Path` 约定。
- `window.py`：`except Exception: self._bridge = None` 静默吞异常（Zen: Errors should never pass silently），补日志；窗口尺寸魔法数字提取为具名常量。
- `settings_store.py`：`except BaseException` 收窄为 `except Exception`（仍原样 re-raise）。
- `report_exporter.py`：`normalize_format` 前置引用后定义的异常类，调整定义顺序提升可读性。
- `generator.py`：`"any"` 魔法字符串改用 `BLANK_POSITION_ANY` 常量；`generate_questions` 内嵌套函数提取为模块级函数（Flat is better than nested）。
- `models.py` / `repositories.py`：`"last"` 魔法字符串改用 `BLANK_POSITION_LAST` 常量。
- `config.py`：`operand_count not in (A, B, *range(...))` 改为显式范围比较，避免每次构造临时元组。

### Batch 2 — Python PEP8 行宽（src）
- 修复 `src/` 下 65 处 E501：函数签名垂直悬挂缩进、长表达式用括号拆行。
- 涉及：`generator.py`(35)、`bridge/api.py`(8)、`practice_service.py`(6)、`report_service.py`(3)、`repositories.py`(3)、`window.py`(3)、`config.py`(2)、`database.py`(2)、`grading.py`(1)、`settings_store.py`(1)、`stats_service.py`(1)。

### Batch 3 — Python PEP8 行宽（tests）+ 反斜杠续行
- 修复 `tests/` 下 40 处 E501。
- 两处 `== \` 反斜杠续行改为括号包裹。
- `test_generator.py` 重复的 parametrize 装饰器提取为模块级常量（DRY）。

### Batch 4 — JS 正确性与安全（Major）
- `api.js`：`bridgePromise` reject 后永久缓存失败状态，改为失败时重置以便重试。
- `history.js`：`aria-label` 拼接未转义，补 `esc()` 防属性注入/XSS；清历史并发守卫 + 统一 `CONFIRM_MS` 常量。
- `result.js`：`gotoCorrectionPage()` 中 `data` 为 null 时的空指针防护。
- `settings.js`：`init()` 增加幂等守卫，避免重复绑定事件。

### Batch 5 — JS ES6+ 标准与一致性（Minor）
- `practice.js`：`let digits` → `const digits`。
- `state.js`：补全动态写入的顶层状态字段声明（practice/historyCache/wrongBookCache 等）。
- 21 处 `err && err.message ? ...` 简化为可选链 + 空值合并（`err?.message ?? ...`）。
- `mask.js` / `toast.js` 等回调统一风格；`history.js` 尾随逗号一致性。

### 执行期校准（基于逐文件复核）
- `settings_store.py` 的 `except BaseException` 保留：它是「清理临时文件后原样 re-raise」的正确写法，收窄为 `Exception` 反而会在 `KeyboardInterrupt`/`SystemExit` 时泄漏 tmp 文件。
- `generator.py` 的嵌套 `generator` 保留：8 行局部闭包直接复用三个局部生成器函数，提取到模块级反而要新增参数/`partial`，可读性更低；仅在 Batch 2 修其行宽。
- `config.py` 的 `operand_count not in (A, B, *range(...))` 保留：语义直白，改写为范围比较无实质收益。

### 收尾验证
- `pycodestyle --max-line-length=79 src tests` = 0
- `pytest -q`（覆盖率 ≥ 85% 门槛）
- JS 语法检查（`node --check`）+ `js_tests` Jest 套件
- 每批提交后跑对应门禁，全绿后继续下一批。

## 执行结果（全部完成）

| 批次 | 提交 | 内容 |
|---|---|---|
| Batch 1 | `7d5a332` | Python 正确性与 PEP20（6 文件 + 计划文档） |
| Batch 2 | `043ce34` | src E501 行宽（11 文件） |
| Batch 3 | `83a9fdf` | tests E501 行宽 + 反斜杠续行（7 文件） |
| Batch 4 | `dca4966` | JS 正确性与安全（4 文件） |
| Batch 5 | `1d81830` | JS ES2020 风格与状态字段声明（8 文件） |

最终门禁：`pycodestyle` 0 违规；`pytest` 215 passed / 覆盖率 89.39%（≥85%）；
全部 JS `node --check` 通过；Jest 11 suites / 67 tests 全绿。工作区干净。

补充说明：Batch 5 未采纳评审中的「字符串拼接全面改模板字面量」「回调统一箭头函数」
两项——前者在含双引号属性的 HTML 骨架中反而降低可读性，后者中 `wrongbook.js:146`
依赖动态 `this`，盲改会引入缺陷；其余 Minor 项（可选链、const、状态字段）均已落地。

## 非目标
- 不引入 ESLint / ruff 等新工具与配置（保持仓库零 lint 配置现状）。
- 不做大规模 DRY 模块抽取（如 cross-page 工具函数合并），仅做局部去重。
- 不改变任何对前端暴露的桥接返回结构与错误文案。
