# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件

使用方法:
    pyinstaller wechat-fabu.spec

打包后输出目录: dist/wechat-fabu/
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))

# 额外二进制文件（UIAutomation 依赖）
site_packages = Path(sys.prefix) / "Lib" / "site-packages"
uiautomation_bin = site_packages / "uiautomation" / "bin"
binaries = []
if uiautomation_bin.exists():
    for dll_name in ("UIAutomationClient_VC140_X64.dll", "UIAutomationClient_VC140_X86.dll"):
        dll_path = uiautomation_bin / dll_name
        if dll_path.exists():
            binaries.append((str(dll_path), "."))
    os.environ["PATH"] = f"{uiautomation_bin}{os.pathsep}" + os.environ.get("PATH", "")

# 收集数据文件
datas = [
    # 配置文件
    (os.path.join(PROJECT_ROOT, 'config.yaml'), '.'),
    (os.path.join(PROJECT_ROOT, 'selectors.yaml'), '.'),
    # 数据目录结构（空目录）
    (os.path.join(PROJECT_ROOT, 'data', 'cache'), 'data/cache'),
    (os.path.join(PROJECT_ROOT, 'data', 'logs'), 'data/logs'),
    (os.path.join(PROJECT_ROOT, 'data', 'receipts'), 'data/receipts'),
    (os.path.join(PROJECT_ROOT, 'data', 'screenshots'), 'data/screenshots'),
    (os.path.join(PROJECT_ROOT, 'data', 'shared'), 'data/shared'),
    # 模板图片（用于图像识别）
    (os.path.join(PROJECT_ROOT, 'data', 'templates'), 'data/templates'),
]

# 过滤掉不存在的目录
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# 隐藏导入（PyInstaller 可能无法自动检测的模块）
hiddenimports = [
    # PySide6 相关
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    # UI自动化
    'uiautomation',
    'pywinauto',
    'pywinauto.controls',
    'pywinauto.controls.uiawrapper',
    # pywin32
    'win32api',
    'win32con',
    'win32gui',
    'win32clipboard',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    # 其他
    'PIL',
    'PIL.Image',
    'cv2',
    'openpyxl',
    'apscheduler',
    'apscheduler.schedulers.background',
    'apscheduler.triggers.interval',
    'apscheduler.triggers.cron',
    'apscheduler.triggers.date',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'yaml',
    'cryptography',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    # matplotlib (用于统计图表)
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.figure',
]

# 排除不需要的模块（减小体积）
excludes = [
    'tkinter',
    'numpy.testing',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
]

# Analysis
a = Analysis(
    ['run.py'],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 过滤掉测试文件
a.pure = [x for x in a.pure if not any(
    pattern in x[0] for pattern in ['test_', 'tests.', 'debug_', 'detect_']
)]

# PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='微信自动发布工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'icon.ico'),
    contents_directory=".",
)

# COLLECT
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wechat-fabu',
)
