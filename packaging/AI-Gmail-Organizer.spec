# PyInstaller configuration for the Windows desktop application.
# Third-party automation packages are bundled so the end-user does not need Python or pip.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path(SPECPATH).resolve().parent

hiddenimports = [
    'win32api', 'win32con', 'win32gui', 'win32process',
    'comtypes', 'comtypes.client',
]
hiddenimports += collect_submodules('pywinauto')
hiddenimports += collect_submodules('playwright')

datas = []
datas += collect_data_files('pywinauto')
datas += collect_data_files('playwright')

# When the build script installs Chromium with PLAYWRIGHT_BROWSERS_PATH=0,
# collect Playwright's bundled browser runtime into the EXE distribution.
playwright_local = project_root / '.playwright'
if playwright_local.exists():
    datas.append((str(playwright_local), 'playwright'))


a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
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
