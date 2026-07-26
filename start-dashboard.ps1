[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBrowser,
    [int]$Port = 8787
)

$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendDir = Join-Path $RepoRoot 'backend'
$StaticDir = Join-Path $BackendDir 'src\claude_codex_monitor\static'
$DistDir = Join-Path $FrontendDir 'dist'

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-CommandOnPath {
    param([string]$Name, [string]$InstallHint)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Error "'$Name' was not found on PATH. $InstallHint"
        exit 1
    }
    return $cmd
}

# ---------------------------------------------------------------------------
# 1. Validate toolchain. pixi is the only tool this script invokes directly;
#    pixi.toml tasks internally shell out to `uv` (Python) and `pnpm`
#    (frontend), so both must also be reachable on PATH for pixi to use them.
# ---------------------------------------------------------------------------
Write-Step 'Checking required tools on PATH (pixi, uv, pnpm)...'
Assert-CommandOnPath -Name 'pixi' -InstallHint 'Install from https://pixi.sh and re-open your shell.' | Out-Null
Assert-CommandOnPath -Name 'uv' -InstallHint 'Install from https://docs.astral.sh/uv/ and re-open your shell.' | Out-Null
Assert-CommandOnPath -Name 'pnpm' -InstallHint 'Install Node.js and enable pnpm (corepack enable pnpm).' | Out-Null
Write-Host 'All required tools found.' -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Sync backend Python environment (pixi task wraps `uv sync`).
# ---------------------------------------------------------------------------
Write-Step 'Syncing backend Python environment (pixi run sync)...'
& pixi run sync
if ($LASTEXITCODE -ne 0) { Write-Error 'Backend dependency sync failed.'; exit 1 }

# ---------------------------------------------------------------------------
# 3. Build the frontend if missing, stale, or -Rebuild was passed.
# ---------------------------------------------------------------------------
function Test-FrontendStale {
    if ($Rebuild) { return $true }
    if (-not (Test-Path $DistDir)) { return $true }
    if (-not (Test-Path $StaticDir) -or (Get-ChildItem $StaticDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.gitkeep' } | Measure-Object).Count -eq 0) {
        return $true
    }
    $newestSource = Get-ChildItem -Path (Join-Path $FrontendDir 'src'), (Join-Path $FrontendDir 'index.html') -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    $newestBuilt = Get-ChildItem -Path $DistDir -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if (-not $newestBuilt) { return $true }
    if ($newestSource -and $newestSource.LastWriteTimeUtc -gt $newestBuilt.LastWriteTimeUtc) { return $true }
    return $false
}

if (Test-FrontendStale) {
    Write-Step 'Installing frontend dependencies (pixi run install-frontend)...'
    & pixi run install-frontend
    if ($LASTEXITCODE -ne 0) { Write-Error 'Frontend dependency install failed.'; exit 1 }

    Write-Step 'Building frontend (pixi run build-frontend)...'
    & pixi run build-frontend
    if ($LASTEXITCODE -ne 0) { Write-Error 'Frontend build failed.'; exit 1 }

    Write-Step 'Copying built frontend into backend static directory...'
    if (Test-Path $StaticDir) {
        Get-ChildItem $StaticDir -Force | Where-Object { $_.Name -ne '.gitkeep' } | Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $StaticDir -Force | Out-Null
    }
    Copy-Item -Path (Join-Path $DistDir '*') -Destination $StaticDir -Recurse -Force
    if (-not (Test-Path (Join-Path $StaticDir '.gitkeep'))) {
        New-Item -ItemType File -Path (Join-Path $StaticDir '.gitkeep') | Out-Null
    }
    Write-Host 'Frontend build complete.' -ForegroundColor Green
} else {
    Write-Host 'Frontend build is up to date; skipping (use -Rebuild to force).' -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 4. Start the backend (serves API + built frontend on the same port).
# ---------------------------------------------------------------------------
Write-Step "Starting backend on http://127.0.0.1:$Port ..."
# Always go through `pixi run ...` (never call uv/pnpm binaries directly) -
# the `serve` task wraps `uv run uvicorn ... --host 127.0.0.1 --port $CCM_PORT`.
$env:CCM_PORT = "$Port"
$backendProcess = Start-Process -FilePath 'pixi' -ArgumentList @('run', 'serve') `
    -WorkingDirectory $RepoRoot -PassThru -NoNewWindow

$cleanupDone = $false
function Stop-Backend {
    if ($cleanupDone) { return }
    $script:cleanupDone = $true
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Step 'Stopping backend process...'
        try {
            Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # Process may have already exited; nothing more to do.
        }
    }
}

try {
    # ---------------------------------------------------------------------
    # 5. Poll /api/health until 200 (or the process dies / times out).
    # ---------------------------------------------------------------------
    Write-Step 'Waiting for backend health check...'
    $healthUrl = "http://127.0.0.1:$Port/api/health"
    $deadline = (Get-Date).AddSeconds(30)
    $healthy = $false
    while ((Get-Date) -lt $deadline) {
        if ($backendProcess.HasExited) {
            Write-Error "Backend process exited early (exit code $($backendProcess.ExitCode)). Check output above."
            exit 1
        }
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $healthy = $true; break }
        } catch {
            # Not ready yet; retry until deadline.
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $healthy) {
        Write-Error "Backend did not become healthy within 30 seconds at $healthUrl."
        Stop-Backend
        exit 1
    }
    Write-Host "Backend is healthy at $healthUrl" -ForegroundColor Green

    # -----------------------------------------------------------------
    # 6. Open the default browser (unless -NoBrowser).
    # -----------------------------------------------------------------
    $dashboardUrl = "http://127.0.0.1:$Port"
    if (-not $NoBrowser) {
        Write-Step "Opening $dashboardUrl in the default browser..."
        Start-Process $dashboardUrl
    } else {
        Write-Host "Dashboard is running at $dashboardUrl (browser not opened, -NoBrowser set)." -ForegroundColor Green
    }

    Write-Host ''
    Write-Host "Claude & Codex Usage Monitor is running at $dashboardUrl" -ForegroundColor Green
    Write-Host 'Press Ctrl+C to stop.' -ForegroundColor Yellow

    # -----------------------------------------------------------------
    # 7. Wait for the backend process; ensure clean shutdown on Ctrl+C.
    # -----------------------------------------------------------------
    Wait-Process -Id $backendProcess.Id
}
finally {
    Stop-Backend
}
