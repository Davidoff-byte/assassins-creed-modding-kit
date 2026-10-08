# set-remote-ip.ps1 - point the live AC4BF plugin [Coop] config at a peer IP (and optionally ports).
# Writes RemoteIp1..4 as the four octets of one address, in place. Safe to run while the game runs
# (the plugin live-reloads the ini).
param(
  [Parameter(Mandatory=$true)][string]$Ip,
  [string]$Ini = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.ini",
  [int]$LocalPort = 0,
  [int]$RemotePort = 0,
  [int]$ClientId = 0
)

$oct = $Ip.Split('.')
if ($oct.Count -ne 4) { "bad IP '$Ip' (need 4 octets)"; exit 1 }
foreach ($o in $oct) {
  $v = 0
  if (-not [int]::TryParse($o, [ref]$v) -or $v -lt 0 -or $v -gt 255) { "bad octet '$o' in '$Ip'"; exit 1 }
}
if (-not (Test-Path $Ini)) { "ini not found: $Ini"; exit 1 }

$lines = Get-Content $Ini
$out = New-Object System.Collections.ArrayList
$inCoop = $false
foreach ($ln in $lines) {
  $t = $ln.Trim()
  if ($t -match '^\[') { $inCoop = ($t -ieq '[Coop]') }
  if ($inCoop) {
    if ($t -match '^RemoteIp1\s*=') { [void]$out.Add("RemoteIp1=$($oct[0])"); continue }
    if ($t -match '^RemoteIp2\s*=') { [void]$out.Add("RemoteIp2=$($oct[1])"); continue }
    if ($t -match '^RemoteIp3\s*=') { [void]$out.Add("RemoteIp3=$($oct[2])"); continue }
    if ($t -match '^RemoteIp4\s*=') { [void]$out.Add("RemoteIp4=$($oct[3])"); continue }
    if ($LocalPort -gt 0 -and $t -match '^LocalPort\s*=')  { [void]$out.Add("LocalPort=$LocalPort"); continue }
    if ($RemotePort -gt 0 -and $t -match '^RemotePort\s*=') { [void]$out.Add("RemotePort=$RemotePort"); continue }
    if ($ClientId -gt 0 -and $t -match '^ClientId\s*=')  { [void]$out.Add("ClientId=$ClientId"); continue }
  }
  [void]$out.Add($ln)
}

[System.IO.File]::WriteAllLines($Ini, $out, (New-Object System.Text.ASCIIEncoding))
"updated: $Ini"
"peer IP: $Ip (octets $($oct -join ' / '))"
Get-Content $Ini | Select-String 'RemoteIp|LocalPort|RemotePort|ClientId' | ForEach-Object { "  " + $_.Line }
