# Keeps the PC's current home address for good: the address, gateway and DNS the router gave by DHCP become static,
# so http://lektyra.lan:8765 (the Mac's /etc/hosts) keeps working. The network drops for a second or two: not while
# a show records. Pick an address outside the router's DHCP range if you can; a reservation in the router does the
# same without touching the PC.
#
# Run once in a terminal as administrator:
#   pwsh -ExecutionPolicy Bypass -File .\scripts\pin-address.ps1
# Undo (DHCP again):
#   Set-NetIPInterface -InterfaceAlias Ethernet -AddressFamily IPv4 -Dhcp Enabled
#   Set-DnsClientServerAddress -InterfaceAlias Ethernet -ResetServerAddresses
param([string]$Interface = 'Ethernet')
$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this in a terminal as administrator.' }

$ipIf = Get-NetIPInterface -InterfaceAlias $Interface -AddressFamily IPv4
if ($ipIf.Dhcp -eq 'Disabled') {
    $now = Get-NetIPAddress -InterfaceAlias $Interface -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress
    Write-Host "Already static: $now"
    return
}
$config = Get-NetIPConfiguration -InterfaceAlias $Interface
$address = @($config.IPv4Address)[0]
$ip = $address.IPAddress
$prefix = $address.PrefixLength
$gateway = @($config.IPv4DefaultGateway)[0].NextHop
$dns = (Get-DnsClientServerAddress -InterfaceAlias $Interface -AddressFamily IPv4).ServerAddresses
if (-not $ip -or -not $gateway -or -not $dns) { throw "Incomplete DHCP settings on $Interface; nothing changed." }
Write-Host "Pinning $ip/$prefix, gateway $gateway, DNS $($dns -join ', ') on $Interface"

Set-NetIPInterface -InterfaceAlias $Interface -AddressFamily IPv4 -Dhcp Disabled
Get-NetIPAddress -InterfaceAlias $Interface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Get-NetRoute -InterfaceAlias $Interface -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
New-NetIPAddress -InterfaceAlias $Interface -IPAddress $ip -PrefixLength $prefix -DefaultGateway $gateway | Out-Null
Set-DnsClientServerAddress -InterfaceAlias $Interface -ServerAddresses $dns

Start-Sleep -Seconds 3
$ok = Test-Connection -TargetName $gateway -Count 1 -Quiet
Write-Host "Static now: $ip. Gateway answers: $ok"
