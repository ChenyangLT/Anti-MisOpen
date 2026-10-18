# Build script: PyInstaller 5.13.2 one-file build (Win7 compatible).
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv38\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv38\Scripts\python.exe - create the Python 3.8 venv and install pyside2/psutil/pyinstaller first."
}

Write-Host "==> Cleaning old artifacts" -ForegroundColor Cyan
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Force dist\Anti-MisOpen.exe -ErrorAction SilentlyContinue

Write-Host "==> Running PyInstaller (about 1-3 minutes)" -ForegroundColor Cyan
& $python -m PyInstaller --clean --noconfirm anti-misopen.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $root "dist\Anti-MisOpen.exe"
if (-not (Test-Path $exe)) {
    throw "Build finished but dist\Anti-MisOpen.exe is missing."
}

$item = Get-Item $exe
Write-Host ("==> Done: {0}  ({1:N1} MB)" -f $item.FullName, ($item.Length / 1MB)) -ForegroundColor Green
