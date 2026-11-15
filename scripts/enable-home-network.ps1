# Lets the computers at home open lektyra (`lektyra serve --lan`, which scripts/serve.ps1 runs): one inbound rule
# for its port, from the local subnet of the wired network only (not the VPN, not WSL). lektyra has no login, so
# anyone on the home network can use it; that is the trade-off (runbook: "Watch from another computer").
#
# Run once in a terminal as administrator, in the repository folder:
#   pwsh -ExecutionPolicy Bypass -File .\scripts\enable-home-network.ps1
# Undo: Remove-NetFirewallRule -Name lektyra-home
param(
    [int]$Port = 8765,
    [string]$Interface = 'Ethernet'
)
$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this in a terminal as administrator.' }
if (-not (Get-NetAdapter -Name $Interface -ErrorAction SilentlyContinue)) {
    throw "No network adapter '$Interface'. Pass -Interface with the one the PC uses at home (Get-NetAdapter)."
}

Get-NetFirewallRule -Name 'lektyra-home' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name 'lektyra-home' -DisplayName 'lektyra from the home network' -Direction Inbound `
    -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet -InterfaceAlias $Interface -Action Allow | Out-Null

$address = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias $Interface | Select-Object -ExpandProperty IPAddress
Write-Host "Ready. At home open http://$($env:COMPUTERNAME.ToLower()).local:$Port or http://$($address):$Port"
