# PyInstaller configuration for a self-contained Windows application folder.
# The EXE is the launcher; browser and automation runtimes live beside it.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path(SPECPATH).resolve().parent

hiddenimports = [
    'win32api', 'win32con', 'win32gui', 'win32process',
    'comtypes', 'comtypes.client',
]
for package in ('pyautogui', 'pyscreeze', 'pytweening', 'pymsgbox', 'mouseinfo', 'PIL', 'pywinauto', 'playwright'):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

datas = []
for package in ('pyautogui', 'pyscreeze', 'PIL', 'pywinauto', 'playwright'):
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

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
    runtime_hooks=[str(project_root / 'packaging' / 'runtime_hook.py')],
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='AI-Gmail-Organizer',
)
