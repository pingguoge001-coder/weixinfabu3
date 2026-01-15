#requires -Version 5.1
<###
.SYNOPSIS
  Prepare to lock WeChat version before 4.0.3.36 on Windows 11.
.DESCRIPTION
  Dry-run by default. Use -Execute to perform actions.
.PARAMETER Execute
  Run actions for real (default is dry-run).
.PARAMETER AutoBackup
  Automatically back up Documents\WeChat Files to D:\WeChatBackup_yyyyMMdd_HHmmss.
.PARAMETER ForceCleanup
  Skip double-confirmation for cleanup of app directories.
.EXAMPLE
  .\lock-wechat-prep.ps1
.EXAMPLE
  .\lock-wechat-prep.ps1 -Execute -AutoBackup
###>

[CmdletBinding()]
param(
    [switch]$Execute,
    [switch]$AutoBackup,
    [switch]$ForceCleanup
)

$DryRun = -not $Execute.IsPresent
$cnWeChat = ([char]0x5FAE) + ([char]0x4FE1)
$cnWeChatPattern = "^$([regex]::Escape($cnWeChat))(\\s|\\d|$)"
$uninstallPatternEnglish = "(?i)WeChat|Weixin"

function Write-Log {
    param(
        [string]$Level,
        [string]$Message
    )
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = if ($DryRun) { "[DRYRUN] " } else { "" }
    Write-Host "$ts ${prefix}[$Level] $Message"
}

function Invoke-Action {
    param(
        [string]$What,
        [ScriptBlock]$Action
    )
    if ($DryRun) {
        Write-Log "INFO" "Would: $What"
        return $null
    }

    Write-Log "INFO" $What
    try {
        & $Action
        Write-Log "OK" "Done: $What"
    } catch {
        Write-Log "ERROR" "Failed: $What. $($_.Exception.Message)"
    }
}

function Confirm-Cleanup {
    if ($ForceCleanup) {
        return $true
    }

    if ($DryRun) {
        Write-Log "INFO" "Cleanup requires double confirmation (use -ForceCleanup to skip)."
        return $false
    }

    $ans1 = Read-Host "Cleanup will remove app folders (not Documents\\WeChat Files). Continue? (y/N)"
    if ($ans1 -notmatch '^(y|yes)$') {
        Write-Log "INFO" "Cleanup skipped by user."
        return $false
    }

    $ans2 = Read-Host "Type DELETE to confirm cleanup"
    if ($ans2 -ne "DELETE") {
        Write-Log "INFO" "Cleanup confirmation failed."
        return $false
    }

    return $true
}

Write-Log "INFO" "Start: WeChat pre-clean and update lock preparation."
Write-Log "INFO" "Mode: $(if ($DryRun) { 'DryRun (no changes)' } else { 'Execute' })"

# 1) Backup reminder / optional auto-backup
$docsPath = [Environment]::GetFolderPath('MyDocuments')
$wechatFiles = Join-Path $docsPath "WeChat Files"
Write-Log "INFO" "Please back up: $wechatFiles"

if (Test-Path $wechatFiles) {
    if ($AutoBackup) {
        $backupRoot = "D:\WeChatBackup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
        Invoke-Action "Backup '$wechatFiles' to '$backupRoot'" {
            New-Item -Path $backupRoot -ItemType Directory -Force | Out-Null
            Copy-Item -Path $wechatFiles -Destination $backupRoot -Recurse -Force
        }
    } else {
        Write-Log "INFO" "Optional: run with -AutoBackup to back up to D:\WeChatBackup_yyyyMMdd_HHmmss"
    }
} else {
    Write-Log "WARN" "WeChat Files folder not found at $wechatFiles"
}

# 2) Stop WeChat/Tencent related processes
$procPattern = '(?i)WeChat|Weixin|Tencent|QQ|TXPlatform|WeChatAppEx|WeChatUpdate'
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match $procPattern }
if ($procs) {
    $procNames = $procs | Select-Object -ExpandProperty ProcessName -Unique
    Write-Log "INFO" "Matched processes: $($procNames -join ', ')"
    Invoke-Action "Stop matched processes" {
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Log "INFO" "No matching processes found."
}

# 3) Uninstall via winget (if available)
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    $wingetTargets = @(
        @{ Label = "WeChat"; Args = @("uninstall", "-e", "--name", "WeChat") },
        @{ Label = "Weixin"; Args = @("uninstall", "-e", "--name", "Weixin") },
        @{ Label = "Tencent.WeChat"; Args = @("uninstall", "-e", "--id", "Tencent.WeChat") },
        @{ Label = "WeChat.WeChat"; Args = @("uninstall", "-e", "--id", "WeChat.WeChat") }
    )

    foreach ($t in $wingetTargets) {
        $wingetArgs = $t.Args + @("--accept-source-agreements")
        $cmd = "winget " + ($wingetArgs -join " ")
        if ($DryRun) {
            Write-Log "INFO" "Would run: $cmd"
        } else {
            Write-Log "INFO" "Running: $cmd"
            & winget @wingetArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Log "WARN" "winget uninstall failed or not found for target: $($t.Label)"
            } else {
                Write-Log "OK" "winget uninstall attempted for target: $($t.Label)"
            }
        }
    }
} else {
    Write-Log "WARN" "winget not found. Will use registry uninstall only."
}

