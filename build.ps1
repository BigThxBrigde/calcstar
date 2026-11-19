# CalcStar packaging script: builds the app via PyInstaller.
# Usage:
#   .\build.ps1                  # onedir (default): dist\CalcStar\CalcStar.exe
#   .\build.ps1 -Mode onefile    # single-file: dist\CalcStar.exe
#   .\build.ps1 -Pack            # onedir + NSIS: dist\CalcStar-<version>-Setup.exe
#   .\build.ps1 -SkipTests       # skip pytest/Jest gates before packaging

param(
    [ValidateSet("onedir", "onefile")]
    [string]$Mode = "onedir",
    [switch]$Pack,
    [string]$NsisPath = "",
    [string]$NsisUrl = "",
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'

if ($Pack -and $Mode -ne "onedir") {
    Write-Error "-Pack only works with -Mode onedir (NSIS packages the dist\CalcStar directory)."
    exit 1
}

$venvDir = ".venv"
$venvPython = "$venvDir\Scripts\python.exe"
$venvCreated = $false

if (-not (Test-Path $venvPython)) {
    Write-Host "venv not found; creating $venvDir ..."
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        & $pythonCmd.Source -m venv $venvDir
    } else {
        $pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
        if (-not $pyCmd) {
            Write-Error "Python not found. Install Python >= 3.11 first."
            exit 1
        }
        & $pyCmd.Source -3 -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Error "Failed to create $venvDir (Python >= 3.11 required)."
        exit 1
    }
    $venvCreated = $true
}

# Install into the project venv only; never into the base/global environment
$needInstall = $venvCreated
if (-not $needInstall) {
    & $venvPython -m pip show pyinstaller *> $null
    $needInstall = ($LASTEXITCODE -ne 0)
}
if ($needInstall) {
    Write-Host "Installing project and dev dependencies into $venvDir ..."
    & $venvPython -m pip install -e .[dev]
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }
}

# Test gates: pytest for the backend, Jest for the web frontend.
if (-not $SkipTests) {
    Write-Host "Running Python tests (pytest) ..."
    & $venvPython -m pytest
    if ($LASTEXITCODE -ne 0) { Write-Error "pytest failed"; exit 1 }

    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npmCmd) {
        Write-Error "npm not found. Install Node.js to run the Jest tests (or pass -SkipTests)."
        exit 1
    }
    $npm = $npmCmd.Source

    $jsTestDir = Join-Path (Get-Location).Path "js_tests"
    if (-not (Test-Path (Join-Path $jsTestDir "package.json"))) {
        Write-Error "JS test project not found: $jsTestDir\package.json"
        exit 1
    }
    if (-not (Test-Path (Join-Path $jsTestDir "node_modules\.bin\jest.cmd"))) {
        Write-Host "Installing JS test dependencies (npm ci) ..."
        & $npm --prefix $jsTestDir ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Write-Error "npm ci failed"; exit 1 }
    }

    Write-Host "Running JavaScript tests (Jest) ..."
    & $npm --prefix $jsTestDir test
    if ($LASTEXITCODE -ne 0) { Write-Error "Jest failed"; exit 1 }
} else {
    Write-Host "Skipping pytest/Jest gates (-SkipTests)."
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

function Find-Makensis {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (Test-Path $ExplicitPath) { return $ExplicitPath }
        return $null
    }

    # 优先使用项目根目录 .nsis\ 下自动下载的编译器（压缩包内还有一层版本目录）
    if (Test-Path ".nsis") {
        $local = Get-ChildItem ".nsis" -Filter makensis.exe -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($local) { return $local }
    }

    $cmd = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

if ($Pack) {
    if (-not (Test-Path "dist\CalcStar\lib")) {
        Write-Error "dist\CalcStar\lib not found. Check that PyInstaller >= 6 was used and CalcStar.spec sets contents_directory."
        exit 1
    }

    $makensis = Find-Makensis -ExplicitPath $NsisPath
    if ([string]::IsNullOrWhiteSpace($makensis)) {
        if (-not [string]::IsNullOrWhiteSpace($NsisPath)) {
            Write-Error "makensis.exe not found at -NsisPath: $NsisPath"
            exit 1
        }

        $nsisVersion = "3.08"
        $downloadUrl = $NsisUrl
        if ([string]::IsNullOrWhiteSpace($downloadUrl)) {
            # NSIS 便携包（zlib 许可，无商业授权限制），经 ghfast.top 加速
            $downloadUrl = "https://ghfast.top/https://github.com/tauri-apps/binary-releases/releases/download/nsis-3/nsis-3.zip"
        }
        $zipPath = Join-Path $env:TEMP "calcstar-nsis-$nsisVersion.zip"
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

        Write-Host "makensis.exe not found; downloading NSIS $nsisVersion from $downloadUrl ..."
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 600
        if (-not (Test-Path $zipPath)) {
            Write-Error "Download failed: $downloadUrl"
            exit 1
        }
        if ([string]::IsNullOrWhiteSpace($NsisUrl)) {
            $expectedHash = "1BB9FC85EE5B220D3869325DBB9D191DFE6537070F641C30FBB275C97051FD0C"
            $actualHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
            if ($actualHash -ne $expectedHash) {
                Remove-Item $zipPath -Force
                Write-Error "NSIS zip SHA256 mismatch: $actualHash"
                exit 1
            }
        }

        Write-Host "Extracting NSIS to .nsis ..."
        if (Test-Path ".nsis") { Remove-Item ".nsis" -Recurse -Force }
        Expand-Archive -Path $zipPath -DestinationPath ".nsis" -Force
        Remove-Item $zipPath -Force
        $makensis = Get-ChildItem ".nsis" -Filter makensis.exe -Recurse |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if ([string]::IsNullOrWhiteSpace($makensis) -or -not (Test-Path $makensis)) {
        Write-Error "makensis.exe not found. Pass -NsisPath <path>."
        exit 1
    }

    $versionMatch = Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"([^"]+)"'
    if (-not $versionMatch) { Write-Error "Cannot read version from pyproject.toml"; exit 1 }
    $version = $versionMatch.Matches[0].Groups[1].Value

    $root = (Get-Location).Path
    $setup = "$root\dist\CalcStar-$version-Setup.exe"
    if (Test-Path $setup) { Remove-Item $setup -Force }

    Write-Host "Packing installer with NSIS ..."
    & $makensis "/DVERSION=$version" "$root\installer\CalcStar.nsi"
    if ($LASTEXITCODE -ne 0) { Write-Error "NSIS compile failed"; exit 1 }
    if (-not (Test-Path $setup)) { Write-Error "Installer not found: $setup"; exit 1 }
    Write-Host "Installer OK: $setup"
}
