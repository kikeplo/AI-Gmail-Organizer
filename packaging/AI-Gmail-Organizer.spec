# PyInstaller configuration for the Windows desktop application.
# User-specific credentials and configuration are intentionally not bundled.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent

hiddenimports = [
    'win32api', 'win32con', 'win32gui', 'win32process',
    'comtypes', 'comtypes.client',
]
hiddenimports += collect_submodules('pywinauto')
hiddenimports += collect_submodules('playwright')


a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    name='AI-Gmail-Organizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
