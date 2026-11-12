# CalcStar packaging script: builds a single-file, windowless exe via PyInstaller.
# Usage: .\build.ps1

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

Write-Host "Building CalcStar.exe ..."
& $venvPython -m PyInstaller CalcStar.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed"; exit 1 }

$exe = "dist\CalcStar.exe"
if (Test-Path $exe) {
    Write-Host "Build OK: $((Resolve-Path $exe).Path)"
} else {
    Write-Error "Build finished but $exe not found"
    exit 1
}
