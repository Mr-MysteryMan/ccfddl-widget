# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files

# Conda keeps this dependency outside DLLs; regular Python does not need it.
expat_library = Path(sys.base_prefix) / 'Library' / 'bin' / 'libexpat.dll'
extra_binaries = [(str(expat_library), '.')] if expat_library.is_file() else []
a = Analysis(
    [str(Path(SPECPATH) / 'src' / 'main.py')],
    pathex=[str(Path(SPECPATH) / 'src')],
    binaries=extra_binaries,
    datas=[(str(Path(SPECPATH) / 'conferences.yaml'), '.')] + collect_data_files('tzdata'),
    hiddenimports=['tzdata'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt 6 uses the Windows system ICU API (for example, ucnv_open).
# Conda's ICU 58 exports versioned symbols (ucnv_open_58) instead. If bundled,
# it shadows the system DLL and QtWidgets fails to import at application start.
if sys.platform == 'win32':
    a.binaries = [
        entry for entry in a.binaries
        if not (
            Path(entry[0]).name.lower().startswith(('icuuc', 'icuin', 'icudt'))
            and Path(entry[0]).suffix.lower() == '.dll'
        )
    ]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CCFDDLWidget',
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
)
