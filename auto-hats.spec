# -*- mode: python ; coding: utf-8 -*-
#
# Compilación "onedir" + sin UPX + con recurso de versión.
# Esto reduce drásticamente los falsos positivos de antivirus
# (Trojan:Win32/Wacatac.B!ml y similares) frente al modo onefile.

a = Analysis(
    ['auto-hats.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.'), ('auto-hats.png', '.')],
    hiddenimports=[],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name='auto-hats',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
    version='packaging/version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='auto-hats',
)
