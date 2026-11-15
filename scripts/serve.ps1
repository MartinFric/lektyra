# lektyra's backend as a background service (ADR-016). The Windows task "lektyra" runs this at logon, hidden
# (scripts/install-service.ps1). It brings up Postgres and MinIO (Docker), runs `lektyra serve`, and starts it
# again 15 s after it stops. Idle while nothing runs: no voice model is loaded until a session starts, and the
# schedule is one small database query every few seconds. Log: data/logs/serve-<day>.log (data/ is never in git).
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$winget = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
$tools = @(
    (Get-ChildItem $winget -Directory -Filter 'astral-sh.uv_*' -ErrorAction SilentlyContinue | Select-Object -First 1),
    (Get-ChildItem $winget -Directory -Filter 'yt-dlp.yt-dlp_*' -ErrorAction SilentlyContinue | Select-Object -First 1),
    (Get-ChildItem $winget -Recurse -Depth 3 -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Directory })
) | Where-Object { $_ } | ForEach-Object { $_.FullName }
$env:Path = (($tools + $env:Path) -join ';')
$env:PYTHONUNBUFFERED = '1'

$logs = Join-Path $repo 'data\logs'
New-Item -ItemType Directory -Force $logs | Out-Null
while ($true) {
    $log = Join-Path $logs ('serve-{0:yyyy-MM-dd}.log' -f (Get-Date))
    "$(Get-Date -Format s) starting lektyra serve" | Out-File -Append -Encoding utf8 $log
    docker compose up -d *>> $log
    uv run lektyra serve --lan *>> $log
    "$(Get-Date -Format s) lektyra serve stopped (exit $LASTEXITCODE); starting again in 15 s" | Out-File -Append -Encoding utf8 $log
    Start-Sleep -Seconds 15
}
