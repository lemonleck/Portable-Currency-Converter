# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\DLLs\\tcl86t.dll', '.'), ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\DLLs\\tk86t.dll', '.')],
    datas=[('assets', 'assets'), ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\tcl\\tcl8.6', '_tcl_data'), ('C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\tcl\\tk8.6', '_tk_data')],
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
