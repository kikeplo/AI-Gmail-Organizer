$ErrorActionPreference = 'Stop'

Write-Host 'AI Gmail Organizer - Portable Windows build' -ForegroundColor Cyan
Write-Host 'The result is a folder containing the EXE plus browser/automation runtimes.'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$InCI = $env:GITHUB_ACTIONS -eq 'true'

$Python = $null
if ($env:VIRTUAL_ENV -and (Test-Path (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'))) {
    $Python = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = (Get-Command py).Source
}

if (-not $Python) {
    throw 'Python 3.11+ is required only on the developer build machine. Activate your .venv or install Python, then run this script again.'
}

Write-Host "Using Python: $Python"
$PlaywrightPath = Join-Path $Root '.playwright'
$env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightPath

if (-not $InCI) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip.' }
    & $Python -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install project dependencies.' }
    & $Python -m pip install 'pyinstaller>=6.22.3,<7'
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install PyInstaller.' }

    if (Test-Path $PlaywrightPath) { Remove-Item $PlaywrightPath -Recurse -Force }
    New-Item -ItemType Directory -Path $PlaywrightPath | Out-Null
    Write-Host 'Preparing Chromium...'
    & $Python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Failed to prepare Chromium.' }
} else {
    if (-not (Test-Path $PlaywrightPath)) { throw "CI Playwright runtime is missing: $PlaywrightPath" }
    Write-Host 'CI mode: reusing preinstalled Python dependencies and Playwright runtime.'
}

Write-Host 'Validating application Python sources...' -ForegroundColor Cyan
& $Python -c "from pathlib import Path; import ast; files=list(Path('app').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print(f'Validated {len(files)} application Python files.')"
if ($LASTEXITCODE -ne 0) { throw 'Application source syntax validation failed.' }

Write-Host 'Building portable application folder...' -ForegroundColor Cyan
& $Python -m PyInstaller packaging\AI-Gmail-Organizer.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$AppDir = Join-Path $Root 'dist\AI-Gmail-Organizer'
$Exe = Join-Path $AppDir 'AI-Gmail-Organizer.exe'
$BrowserDir = Join-Path $AppDir 'playwright'

if (-not (Test-Path $AppDir)) { throw "Missing application folder: $AppDir" }
if (-not (Test-Path $Exe)) { throw "Missing launcher: $Exe" }

if (Test-Path $BrowserDir) { Remove-Item $BrowserDir -Recurse -Force }
New-Item -ItemType Directory -Path $BrowserDir | Out-Null
Copy-Item -Path (Join-Path $PlaywrightPath '*') -Destination $BrowserDir -Recurse -Force

$Chromium = Get-ChildItem -Path $BrowserDir -Recurse -Filter 'chrome.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Chromium) { throw 'No Chromium chrome.exe was found in the packaged browser directory.' }

Write-Host ''
Write-Host 'Portable build verified.' -ForegroundColor Green
Write-Host "Folder: $AppDir"
Write-Host "Launcher: $Exe"
Write-Host "Chromium: $($Chromium.FullName)"
Write-Host ''
Write-Host 'Distribute the complete AI-Gmail-Organizer folder.'
Write-Host 'The recipient should launch AI-Gmail-Organizer.exe inside that folder.'
