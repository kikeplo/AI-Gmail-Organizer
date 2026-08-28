$ErrorActionPreference = 'Stop'

Write-Host 'AI Gmail Organizer - Windows build' -ForegroundColor Cyan
Write-Host 'Installing all Python dependencies and preparing bundled browser support...'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python 3.11+ is required to build the application. Install Python, then run this script again.'
}

$Python = (Get-Command py).Source
& $Python -3.11 -m pip install --upgrade pip
& $Python -3.11 -m pip install -e .
& $Python -3.11 -m pip install 'pyinstaller>=6,<7'

# Keep the Chromium runtime inside the project so the PyInstaller spec can bundle it.
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $Root '.playwright')
if (Test-Path (Join-Path $Root '.playwright')) {
    Remove-Item (Join-Path $Root '.playwright') -Recurse -Force
}
New-Item -ItemType Directory -Path (Join-Path $Root '.playwright') | Out-Null

& $Python -3.11 -m playwright install chromium

Write-Host 'Building self-contained EXE...' -ForegroundColor Cyan
& $Python -3.11 -m PyInstaller packaging\AI-Gmail-Organizer.spec --clean --noconfirm

Write-Host ''
Write-Host 'Build complete. The EXE is in dist\AI-Gmail-Organizer.exe' -ForegroundColor Green
Write-Host 'The packaged application includes the Python dependencies and bundled Chromium runtime.'
