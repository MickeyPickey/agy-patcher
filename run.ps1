# Antigravity Minimal Patcher - one-command launch on Windows
# Usage:
#   irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex

& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    # Specify your repository in 'username/repo' format
    $Repo = if ($env:AGY_REPO) { $env:AGY_REPO } else { "MickeyPickey/agy-patcher" }
    $Branch = if ($env:AGY_BRANCH) { $env:AGY_BRANCH } else { "main" }
    $CacheBust = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

    # Prefer running patcher.py directly via Python 3 when available
    $pyCmd = $null
    if (-not $env:AGY_USE_EXE) {
        foreach ($candidate in @("python", "py")) {
            try {
                if (Get-Command $candidate -ErrorAction SilentlyContinue) {
                    $check = & $candidate -c "import sys; print('OK' if sys.version_info >= (3, 7) else 'OLD')" 2>$null
                    if ($LASTEXITCODE -eq 0 -and "$check".Trim() -eq "OK") {
                        $pyCmd = $candidate
                        break
                    }
                }
            } catch {}
        }
    }

    if ($pyCmd) {
        $pyUrl = "https://raw.githubusercontent.com/$Repo/$Branch/patcher.py?cb=$CacheBust"
        $pyDest = Join-Path $env:TEMP "patcher.py"
        Write-Host "Downloading Antigravity Patcher (patcher.py) from $Repo..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyDest -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
        & $pyCmd $pyDest @args
        return
    }

    $tag = if ($env:AGY_VERSION) { $env:AGY_VERSION } else { "latest" }
    $url = if ($tag -eq "latest") {
        "https://github.com/$Repo/releases/latest/download/antigravity-patcher.exe"
    } else {
        "https://github.com/$Repo/releases/download/$tag/antigravity-patcher.exe"
    }
    $dest = Join-Path $env:TEMP "antigravity-patcher.exe"

    Write-Host "Downloading Antigravity Patcher (antigravity-patcher.exe) from $Repo ($tag)..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
    } catch {
        Write-Host "Failed to download compiled EXE, falling back to Python..." -ForegroundColor Yellow
        $pyUrl = "https://raw.githubusercontent.com/$Repo/$Branch/patcher.py?cb=$CacheBust"
        $pyDest = Join-Path $env:TEMP "patcher.py"
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyDest -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
        python $pyDest @args
        return
    }

    & $dest @args
}
