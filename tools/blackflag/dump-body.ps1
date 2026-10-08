# Dump a body object's memory to file for offline comparison.
param(
  [Parameter(Mandatory=$true)][string]$Addr,
  [int]$Size = 0x600,
  [string]$Out = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\body_dump.bin"
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MemDump {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int access, bool inherit, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
}
"@
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit 1 }
$h = [MemDump]::OpenProcess(0x0410, $false, $p.Id)
$base = [Convert]::ToInt64($Addr, 16)
$buf = New-Object byte[] $Size
$read = [IntPtr]::Zero
$ok = [MemDump]::ReadProcessMemory($h, [IntPtr]$base, $buf, $Size, [ref]$read)
if (-not $ok) { "ReadProcessMemory failed"; exit 1 }
[System.IO.File]::WriteAllBytes($Out, $buf)
"dumped $Size bytes from $Addr to $Out"
# also print a readable hex+ascii listing
$lines = @()
for ($r = 0; $r -lt $Size; $r += 16) {
  $hex = ($buf[$r..([Math]::Min($r+15,$Size-1))] | ForEach-Object { $_.ToString("X2") }) -join " "
  $asc = -join ($buf[$r..([Math]::Min($r+15,$Size-1))] | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { "." } })
  $lines += ("0x{0:X6}  {1,-47}  {2}" -f ($r), $hex, $asc)
}
$lines | Set-Content "$Out.txt"
"listing -> $Out.txt"
