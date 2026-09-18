# PyInstaller configuration for a portable Windows application folder.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# This spec lives in <project>/packaging, so the project root is one level up.
project_root = Path(SPECPATH).resolve().parent
if project_root.name.casefold() == "packaging":
    project_root = project_root.parent

# Build an explicit list of every application module without importing the
# application's package while the spec itself is being evaluated.
app_root = project_root / "app"
app_modules = []
if app_root.is_dir():
    for source in sorted(app_root.rglob("*.py")):
        relative = source.relative_to(project_root).with_suffix("")
        app_modules.append(".".join(relative.parts))

hiddenimports = [
    "win32api", "win32con", "win32gui", "win32process",
    "comtypes", "comtypes.client",
]
hiddenimports += app_modules

for package in (
    "pyautogui", "pyscreeze", "pytweening", "pymsgbox",
    "mouseinfo", "PIL", "pywinauto", "playwright",
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

datas = []

# Keep a source copy of the application package in the onedir bundle as a
# runtime fallback. The runtime hook adds sys._MEIPASS to sys.path before main
# starts, so imports such as app.windows.action_router always have a filesystem
# fallback even if a future PyInstaller/modulegraph change affects PYZ.
if app_root.is_dir():
    datas.append((str(app_root), "app"))

for package in ("pyautogui", "pyscreeze", "PIL", "pywinauto", "playwright"):
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

playwright_local = project_root / ".playwright"
if playwright_local.exists():
    datas.append((str(playwright_local), "playwright"))

icon = project_root / "assets" / "ai_gmail_organizer.svg"
if icon.exists():
    datas.append((str(icon), "assets"))

runtime_hook = project_root / "packaging" / "runtime_hooks" / "playwright_portable.py"
path_runtime_hook = project_root / "packaging" / "runtime_hook.py"

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(runtime_hook), str(path_runtime_hook)],
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
    name="AI-Gmail-Organizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="AI-Gmail-Organizer")
