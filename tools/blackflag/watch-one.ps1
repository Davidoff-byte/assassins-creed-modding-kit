# watch-one.ps1 - poll a single object's bytes, log changes + recycle.
param(
  [Parameter(Mandatory = $true)][string]$Addr,
  [int]$Seconds = 300,
  [int]$IntervalMs = 80,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\health"
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WO {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
}
'@
[WO]::H = [WO]::OpenProcess(0x0410, $false, $game.Id)

$a = [Convert]::ToInt64($Addr, 16)
$logf = Join-Path $OutDir ("watchone_" + (Get-Date -Format "HHmmss") + ".log")
$HEALTH_VT = 0x02712F60
"watching {0:X8} for {1}s -> {2}" -f $a, $Seconds, $logf

$prev = $null
$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
  Start-Sleep -Milliseconds $IntervalMs
  $ts = (Get-Date).ToString("HH:mm:ss.fff")
  $b = [WO]::Read($a, 0x78)
  if ($b -eq $null) { continue }
  $vt = [BitConverter]::ToUInt32($b, 0)
  if ($vt -ne $HEALTH_VT) {
    $line = "{0}  RECYCLED (vt={1:X8})" -f $ts, $vt
    Add-Content -Path $logf -Value $line
    $line
    break
  }
  $hex = ($b | ForEach-Object { $_.ToString("X2") }) -join ''
  if ($prev -eq $null) { $prev = $hex; continue }
  if ($hex -eq $prev) { continue }
  for ($i = 0; $i -lt ($hex.Length / 2); $i++) {
    $x = $hex.Substring($i * 2, 2)
    $y = $prev.Substring($i * 2, 2)
    if ($x -ne $y) {
      $line = "{0}  +0x{1:X2}: {2} -> {3}" -f $ts, $i, $y, $x
      Add-Content -Path $logf -Value $line
      $line
    }
  }
  $prev = $hex
}
"done -> $logf"
