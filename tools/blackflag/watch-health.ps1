# watch-health.ps1 v2 - poll CSrvNPCHealth instances across heap ranges, log byte changes,
# detect recycled objects (vt changed) so log stays clean.
param(
  [int]$Seconds = 600,
  [int]$IntervalMs = 120,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\health"
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class WH2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static List<long> ScanU32(long lo, long hi, uint pattern, int chunk) {
    var found = new List<long>();
    var buf = new byte[chunk];
    for (long p = lo; p < hi; p += chunk) {
      IntPtr r;
      int size = (int)Math.Min(chunk, hi - p);
      if (!ReadProcessMemory(H, (IntPtr)p, buf, size, out r)) continue;
      for (int i = 0; i + 4 <= size; i += 4) {
        if (BitConverter.ToUInt32(buf, i) == pattern) found.Add(p + i);
      }
    }
    return found;
  }
}
'@
[WH2]::H = [WH2]::OpenProcess(0x0410, $false, $game.Id)

$HEALTH_VT = [uint32]0x02712F60
$ranges = @(@(0x0E000000L, 0x2E000000L), @(0x2E000000L, 0x31000000L), @(0x30000000L, 0x56000000L), @(0x56000000L, 0x80000000L), @(0x80000000L, 0xF0000000L), @(0xF0000000L, 0xFFF00000L))
$hits = New-Object System.Collections.Generic.List[long]
foreach ($r in $ranges) {
  $found = [WH2]::ScanU32($r[0], $r[1], $HEALTH_VT, 0x800000)
  foreach ($f in $found) { if (-not $hits.Contains($f)) { $hits.Add($f) } }
}
"watching $($hits.Count) instances for $Seconds s ..."
$logf = Join-Path $OutDir ("watch_" + (Get-Date -Format "HHmmss") + ".log")

function ObjState([long]$a) {
  $b = [WH2]::Read($a, 0x78)
  if ($b -eq $null) { return $null }
  if ([BitConverter]::ToUInt32($b, 0) -ne $HEALTH_VT) { return "RECYCLED" }
  return (($b | ForEach-Object { $_.ToString("X2") }) -join '')
}

$prev = @{}
$base = @()
foreach ($h in $hits) {
  $s = ObjState $h
  if ($s -eq $null) { continue }
  if ($s -eq "RECYCLED") { continue }
  $prev[$h] = $s
  $L = [BitConverter]::ToUInt16([byte[]]@([Convert]::ToByte($s.Substring(0x5A * 2, 2), 16), [Convert]::ToByte($s.Substring(0x5A * 2 + 2, 2), 16)), 0)
  $M = [BitConverter]::ToUInt16([byte[]]@([Convert]::ToByte($s.Substring(0x5C * 2, 2), 16), [Convert]::ToByte($s.Substring(0x5C * 2 + 2, 2), 16)), 0)
  $X = [BitConverter]::ToUInt16([byte[]]@([Convert]::ToByte($s.Substring(0x5E * 2, 2), 16), [Convert]::ToByte($s.Substring(0x5E * 2 + 2, 2), 16)), 0)
  $F = $s.Substring(0x60 * 2, 8)
  $base += ("BASE {0:X8} +5A={1} +5C={2} +5E={3} +60={4}" -f $h, $L, $M, $X, $F)
}
$base | Set-Content $logf
$base | Select-Object -First 5

$t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
  Start-Sleep -Milliseconds $IntervalMs
  $ts = (Get-Date).ToString("HH:mm:ss.fff")
  foreach ($h in @($prev.Keys)) {
    $s = ObjState $h
    if ($s -eq $null) { continue }
    if ($s -eq "RECYCLED") {
      $line = "{0}  {1:X8} RECYCLED (no longer health service)" -f $ts, $h
      Add-Content -Path $logf -Value $line
      $line
      $prev.Remove($h)
      continue
    }
    $o = $prev[$h]
    if ($s -eq $o) { continue }
    for ($i = 0; $i -lt ($s.Length / 2); $i++) {
      $a = $s.Substring($i * 2, 2)
      $c = $o.Substring($i * 2, 2)
      if ($a -ne $c) {
        $line = "{0}  {1:X8} +0x{2:X2}: {3} -> {4}" -f $ts, $h, $i, $c, $a
        Add-Content -Path $logf -Value $line
        $line
      }
    }
    $prev[$h] = $s
  }
}
"done -> $logf"
