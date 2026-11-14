# Installs (or replaces) the Windows task "lektyra": scripts/serve.ps1, hidden, from logon, for this user only.
# No admin rights needed. Stop it: scripts/stop-service.ps1. Remove it: Unregister-ScheduledTask lektyra -Confirm:$false
$repo = Split-Path -Parent $PSScriptRoot
$pwsh = (Get-Command pwsh).Source
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $pwsh -WorkingDirectory $repo `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$repo\scripts\serve.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'lektyra' -Force -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "lektyra's backend: the schedule and live sessions (ADR-016). Idle until something runs." |
    Out-Null
"installed: the task 'lektyra' starts lektyra serve at logon. Start it now: Start-ScheduledTask lektyra"
