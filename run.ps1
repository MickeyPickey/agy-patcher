# Antigravity Patcher - one-command remote installer & launcher on Windows
# Usage:
#   irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex

& {
    $ErrorActionPreference = 'Stop'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $Repo = if ($env:AGY_REPO) { $env:AGY_REPO } else { "MickeyPickey/agy-patcher" }
    $Branch = if ($env:AGY_BRANCH) { $env:AGY_BRANCH } else { "main" }

    $InstallDir = Join-Path $env:LOCALAPPDATA "agy-patcher"
    $InstalledExe = Join-Path $InstallDir "agy-patcher.exe"
    $InstalledCmd = Join-Path $InstallDir "agy-patcher.cmd"
    $InstalledPy  = Join-Path $InstallDir "patcher.py"
    $TempExe = Join-Path $env:TEMP "agy-patcher.exe"
    $TempPy  = Join-Path $env:TEMP "patcher.py"

    function Add-UserPath([string]$dir) {
        try {
            $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
            $parts = if ($userPath) { $userPath -split ";" } else { @() }
            if ($parts -notcontains $dir) {
                $newPath = if ($userPath) { "$userPath;$dir" } else { $dir }
                [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            }
            if (($env:PATH -split ";") -notcontains $dir) {
                $env:PATH = "$dir;$env:PATH"
            }
        } catch {}
    }

    function Download-FileWithProgress(
        [string]$Uri,
        [string]$Destination,
        [hashtable]$Headers = $null,
        [int]$TimeoutSeconds = 15,
        [string]$Activity = "Downloading"
    ) {
        $tempPath = "$Destination.tmp"
        $response = $null
        $stream = $null
        $fs = $null

        try {
            $req = [System.Net.HttpWebRequest]::Create($Uri)
            $req.Timeout = $TimeoutSeconds * 1000
            $req.ReadWriteTimeout = $TimeoutSeconds * 1000
            $req.UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) agy-patcher"
            $req.Headers.Add("Cache-Control", "no-cache")

            if ($Headers) {
                foreach ($k in $Headers.Keys) {
                    if ($k -eq "Accept") {
                        $req.Accept = $Headers[$k]
                    } else {
                        $req.Headers[$k] = $Headers[$k]
                    }
                }
            }

            $response = $req.GetResponse()
            $totalBytes = $response.ContentLength
            $stream = $response.GetResponseStream()

            if ([System.IO.File]::Exists($tempPath)) {
                [System.IO.File]::Delete($tempPath)
            }
            $fs = New-Object System.IO.FileStream($tempPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)

            $buffer = New-Object byte[] 65536
            $downloadedBytes = 0
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $lastUpdate = [DateTime]::MinValue

            while (($bytesRead = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $fs.Write($buffer, 0, $bytesRead)
                $downloadedBytes += $bytesRead

                $now = [DateTime]::UtcNow
                if (($now - $lastUpdate).TotalMilliseconds -ge 200 -or $downloadedBytes -eq $totalBytes) {
                    $lastUpdate = $now
                    $percent = if ($totalBytes -gt 0) { [math]::Min(100, [int](($downloadedBytes / $totalBytes) * 100)) } else { -1 }
                    $speedKBps = if ($sw.Elapsed.TotalSeconds -gt 0) { [math]::Round(($downloadedBytes / 1024) / $sw.Elapsed.TotalSeconds, 1) } else { 0 }
                    $downloadedMB = [math]::Round($downloadedBytes / 1MB, 2)
                    $totalMB = if ($totalBytes -gt 0) { [math]::Round($totalBytes / 1MB, 2) } else { "?" }

                    $status = "$downloadedMB MB / $totalMB MB ($speedKBps KB/s)"
                    if ($percent -ge 0) {
                        Write-Progress -Activity $Activity -Status $status -PercentComplete $percent
                    } else {
                        Write-Progress -Activity $Activity -Status $status
                    }
                }
            }

            $fs.Flush()
            $fs.Close()
            $fs = $null
            $stream.Close()
            $stream = $null
            $response.Close()
            $response = $null
            Write-Progress -Activity $Activity -Completed -Status "Completed"

            if ([System.IO.File]::Exists($Destination)) {
                [System.IO.File]::Delete($Destination)
            }
            [System.IO.File]::Move($tempPath, $Destination)
            return $true
        } catch {
            if ($fs) { $fs.Close(); $fs = $null }
            if ($stream) { $stream.Close(); $stream = $null }
            if ($response) { $response.Close(); $response = $null }
            Write-Progress -Activity $Activity -Completed -Status "Failed"
            if ([System.IO.File]::Exists($tempPath)) {
                try { [System.IO.File]::Delete($tempPath) } catch {}
            }
            return $false
        }
    }

    function Download-AgyExe([string]$TargetRepo, [string]$Destination) {
        # 1. Direct release asset download (fast, 10s timeout)
        $directUrl = "https://github.com/$TargetRepo/releases/latest/download/agy-patcher.exe"
        Write-Host "Downloading agy-patcher binary from $TargetRepo..." -ForegroundColor Cyan
        if (Download-FileWithProgress -Uri $directUrl -Destination $Destination -TimeoutSeconds 10 -Activity "Downloading agy-patcher.exe") {
            if ([System.IO.File]::Exists($Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 100000) {
                return $true
            }
        }

        # 2. Resilient fallback: GitHub API asset endpoint (handles CDN 504 Gateway Timeouts)
        try {
            Write-Host "[*] Direct release URL timed out / unavailable. Trying GitHub API fallback..." -ForegroundColor Yellow
            $apiUrl = "https://api.github.com/repos/$TargetRepo/releases/latest"
            $json = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "agy-patcher"; "Accept" = "application/vnd.github.v3+json" } -TimeoutSec 10
            $asset = $json.assets | Where-Object { $_.name -eq "agy-patcher.exe" } | Select-Object -First 1
            if ($asset -and $asset.url) {
                if (Download-FileWithProgress -Uri $asset.url -Destination $Destination -Headers @{ "Accept" = "application/octet-stream" } -TimeoutSeconds 20 -Activity "Downloading agy-patcher.exe (API fallback)") {
                    if ([System.IO.File]::Exists($Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 100000) {
                        return $true
                    }
                }
            }
        } catch {}

        return $false
    }

    function Download-PatcherPy([string]$TargetRepo, [string]$TargetBranch, [string]$Destination) {
        $cb = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $url = "https://raw.githubusercontent.com/$TargetRepo/$TargetBranch/patcher.py?cb=$cb"
        Write-Host "Downloading patcher.py from $TargetRepo ($TargetBranch)..." -ForegroundColor Cyan
        return (Download-FileWithProgress -Uri $url -Destination $Destination -TimeoutSeconds 15 -Activity "Downloading patcher.py")
    }

    function Get-LatestReleaseVersion([string]$TargetRepo) {
        try {
            $apiUrl = "https://api.github.com/repos/$TargetRepo/releases/latest"
            $json = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "agy-patcher" } -TimeoutSec 5
            if ($json -and $json.tag_name) {
                return $json.tag_name.TrimStart("v")
            }
        } catch {}
        try {
            $req = [System.Net.WebRequest]::Create("https://github.com/$TargetRepo/releases/latest")
            $req.Method = "HEAD"
            $req.AllowAutoRedirect = $false
            $req.Timeout = 5000
            $resp = $req.GetResponse()
            $loc = $resp.GetResponseHeader("Location")
            $resp.Close()
            if ($loc) {
                return ($loc -split "/")[-1].TrimStart("v")
            }
        } catch {}
        return $null
    }

    function Get-InstalledRunner {
        if ([System.IO.File]::Exists($InstalledExe)) {
            return @{ Path = $InstalledExe; Type = "exe" }
        }
        if ([System.IO.File]::Exists($InstalledCmd) -and [System.IO.File]::Exists($InstalledPy)) {
            return @{ Path = $InstalledCmd; Type = "py" }
        }
        return $null
    }

    function Get-RunnerVersion([hashtable]$runner) {
        try {
            $out = & $runner.Path --version 2>$null
            if ($out -match '(\d+(\.\d+)+)') {
                return $matches[1]
            }
        } catch {}
        return "0.0.0"
    }

    function Compare-IsGreater([string]$v1, [string]$v2) {
        try {
            return [System.Version]$v1 -gt [System.Version]$v2
        } catch {
            return $v1 -ne $v2
        }
    }

    $isInteractive = $true
    try {
        if ([Console]::IsInputRedirected) {
            $isInteractive = $false
        }
    } catch {
        $isInteractive = $false
    }

    # 1. Check if already installed (either binary exe or python wrapper)
    $runner = Get-InstalledRunner

    # Non-interactive or arguments passed: run directly
    if ($args.Count -gt 0 -or -not $isInteractive) {
        if ($runner) {
            Add-UserPath $InstallDir
            & $runner.Path @args
            return
        }
        if (Download-AgyExe $Repo $TempExe) {
            & $TempExe @args
            return
        }
        if (Download-PatcherPy $Repo $Branch $TempPy) {
            python $TempPy @args
            return
        }
        Write-Error "Failed to download and run agy-patcher."
        return
    }

    # Interactive mode: Already installed -> check updates then launch
    if ($runner) {
        Add-UserPath $InstallDir
        $localVer = Get-RunnerVersion $runner
        Write-Host "Installed: agy-patcher v$localVer ($($runner.Type.ToUpper()))" -ForegroundColor DarkGray

        # Upgrade to binary .exe if currently running Python shim on Windows
        if ($runner.Type -eq "py") {
            Write-Host "[*] Upgrading to compiled Windows binary (agy-patcher.exe)..." -ForegroundColor Cyan
            if (Download-AgyExe $Repo $InstalledExe) {
                $runner = @{ Path = $InstalledExe; Type = "exe" }
                $localVer = Get-RunnerVersion $runner
                Write-Host "[+] Successfully upgraded to binary agy-patcher.exe v$localVer!" -ForegroundColor Green
            } else {
                Write-Host "[-] Binary upgrade unavailable, continuing with Python runner..." -ForegroundColor Yellow
            }
        }

        Write-Host "Checking for updates..." -ForegroundColor Gray
        $remoteVer = Get-LatestReleaseVersion $Repo
        if ($remoteVer -and (Compare-IsGreater $remoteVer $localVer)) {
            Write-Host "[*] New version available: v$localVer -> v$remoteVer" -ForegroundColor Cyan
            $ans = Read-Host "Would you like to update agy-patcher now? [Y/n]"
            if ([string]::IsNullOrWhiteSpace($ans) -or $ans.Trim().ToLower() -eq "y" -or $ans.Trim().ToLower() -eq "yes") {
                Write-Host "Updating agy-patcher to v$remoteVer..." -ForegroundColor Cyan
                $downloadTemp = Join-Path $InstallDir "agy-patcher.new.exe"
                if (Download-AgyExe $Repo $downloadTemp) {
                    $oldExe = Join-Path $InstallDir "agy-patcher.old.exe"
                    if ([System.IO.File]::Exists($oldExe)) {
                        try { [System.IO.File]::Delete($oldExe) } catch {}
                    }
                    if ([System.IO.File]::Exists($InstalledExe)) {
                        [System.IO.File]::Move($InstalledExe, $oldExe)
                    }
                    [System.IO.File]::Move($downloadTemp, $InstalledExe)
                    # If previously python, refresh runner to exe
                    $runner = @{ Path = $InstalledExe; Type = "exe" }
                    Write-Host "[+] Successfully updated agy-patcher to v$remoteVer!" -ForegroundColor Green
                } else {
                    Write-Host "[-] Failed to download updated version, running existing..." -ForegroundColor Yellow
                }
            }
        }
        & $runner.Path @args
        return
    }

    # Not installed locally: prompt to install
    $ans = Read-Host "[?] agy-patcher is not installed. Would you like to install it to your system? [Y/n]"
    if ([string]::IsNullOrWhiteSpace($ans) -or $ans.Trim().ToLower() -eq "y" -or $ans.Trim().ToLower() -eq "yes") {
        Write-Host "Installing agy-patcher to $InstallDir..." -ForegroundColor Cyan
        if (-not (Test-Path -LiteralPath $InstallDir)) {
            New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        }

        # On Windows, always attempt compiled binary .exe first
        if (Download-AgyExe $Repo $InstalledExe) {
            Add-UserPath $InstallDir
            Write-Host "[+] agy-patcher successfully installed to $InstalledExe" -ForegroundColor Green
            Write-Host "[*] You can run it anytime with command: agy-patcher" -ForegroundColor Cyan
            & $InstalledExe @args
            return
        }

        # Fallback to Python wrapper only if binary download fails
        Write-Host "[-] Binary download unavailable, falling back to Python..." -ForegroundColor Yellow
        if (Download-PatcherPy $Repo $Branch $InstalledPy) {
            '@echo off' + "`r`n" + 'python "%~dp0patcher.py" %*' | Set-Content -LiteralPath $InstalledCmd -Encoding ASCII
            Add-UserPath $InstallDir
            Write-Host "[+] agy-patcher successfully installed via Python wrapper!" -ForegroundColor Green
            Write-Host "[*] You can run it anytime with command: agy-patcher" -ForegroundColor Cyan
            & $InstalledCmd @args
            return
        }
        Write-Error "Failed to install agy-patcher."
    } else {
        Write-Host "[*] Skipping installation. Running temporarily..." -ForegroundColor Yellow
        if (Download-AgyExe $Repo $TempExe) {
            & $TempExe @args
            return
        }
        if (Download-PatcherPy $Repo $Branch $TempPy) {
            python $TempPy @args
            return
        }
        Write-Error "Failed to run agy-patcher."
    }
} @args
