# Antigravity Patcher - one-command remote installer & launcher on Windows
# Usage:
#   irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex

& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $Repo = if ($env:AGY_REPO) { $env:AGY_REPO } else { "MickeyPickey/agy-patcher" }
    $Branch = if ($env:AGY_BRANCH) { $env:AGY_BRANCH } else { "main" }

    $InstallDir = Join-Path $env:LOCALAPPDATA "agy-patcher"
    $InstalledExe = Join-Path $InstallDir "agy-patcher.exe"
    $TempExe = Join-Path $env:TEMP "agy-patcher.exe"

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

    function Download-AgyExe([string]$TargetRepo, [string]$Destination) {
        $urls = @(
            "https://github.com/$TargetRepo/releases/latest/download/agy-patcher.exe",
            "https://github.com/$TargetRepo/releases/latest/download/antigravity-patcher.exe"
        )
        foreach ($u in $urls) {
            try {
                Invoke-WebRequest -Uri $u -OutFile $Destination -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
                if ((Test-Path $Destination) -and (Get-Item $Destination).Length -gt 100000) {
                    return $true
                }
            } catch {}
        }
        return $false
    }

    function Download-PatcherPy([string]$TargetRepo, [string]$TargetBranch, [string]$Destination) {
        $cb = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $url = "https://raw.githubusercontent.com/$TargetRepo/$TargetBranch/patcher.py?cb=$cb"
        try {
            Invoke-WebRequest -Uri $url -OutFile $Destination -UseBasicParsing -Headers @{"Cache-Control"="no-cache"}
            return (Test-Path $Destination)
        } catch {
            return $false
        }
    }

    function Get-LatestReleaseVersion([string]$TargetRepo) {
        try {
            $req = [System.Net.WebRequest]::Create("https://github.com/$TargetRepo/releases/latest")
            $req.Method = "HEAD"
            $req.AllowAutoRedirect = $false
            $resp = $req.GetResponse()
            $loc = $resp.GetResponseHeader("Location")
            $resp.Close()
            if ($loc) {
                return ($loc -split "/")[-1].TrimStart("v")
            }
        } catch {}
        return $null
    }

    function Get-ExeVersion([string]$exePath) {
        try {
            $out = & $exePath --version 2>$null
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

    # Non-interactive or arguments passed: run directly without prompting
    if ($args.Count -gt 0 -or -not $isInteractive) {
        if (Test-Path $InstalledExe) {
            Add-UserPath $InstallDir
            & $InstalledExe @args
            return
        }
        Write-Host "Downloading Antigravity Patcher from $Repo..." -ForegroundColor Cyan
        if (Download-AgyExe $Repo $TempExe) {
            & $TempExe @args
            return
        }
        # Fallback to python
        $tempPy = Join-Path $env:TEMP "patcher.py"
        if (Download-PatcherPy $Repo $Branch $tempPy) {
            python $tempPy @args
            return
        }
        Write-Error "Failed to download agy-patcher."
        return
    }

    # Interactive mode without arguments
    if (Test-Path $InstalledExe) {
        Add-UserPath $InstallDir
        $localVer = Get-ExeVersion $InstalledExe
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
                    if (Test-Path $oldExe) { Remove-Item $oldExe -Force -ErrorAction SilentlyContinue }
                    Move-Item $InstalledExe $oldExe -Force
                    Move-Item $downloadTemp $InstalledExe -Force
                    Write-Host "[+] Successfully updated agy-patcher to v$remoteVer!" -ForegroundColor Green
                } else {
                    Write-Host "[-] Failed to download updated version, running existing..." -ForegroundColor Yellow
                }
            }
        }
        & $InstalledExe @args
        return
    }

    # Not installed locally: prompt to install
    $ans = Read-Host "[?] agy-patcher is not installed. Would you like to install it to your system? [Y/n]"
    if ([string]::IsNullOrWhiteSpace($ans) -or $ans.Trim().ToLower() -eq "y" -or $ans.Trim().ToLower() -eq "yes") {
        Write-Host "Downloading and installing agy-patcher..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        if (Download-AgyExe $Repo $InstalledExe) {
            Add-UserPath $InstallDir
            Write-Host "[+] agy-patcher successfully installed to $InstalledExe" -ForegroundColor Green
            Write-Host "[*] You can run it anytime with the command: agy-patcher" -ForegroundColor Cyan
            & $InstalledExe @args
            return
        }
        Write-Host "[-] Failed to download compiled binary, falling back to Python..." -ForegroundColor Yellow
        $installedPy = Join-Path $InstallDir "patcher.py"
        if (Download-PatcherPy $Repo $Branch $installedPy) {
            $cmdShim = Join-Path $InstallDir "agy-patcher.cmd"
            '@echo off' + "`r`n" + 'python "%~dp0patcher.py" %*' | Set-Content -Path $cmdShim -Encoding ASCII
            Add-UserPath $InstallDir
            Write-Host "[+] agy-patcher successfully installed via Python wrapper!" -ForegroundColor Green
            & $cmdShim @args
            return
        }
        Write-Error "Failed to install agy-patcher."
    } else {
        Write-Host "[*] Skipping installation. Running temporarily..." -ForegroundColor Yellow
        Write-Host "Downloading Antigravity Patcher from $Repo..." -ForegroundColor Cyan
        if (Download-AgyExe $Repo $TempExe) {
            & $TempExe @args
            return
        }
        $tempPy = Join-Path $env:TEMP "patcher.py"
        if (Download-PatcherPy $Repo $Branch $tempPy) {
            python $tempPy @args
            return
        }
        Write-Error "Failed to run agy-patcher."
    }
}
