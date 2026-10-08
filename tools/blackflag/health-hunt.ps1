# health-hunt.ps1 - find the NPC health field and (later) the damage writer.
# Phases:
#   find  : list candidate NPC bodies near the player (scan for the body vtable)
#   snap  : snapshot each candidate's memory window
#   diff  : rescan and report fields that DECREASED (= damage taken)
# Usage:
#   health-hunt.ps1 -Phase find
#   health-hunt.ps1 -Phase snap
#   <hit the guard(s) in game>
#   health-hunt.ps1 -Phase diff
param(
  [Parameter(Mandatory=$true)][ValidateSet("find","snap","diff")][string]$Phase,
  [int]$Radius = 45,
  [string]$Tag = "a",
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\healthhunt"
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class HH {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  // scan [lo,hi) in chunks; return addresses where u32 == pattern (4-byte aligned steps)
  public static List<long> ScanBodies(long lo, long hi, uint pattern, int chunk) {
    var found = new List<long>();
    var buf = new byte[chunk];
    for (long p = lo; p < hi; p += chunk) {
      IntPtr r;
      int size = (int)Math.Min(chunk, hi - p);
      if (!ReadProcessMemory(H, (IntPtr)p, buf, size, out r)) continue;
      for (int i = 0; i + 4 <= size; i += 4) {
        if (buf[i] == (byte)(pattern & 0xFF) && buf[i+1] == (byte)((pattern >> 8) & 0xFF) &&
            buf[i+2] == (byte)((pattern >> 16) & 0xFF) && buf[i+3] == (byte)((pattern >> 24) & 0xFF)) {
          found.Add(p + i);
        }
      }
    }
    return found;
  }
  public static uint U32(long addr) { var b = Read(addr, 4); return b == null ? 0 : BitConverter.ToUInt32(b, 0); }
  public static ushort U16(long addr) { var b = Read(addr, 2); return b == null ? (ushort)0 : BitConverter.ToUInt16(b, 0); }
  public static float F32(long addr) { var b = Read(addr, 4); return b == null ? 0f : BitConverter.ToSingle(b, 0); }
}
'@
[HH]::H = [HH]::OpenProcess(0x0410, $false, $game.Id)

# player position from the newest plugin log line
function Get-PlayerPos {
  $dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
  $f = Get-ChildItem $dir -Filter "AC.BlackFlag.PatchFix*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)") {
    return @([double]$Matches[1], [double]$Matches[2])
  }
  return $null
}

$manifest = Join-Path $OutDir "candidates.txt"
$window = 0x1000
$before = 0x300

if ($Phase -eq "find" -or $Phase -eq "snap") {
  $pp = Get-PlayerPos
  if (-not $pp) { "could not read player position"; exit 1 }
  "player ~ ({0:F1},{1:F1})" -f $pp[0], $pp[1]
  "scanning bodies (this takes a few seconds)..."
  $hits = [HH]::ScanBodies(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
  "raw vtable hits: " + $hits.Count
  $cands = @()
  foreach ($a in $hits) {
    $ch = [HH]::U16($a + 0x66)
    if ($ch -lt 16) { continue }
    $f7c = [HH]::F32($a + 0x7C)
    if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
    $x = [HH]::F32($a + 0x40); $y = [HH]::F32($a + 0x44)
    if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
    $d = [Math]::Sqrt([Math]::Pow($x - $pp[0], 2) + [Math]::Pow($y - $pp[1], 2))
    if ($d -gt $Radius -or $d -lt 2.5) { continue }
    $cands += ,@($a, $x, $y, $d, $ch)
  }
  $cands = $cands | Sort-Object { $_[3] }
  "candidates within $Radius m: " + $cands.Count
  $lines = @()
  foreach ($c in $cands) {
    $line = "{0:X8}  pos=({1:F1},{2:F1})  d={3:F1}  ch={4}" -f $c[0], $c[1], $c[2], $c[3], $c[4]
    $line
    $lines += ("{0:X8}" -f $c[0])
  }
  if ($Phase -eq "find") { $lines | Set-Content $manifest }
  if ($Phase -eq "snap") {
    $lines | Set-Content $manifest
    $i = 0
    foreach ($c in $cands) {
      $addr = [int64]$c[0]
      $buf = [HH]::Read($addr - $before, $window)
      if ($buf) {
        [System.IO.File]::WriteAllBytes((Join-Path $OutDir ("body_{0:X8}_{1}.bin" -f $addr, $Tag)), $buf)
        $i++
      }
    }
    "snapshotted $i bodies (- $before .. +$($window-$before) bytes each)"
    "(now hit the guard(s) in game, then run -Phase diff)"
  }
}

if ($Phase -eq "diff") {
  $addrs = Get-Content $manifest
  "comparing " + $addrs.Count + " bodies..."
  foreach ($s in $addrs) {
    $addr = [Convert]::ToInt64($s, 16)
    $file = Join-Path $OutDir ("body_{0:X8}_{1}.bin" -f $addr, $Tag)
    if (-not (Test-Path $file)) { continue }
    $old = [System.IO.File]::ReadAllBytes($file)
    $new = [HH]::Read($addr - $before, $window)
    if (-not $new) { "  {0:X8}: unreadable now" -f $addr; continue }
    $reports = @()
    for ($o = 0; $o + 4 -le $old.Length; $o += 4) {
      $u1 = [BitConverter]::ToUInt32($old, $o); $u2 = [BitConverter]::ToUInt32($new, $o)
      if ($u2 -lt $u1 -and ($u1 - $u2) -ge 1 -and ($u1 - $u2) -le 5000 -and $u1 -ne 0) {
        $f1 = [BitConverter]::ToSingle($old, $o); $f2 = [BitConverter]::ToSingle($new, $o)
        $asF = "  (f: {0:F2} -> {1:F2})" -f $f1, $f2
        $reports += ("    +0x{0:X4}: u32 {1} -> {2}   delta={3}{4}" -f ($o - $before), $u1, $u2, ($u1-$u2), $asF)
      }
    }
    if ($reports.Count -gt 0) {
      "  {0:X8}:" -f $addr
      $reports | Select-Object -First 12 | ForEach-Object { $_ }
    }
  }
  "done - the field that dropped on the guard you hit is the health (confirm with a second hit)"
}
