# Stops the "lektyra" task and the lektyra serve it started (Windows does not stop child processes with the task).
# Needed before `uv add` / `uv sync` (they replace lektyra.exe). Start again: Start-ScheduledTask lektyra
param([int]$Port = 8765)
Stop-ScheduledTask -TaskName 'lektyra' -ErrorAction SilentlyContinue
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($pid_ in ($listening | Select-Object -ExpandProperty OwningProcess -Unique)) {
    Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
}
Get-Process lektyra -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
"stopped"
