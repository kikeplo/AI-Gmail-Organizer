$ErrorActionPreference = 'Stop'

Write-Host 'AI Gmail Organizer - Windows build' -ForegroundColor Cyan
Write-Host 'Preparing dependencies and bundled browser support...'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

# Prefer the currently active virtual environment when one exists.
$Python = $null
if ($env:VIRTUAL_ENV -and (Test-Path (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'))) {
    $Python = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = (Get-Command py).Source
}

if (-not $Python) {
    throw 'Python 3.11+ is required to build the application. Install Python, or activate your .venv, then run this script again.'
}

Write-Host "Using Python: $Python"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip.' }
& $Python -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw 'Failed to install project dependencies.' }
& $Python -m pip install 'pyinstaller>=6.22.3,<7'
if ($LASTEXITCODE -ne 0) { throw 'Failed to install PyInstaller.' }

# Keep the Chromium runtime inside the project so the PyInstaller spec can bundle it.
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $Root '.playwright')
$PlaywrightPath = Join-Path $Root '.playwright'
if (Test-Path $PlaywrightPath) {
    Remove-Item $PlaywrightPath -Recurse -Force
}
New-Item -ItemType Directory -Path $PlaywrightPath | Out-Null

& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Failed to prepare the bundled Chromium runtime.' }

Write-Host 'Building self-contained EXE...' -ForegroundColor Cyan
& $Python -m PyInstaller packaging\AI-Gmail-Organizer.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed. No valid EXE was produced.' }

$AppDir = Join-Path $Root 'dist\AI-Gmail-Organizer'
$Exe = Join-Path $AppDir 'AI-Gmail-Organizer.exe'
if (-not (Test-Path $AppDir)) { throw 'Build finished without producing dist\AI-Gmail-Organizer.' }
if (-not (Test-Path $Exe)) { throw 'Build finished without producing the packaged AI-Gmail-Organizer.exe.' }

Write-Host ''
Write-Host 'Build complete.' -ForegroundColor Green
Write-Host "Application folder: $AppDir"
Write-Host "EXE: $Exe"
Write-Host 'The packaged application includes the Python dependencies and bundled Chromium runtime.'
