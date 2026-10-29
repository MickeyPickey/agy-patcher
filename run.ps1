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

    $url = "https://raw.githubusercontent.com/$Repo/$Branch/antigravity-patcher.exe"
    $dest = Join-Path $env:TEMP "antigravity-patcher.exe"

    Write-Host "Downloading Antigravity Patcher from $Repo..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    } catch {
        Write-Host "Failed to download compiled EXE, falling back to Python..." -ForegroundColor Yellow
        $pyUrl = "https://raw.githubusercontent.com/$Repo/$Branch/patcher.py"
        $pyDest = Join-Path $env:TEMP "patcher.py"
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyDest -UseBasicParsing
        python $pyDest
        return
    }

    & $dest
}
