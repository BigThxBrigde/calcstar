# CalcStar packaging script: builds the app via PyInstaller.
# Usage:
#   .\build.ps1            # onedir (default): dist\CalcStar\CalcStar.exe
#   .\build.ps1 -Mode onefile  # single-file: dist\CalcStar.exe

param(
    [ValidateSet("onedir", "onefile")]
    [string]$Mode = "onedir"
)

$ErrorActionPreference = 'Stop'

$venvPython = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "venv not found. Run first: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e .[dev]"
    exit 1
}

# Ensure pyinstaller is installed (installs dev extras if missing)
& $venvPython -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pyinstaller missing, installing dev extras..."
    & $venvPython -m pip install -e .[dev]
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }
}

# Pass the pack mode to CalcStar.spec via env var (default onedir)
$env:CALCSTAR_PACK_MODE = $Mode

# Remove the other mode's stale artifact to avoid confusion
if ($Mode -eq "onedir" -and (Test-Path "dist\CalcStar.exe")) {
    Remove-Item "dist\CalcStar.exe" -Force
}
if ($Mode -eq "onefile" -and (Test-Path "dist\CalcStar")) {
    Remove-Item "dist\CalcStar" -Recurse -Force
}

Write-Host "Building CalcStar ($Mode) ..."
& $venvPython -m PyInstaller CalcStar.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed"; exit 1 }

if ($Mode -eq "onedir") { $exe = "dist\CalcStar\CalcStar.exe" } else { $exe = "dist\CalcStar.exe" }
if (Test-Path $exe) {
    Write-Host "Build OK ($Mode): $((Resolve-Path $exe).Path)"
} else {
    Write-Error "Build finished but $exe not found"
    exit 1
}
