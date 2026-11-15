# Lets another computer on the home network watch lektyra through an SSH tunnel (runbook: "Watch from another
# computer"). lektyra itself keeps listening on 127.0.0.1 only; this opens SSH, key-only, from the local subnet only,
# and the computer's key may only forward to lektyra's port: no shell, no other port.
#
# Run once in a terminal as administrator, in the repository folder:
#   pwsh -ExecutionPolicy Bypass -File .\scripts\enable-remote-view.ps1 -ComputerKey 'ssh-ed25519 AAAA... martin-mac'
# Running it again with another key adds that key too.
param(
    [Parameter(Mandatory = $true)][string]$ComputerKey,
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this in PowerShell as administrator.' }
$ComputerKey = $ComputerKey.Trim()
if ($ComputerKey -notmatch '^(ssh-ed25519|ecdsa-sha2-nistp\d+|ssh-rsa) [A-Za-z0-9+/=]+( .*)?$') {
    throw 'ComputerKey must be one public key line, e.g. the content of ~/.ssh/lektyra_pc.pub on the Mac.'
}

# 1. the OpenSSH server (part of Windows)
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    Write-Host 'Installing the OpenSSH server...'
    Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' | Out-Null
}
$sshDir = Join-Path $env:ProgramData 'ssh'
$config = Join-Path $sshDir 'sshd_config'
if (-not (Test-Path $config)) {
    Start-Service sshd  # the first start writes sshd_config and the host keys
    Stop-Service sshd
}

# 2. keys only, never a password
$lines = Get-Content $config
if ($lines -match '^\s*#?\s*PasswordAuthentication\b') {
    $lines = $lines -replace '^\s*#?\s*PasswordAuthentication\b.*$', 'PasswordAuthentication no'
} else {
    $lines = @('PasswordAuthentication no') + $lines
}
Set-Content -Path $config -Value $lines -Encoding ascii

# 3. the firewall: SSH from the home network only (Windows' own rule allows any address)
Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
Get-NetFirewallRule -Name 'lektyra-ssh-lan' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name 'lektyra-ssh-lan' -DisplayName 'SSH from the home network only (lektyra)' `
    -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress LocalSubnet -Action Allow | Out-Null

# 4. the computer's key, allowed only to forward to lektyra. An administrator's keys live in
#    administrators_authorized_keys (sshd ignores ~/.ssh/authorized_keys for them), readable by
#    Administrators and SYSTEM only.
$keys = Join-Path $sshDir 'administrators_authorized_keys'
$line = "restrict,port-forwarding,permitopen=`"127.0.0.1:$Port`" $ComputerKey"
$present = (Test-Path $keys) -and ((Get-Content $keys) -contains $line)
if (-not $present) { Add-Content -Path $keys -Value $line -Encoding ascii }
icacls.exe $keys /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null

# 5. start now and at every boot
Set-Service sshd -StartupType Automatic
Restart-Service sshd

$address = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.PrefixOrigin -in 'Dhcp', 'Manual' -and $_.InterfaceAlias -notmatch 'vEthernet|VPN|TAP|Loopback' } |
    Select-Object -ExpandProperty IPAddress
Write-Host ''
Write-Host "Ready. On the Mac: HostName $($address -join ' or ') (or $env:COMPUTERNAME.local), User $env:USERNAME."
Write-Host 'The PC''s fingerprint, to compare when the Mac connects the first time:'
ssh-keygen.exe -lf (Join-Path $sshDir 'ssh_host_ed25519_key.pub')
