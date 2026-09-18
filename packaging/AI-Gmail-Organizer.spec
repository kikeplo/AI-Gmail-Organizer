# PyInstaller configuration for a portable Windows application folder.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# This spec lives in <project>/packaging, so the project root is one level up.
project_root = Path(SPECPATH).resolve().parent
if project_root.name.casefold() == 'packaging':
    project_root = project_root.parent

hiddenimports = [
    'win32api', 'win32con', 'win32gui', 'win32process', 'comtypes', 'comtypes.client',
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
icon = project_root / 'assets' / 'ai_gmail_organizer.svg'
if icon.exists():
    datas.append((str(icon), 'assets'))
runtime_hook = project_root / 'packaging' / 'runtime_hooks' / 'playwright_portable.py'

# Keep the application's own Python modules as ordinary files rather than
# embedding them in PYZ. This makes imports such as app.windows.action_router
# resolve through the normal frozen filesystem importer in the onedir build.
a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(runtime_hook)],
    excludes=[],
    noarchive=True,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AI-Gmail-Organizer', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='AI-Gmail-Organizer')
