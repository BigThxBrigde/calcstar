# -*- mode: python ; coding: utf-8 -*-
# CalcStar PyInstaller 打包配置：单文件、无控制台窗口。
# web/ 前端资源与 PyQtWebEngine 运行时随包内置；禁用 UPX 以避免压缩损坏 QtWebEngine。

import os
import glob

datas = []
for f in glob.glob(os.path.join("web", "**", "*"), recursive=True):
    if os.path.isfile(f):
        datas.append((f.replace("/", os.sep), os.path.dirname(f).replace("/", os.sep)))

# 应用图标随包内置（运行期窗口图标由 config.get_icon_path 定位）
datas.append((os.path.join("assets", "calcstar.ico"), "assets"))

a = Analysis(
    ["src/calcstar/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PyQt5.QtWebChannel",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebEngineWidgets",
        "calcstar",
        "calcstar.config",
        "calcstar.desktop",
        "calcstar.desktop.window",
        "calcstar.bridge",
        "calcstar.bridge.api",
        "calcstar.services",
        "calcstar.services.practice_service",
        "calcstar.services.stats_service",
        "calcstar.domain",
        "calcstar.domain.models",
        "calcstar.domain.generator",
        "calcstar.domain.grading",
        "calcstar.data",
        "calcstar.data.database",
        "calcstar.data.repositories",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CalcStar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用 UPX：压缩 QtWebEngine 的 DLL 会导致运行异常
    console=False,
    icon="assets/calcstar.ico",  # exe 文件图标（资源管理器/任务栏/快捷方式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