# Registry uninstall (desktop)
function Get-UninstallEntries {
    $paths = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
    )

    $entries = foreach ($p in $paths) {
        if (Test-Path $p) {
            Get-ItemProperty -Path (Join-Path $p "*") -ErrorAction SilentlyContinue
        }
    }

    $entries | Where-Object {
        $_.DisplayName -and (
            $_.DisplayName -match $uninstallPatternEnglish -or
            $_.DisplayName -match $cnWeChatPattern
        )
    }
}

$uninstallEntries = Get-UninstallEntries
if ($uninstallEntries) {
    Write-Log "INFO" "Found uninstall entries:"
    foreach ($e in $uninstallEntries) {
        Write-Log "INFO" "- $($e.DisplayName)"
    }

    function Split-UninstallCommand {
        param([string]$Raw)
        $trim = $Raw.Trim()
        if ($trim -match '^\s*\"([^\"]+)\"\s*(.*)$') {
            return @{ File = $matches[1]; Args = $matches[2].Trim() }
        }

        $exeMatch = [regex]::Match($trim, '^(.*?\.(exe|msi|cmd|bat))\b\s*(.*)$', 'IgnoreCase')
        if ($exeMatch.Success) {
            return @{ File = $exeMatch.Groups[1].Value.Trim(); Args = $exeMatch.Groups[3].Value.Trim() }
        }

        $parts = $trim -split '\s+', 2
        $file = $parts[0]
        $args = if ($parts.Count -gt 1) { $parts[1] } else { "" }
        return @{ File = $file; Args = $args }
    }

    foreach ($e in $uninstallEntries) {
        $cmd = $e.QuietUninstallString
        if (-not $cmd) { $cmd = $e.UninstallString }
        if (-not $cmd) {
            Write-Log "WARN" "No uninstall command for: $($e.DisplayName)"
            continue
        }

        if ($cmd -match '(?i)msiexec' -and $cmd -match '/I') {
            $cmd = $cmd -replace '/I', '/X'
        }

        $cmdInfo = Split-UninstallCommand -Raw $cmd
        if ($DryRun) {
            Write-Log "INFO" "Would uninstall: $($e.DisplayName) with '$($cmdInfo.File) $($cmdInfo.Args)'"
        } else {
            Write-Log "INFO" "Uninstalling: $($e.DisplayName)"
            try {
                Start-Process -FilePath $cmdInfo.File -ArgumentList $cmdInfo.Args -Wait -NoNewWindow
                Write-Log "OK" "Uninstall command executed for: $($e.DisplayName)"
            } catch {
                Write-Log "ERROR" "Uninstall failed for: $($e.DisplayName). $($_.Exception.Message)"
            }
        }
    }
} else {
    Write-Log "INFO" "No matching uninstall entries found."
}

# 4) Cleanup residual directories (double confirm or -ForceCleanup)
$cleanupPaths = @(
    "$env:ProgramFiles\Tencent",
    "${env:ProgramFiles(x86)}\Tencent",
    "$env:APPDATA\Tencent",
    "$env:LOCALAPPDATA\Tencent",
    "$env:LOCALAPPDATA\WeChat"
)

$doCleanup = if ($DryRun) {
    Write-Log "INFO" "Cleanup will require double confirmation in Execute mode (or use -ForceCleanup)."
    $true
} else {
    Confirm-Cleanup
}
if ($doCleanup) {
    foreach ($p in $cleanupPaths) {
        if (Test-Path $p) {
            Invoke-Action "Remove folder '$p'" {
                Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Log "INFO" "Path not found: $p"
        }
    }
} else {
    Write-Log "INFO" "Cleanup step skipped."
}

# 5) Disable WeChat/Tencent update scheduled tasks
$taskPatternBase = '(?i)WeChat|Weixin|Tencent|TXPlatform'
$taskPatternUpdate = '(?i)Update|Updater'
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $fullName = $_.TaskPath + $_.TaskName
    ($fullName -match $taskPatternBase) -or (($fullName -match $taskPatternUpdate) -and ($fullName -match $taskPatternBase))
}

if ($tasks) {
    Write-Log "INFO" "Matched scheduled tasks:"
    foreach ($t in $tasks) {
        Write-Log "INFO" "- $($t.TaskPath)$($t.TaskName)"
    }

    if ($DryRun) {
        Write-Log "INFO" "Would disable the matched tasks."
    } else {
        foreach ($t in $tasks) {
            try {
                Disable-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath | Out-Null
                Write-Log "OK" "Disabled task: $($t.TaskPath)$($t.TaskName)"
            } catch {
                Write-Log "ERROR" "Failed to disable task: $($t.TaskPath)$($t.TaskName). $($_.Exception.Message)"
            }
        }
    }
} else {
    Write-Log "INFO" "No matching scheduled tasks found."
}

# 6) Next steps
Write-Host ""
Write-Log "INFO" "Next steps:"
Write-Host "  1) Restart the PC."
Write-Host "  2) Install WeChat 4.0.3.36."
Write-Host "  3) Optional hard lock (ACL) after install, run as admin:"
Write-Host '     icacls "C:\Program Files\Tencent\WeChat" /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" /deny "Users:(OI)(CI)W"'
Write-Host "     (Adjust path if installed elsewhere. This is not executed by this script.)"

Write-Log "INFO" "Completed."
