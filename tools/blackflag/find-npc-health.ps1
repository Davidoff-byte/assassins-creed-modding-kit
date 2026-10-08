# find-npc-health.ps1 - walk body -> (container) -> services[] -> health service
# and report candidate NPC health objects (Life u16 @+0x5A, MaxLife u16 @+0x5C, flags u32 @+0x60).
param(
  [int]$Radius = 30,
  [string]$Addr = ""
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class NH {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static uint U32(long a) { var b = Read(a, 4); return b == null ? 0 : BitConverter.ToUInt32(b, 0); }
  public static ushort U16(long a) { var b = Read(a, 2); return b == null ? (ushort)0 : BitConverter.ToUInt16(b, 0); }
  public static float F32(long a) { var b = Read(a, 4); return b == null ? 0f : BitConverter.ToSingle(b, 0); }
  public static List<long> ScanVt(long lo, long hi, uint pattern, int chunk) {
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
}
'@
[NH]::H = [NH]::OpenProcess(0x0410, $false, $game.Id)

function Get-Ptrs([long]$base, [int]$size) {
  $ptrs = @()
  for ($o = 0; $o -lt $size; $o += 4) {
    $v = [NH]::U32($base + $o)
    if ($v -gt 0x10000 -and $v -lt 0x7FFF0000 -and ($v % 4) -eq 0) { $ptrs += ,@($o, [int64]$v) }
  }
  return $ptrs
}

function Probe-Container([long]$p) {
  $found = @()
  foreach ($countOff in @(0x76, 0x74)) {
    $arr = [NH]::U32($p + 0x70)
    $cnt = [NH]::U16($p + $countOff)
    if ($arr -gt 0x10000 -and $arr -lt 0x7FFF0000 -and $cnt -ge 1 -and $cnt -le 64) {
      for ($i = 0; $i -lt [Math]::Min($cnt, 48); $i++) {
        $s = [NH]::U32($arr + $i * 4)
        if ($s -lt 0x10000 -or $s -gt 0x7FFF0000) { continue }
        $svt = [NH]::U32($s)
        if ($svt -lt 0x1E00000 -or $svt -gt 0x2600000) { continue }   # vtable in .rdata window
        $life = [NH]::U16($s + 0x5A)
        $maxl = [NH]::U16($s + 0x5C)
        $lim  = [NH]::U16($s + 0x5E)
        $fl   = [NH]::U32($s + 0x60)
        if ($maxl -ge 10 -and $maxl -le 3000 -and $life -le $maxl) {
          $found += ("container 0x{0:X8} cnt@{1:X} svc[{2}] 0x{3:X8} vt=0x{4:X8} life={5} max={6} lim={7} flags=0x{8:X8}" -f $p, $countOff, $i, $s, $svt, $life, $maxl, $lim, $fl)
        }
      }
    }
  }
  return $found
}

function Probe-Body([long]$body) {
  $found = @()
  $probed = 0
  foreach ($pair in (Get-Ptrs $body 0x200)) {
    $off = $pair[0]; $p = $pair[1]
    $r1 = Probe-Container $p
    $probed++
    foreach ($x in $r1) { $found += ("body+0x{0:X2} -> {1}" -f $off, $x) }
    if ($r1.Count -eq 0 -and $probed -lt 300) {
      foreach ($pair2 in (Get-Ptrs $p 0x120)) {
        $off2 = $pair2[0]; $p2 = $pair2[1]
        $r2 = Probe-Container $p2
        $probed++
        foreach ($x in $r2) { $found += ("body+0x{0:X2} -> +0x{1:X2} -> {2}" -f $off, $off2, $x) }
        if ($probed -ge 300) { break }
      }
    }
  }
  return $found
}

if ($Addr -ne "") {
  $b = [Convert]::ToInt64($Addr, 16)
  "--- probes for body 0x$($Addr.ToUpper()) ---"
  Probe-Body $b
} else {
  "scanning bodies within $Radius m ..."
  # player pos from the log
  $dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
  $f = Get-ChildItem $dir -Filter "AC.BlackFlag.PatchFix*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  $px = 0.0; $py = 0.0
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2] }
  "player ~ ($px,$py)"
  $hits = [NH]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
  "raw hits: " + $hits.Count
  foreach ($h in $hits) {
    $ch = [NH]::U16($h + 0x66)
    if ($ch -lt 16) { continue }
    $f7c = [NH]::F32($h + 0x7C)
    if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
    $x = [NH]::F32($h + 0x40); $y = [NH]::F32($h + 0x44)
    $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2))
    if ($d -gt $Radius -or $d -lt 2.5) { continue }
    $res = Probe-Body $h
    if ($res.Count -gt 0) {
      "BODY 0x{0:X8} at ({1:F1},{2:F1}) d={3:F1}" -f $h, $x, $y, $d
      $res | ForEach-Object { "   " + $_ }
    }
  }
  "done"
}
