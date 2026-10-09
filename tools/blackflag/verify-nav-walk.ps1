# verify-nav-walk.ps1 - after an accepted NavigateTo, find the NPC's body via its known service
# container P (scan for the pointer) and sample its feet position to confirm real walking.
param([long]$P = 0, [int]$Seconds = 45, [int]$IntervalMs = 250)
$ErrorActionPreference = 'Continue'

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class VNW {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size]; IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static uint U32(long a) { var b = Read(a, 4); return b == null ? 0 : BitConverter.ToUInt32(b, 0); }
  public static float F32(long a) { var b = Read(a, 4); return b == null ? 0f : BitConverter.ToSingle(b, 0); }
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
[VNW]::H = [VNW]::OpenProcess(0x0410, $false, $game.Id)

# player position from the plugin log
$log = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.log"
$tail = Get-Content $log -Tail 300
$pp = $null
foreach ($l in $tail) {
  if ($l -match "PlayerTransform: pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)") {
    $pp = @([double]$Matches[1], [double]$Matches[2], [double]$Matches[3])
  }
}
"player at ($($pp[0]), $($pp[1]), $($pp[2]))"

"scanning for P=0x$('{0:X8}' -f $P)..."
$hits = [VNW]::ScanU32(0x30000000, 0x50000000, [uint32]$P, 0x800000)
"pointer hits: $($hits.Count)"
$body = 0
foreach ($h in $hits) {
  $b = $h - 0x114
  if ($b -lt 0x10000) { continue }
  if ([VNW]::U32($b) -eq 0x01E4CE90 -and [VNW]::U32($b + 0x68) -eq 0x04DD5F8C) { $body = $b; break }
}
if ($body -eq 0) { "body not found near any hit; dumping hit candidates:"; foreach ($h in ($hits | Select-Object -First 10)) { $b = $h - 0x114; "  hit=0x{0:X8} body?=0x{1:X8} vt=0x{2:X8} mark=0x{3:X8}" -f $h, $b, ([VNW]::U32($b)), ([VNW]::U32($b + 0x68)) }; exit 1 }
"BODY = 0x$('{0:X8}' -f $body)"
"sampling position for $Seconds s..."
$start = Get-Date
$lastX = $null; $lastY = $null; $lastT = $null
while (((Get-Date) - $start).TotalSeconds -lt $Seconds) {
  $x = [VNW]::F32($body + 0x40); $y = [VNW]::F32($body + 0x44); $z = [VNW]::F32($body + 0x48)
  $now = Get-Date
  $spd = ""
  if ($null -ne $lastX) {
    $d = [Math]::Sqrt(($x - $lastX) * ($x - $lastX) + ($y - $lastY) * ($y - $lastY))
    $dt = ($now - $lastT).TotalSeconds
    if ($dt -gt 0) { $spd = "  spd={0:F2} m/s" -f ($d / $dt) }
  }
  $dp = [Math]::Sqrt(($x - $pp[0]) * ($x - $pp[0]) + ($y - $pp[1]) * ($y - $pp[1]))
  "{0}  pos=({1:F1},{2:F1},{3:F1}) distPlayer={4:F1}{5}" -f $now.ToString("HH:mm:ss.fff"), $x, $y, $z, $dp, $spd
  $lastX = $x; $lastY = $y; $lastT = $now
  Start-Sleep -Milliseconds $IntervalMs
}
"done"
