# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/Anti-Gravitasia/sayan-clicker/main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:/Anti-Gravitasia/sayan-clicker/assets/sprites', 'assets/sprites'), ('D:/Anti-Gravitasia/sayan-clicker/assets/sounds', 'assets/sounds'), ('D:/Anti-Gravitasia/sayan-clicker/assets/sayan_icon.ico', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'matplotlib', 'playwright', 'pytest'],
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
    name='SayanClicker',
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
    icon=['D:/Anti-Gravitasia/sayan-clicker/assets/sayan_icon.ico'],
)
