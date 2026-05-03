# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


PYTHON_ROOT = Path(sys.base_prefix)
TK_DLL_DIR = PYTHON_ROOT / 'DLLs'
TCL_DIR = PYTHON_ROOT / 'tcl'

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[(str(TK_DLL_DIR / 'tcl86t.dll'), '.'), (str(TK_DLL_DIR / 'tk86t.dll'), '.')],
    datas=[('assets', 'assets'), (str(TCL_DIR / 'tcl8.6'), '_tcl_data'), (str(TCL_DIR / 'tk8.6'), '_tk_data')],
    hiddenimports=[],
    hookspath=['build_hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='汇率转换工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app_icon.ico'],
)
