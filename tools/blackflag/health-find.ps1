# health-find.ps1 - locate CSrvNPCHealth instances (vt=02712F60) and the body->service chain.
param(
  [ValidateSet("list", "diff", "chains", "fulldump", "fulldiff")][string]$Mode = "list",
  [double]$Radius = 120,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\health"
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class HF {
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
[HF]::H = [HF]::OpenProcess(0x0410, $false, $game.Id)

$HEALTH_VT = [uint32]0x02712F60
$snap = Join-Path $OutDir "health_instances.txt"

if ($Mode -eq "list") {
  $ranges = @(@(0x0E000000L, 0x2E000000L), @(0x2E000000L, 0x31000000L), @(0x30000000L, 0x56000000L), @(0x56000000L, 0x80000000L), @(0x80000000L, 0xF0000000L), @(0xF0000000L, 0xFFF00000L))
  $hits = New-Object System.Collections.Generic.List[long]
  foreach ($r in $ranges) {
    $found = [HF]::ScanU32($r[0], $r[1], $HEALTH_VT, 0x800000)
    foreach ($f in $found) { if (-not $hits.Contains($f)) { $hits.Add($f) } }
  }
  "instances: $($hits.Count)"
  $lines = @()
  foreach ($h in $hits) {
    $A = [HF]::U16($h + 0x5A); $LIFE = [HF]::U16($h + 0x5C); $MAX = [HF]::U16($h + 0x5E); $fl = [HF]::U32($h + 0x60)
    $mark = ""
    if ($LIFE -lt $MAX) { $mark = "  *** WOUNDED ***" }
    $lines += ("{0:X8} +5A={1} LIFE={2} MAX={3} fl={4:X8}{5}" -f $h, $A, $LIFE, $MAX, $fl, $mark)
  }
  $lines | Set-Content $snap
  "saved -> $snap"
  $lines | Select-Object -First 40
  "--- header dump of first 3 instances ---"
  foreach ($h in ($hits | Select-Object -First 3)) {
    $b = [HF]::Read($h, 0x50)
    if ($b) {
      "OBJ {0:X8}: {1}" -f $h, (($b | ForEach-Object { $_.ToString("X2") }) -join ' ')
      "   ptrs: +4={0:X8} +8={1:X8} +C={2:X8} +10={3:X8} +14={4:X8} +18={5:X8}" -f ([HF]::U32($h + 4)), ([HF]::U32($h + 8)), ([HF]::U32($h + 0xC)), ([HF]::U32($h + 0x10)), ([HF]::U32($h + 0x14)), ([HF]::U32($h + 0x18))
      $us = (0x40..0x70 | Where-Object { $_ % 2 -eq 0 } | ForEach-Object { "{0:X}={1}" -f $_, [HF]::U16($h + $_) }) -join ' '
      "   u16s +40..+70: $us"
    }
  }
  exit 0
}

if ($Mode -eq "diff") {
  $old = @{}
  foreach ($l in (Get-Content $snap)) {
    $p = $l.Split(' ')
    $old[$p[0]] = [int]($p[1].Split('=')[1])
  }
  "old entries: $($old.Count)"
  $hits = [HF]::ScanU32(0x30000000, 0x56000000, $HEALTH_VT, 0x800000)
  "now: $($hits.Count)"
  foreach ($h in $hits) {
    $key = "{0:X8}" -f $h
    if (-not $old.ContainsKey($key)) { continue }
    $L = [HF]::U16($h + 0x5A)
    if ($L -lt $old[$key]) {
      $M = [HF]::U16($h + 0x5C); $fl = [HF]::U32($h + 0x60)
      "DROPPED {0}: L {1} -> {2} (M={3} fl={4:X8})" -f $key, $old[$key], $L, $M, $fl
    }
  }
  "done"
  exit 0
}

if ($Mode -eq "fulldump") {
  $hits = [HF]::ScanU32(0x30000000, 0x56000000, $HEALTH_VT, 0x800000)
  "instances: $($hits.Count)"
  $lines = @()
  foreach ($h in $hits) {
    $b = [HF]::Read($h, 0x78)
    if ($b -eq $null) { $lines += ("{0:X8} UNREADABLE" -f $h); continue }
    $lines += ("{0:X8} {1}" -f $h, (($b | ForEach-Object { $_.ToString("X2") }) -join ''))
  }
  $lines | Set-Content (Join-Path $OutDir "health_full.txt")
  "saved -> health_full.txt ($($lines.Count) lines)"
  exit 0
}

if ($Mode -eq "fulldiff") {
  $old = @{}
  foreach ($l in (Get-Content (Join-Path $OutDir "health_full.txt"))) {
    $p = $l.Split(' ')
    if ($p.Count -ge 2) { $old[$p[0]] = $p[1] }
  }
  "old: $($old.Count)"
  $hits = [HF]::ScanU32(0x30000000, 0x56000000, $HEALTH_VT, 0x800000)
  "now: $($hits.Count)"
  $nowSet = @{}
  foreach ($h in $hits) {
    $key = "{0:X8}" -f $h
    $nowSet[$key] = $true
    $b = [HF]::Read($h, 0x78)
    if ($b -eq $null) { continue }
    $hex = ($b | ForEach-Object { $_.ToString("X2") }) -join ''
    if (-not $old.ContainsKey($key)) { "NEW {0}" -f $key; continue }
    $o = $old[$key]
    if ($o -eq $hex) { continue }
    "CHANGED {0}" -f $key
    for ($i = 0; $i -lt ($hex.Length / 2); $i++) {
      $a = $hex.Substring($i * 2, 2); $b2 = $o.Substring($i * 2, 2)
      if ($a -ne $b2) { "   +0x{0:X2}: {1} -> {2}" -f $i, $b2, $a }
    }
    $u16s = @()
    for ($i = 0; $i -lt 0x78; $i += 2) {
      $av = [BitConverter]::ToUInt16([byte[]]@([Convert]::ToByte($hex.Substring($i * 2, 2), 16), [Convert]::ToByte($hex.Substring($i * 2 + 2, 2), 16)), 0)
      $u16s += ("{0:X}={1}" -f $i, $av)
    }
    "   now u16: " + ($u16s -join ' ')
  }
  foreach ($k in $old.Keys) { if (-not $nowSet.ContainsKey($k)) { "GONE $k" } }
  "done"
  exit 0
}

if ($Mode -eq "chains") {
  $ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
  $f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  $px = 0.0; $py = 0.0; $havePos = $false
  if ($f) {
    $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
    if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2]; $havePos = $true }
  }
  "player ~ ($px,$py)"
  $bodies = @()
  $rawB = [HF]::ScanU32(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
  foreach ($h in $rawB) {
    $ch = [HF]::U16($h + 0x66); if ($ch -lt 16) { continue }
    $f7c = [HF]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
    $x = [HF]::F32($h + 0x40); $y = [HF]::F32($h + 0x44)
    $d = -1.0
    if ($havePos) { $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2)) }
    if ($Radius -gt 0 -and $d -gt $Radius) { continue }
    $bodies += ,@($h, $x, $y, $d)
  }
  "bodies in radius: $($bodies.Count)"
  foreach ($b in ($bodies | Sort-Object { $_[3] })) {
    $body = $b[0]; $dist = $b[3]
    $found = $false
    for ($o = 0; $o -lt 0x1F0; $o += 4) {
      $P = [HF]::U32($body + $o)
      if ($P -lt 0x10000000 -or $P -gt 0x7FFF0000 -or ($P -band 3) -ne 0) { continue }
      foreach ($spec in @(@(0x70, 0x76), @(0x70, 0x74), @(0x68, 0x6E), @(0x68, 0x6C))) {
        $base = [HF]::U32($P + $spec[0]); $size = [HF]::U16($P + $spec[1])
        if ($base -lt 0x10000000 -or $base -gt 0x7FFF0000 -or ($base -band 3) -ne 0) { continue }
        if ($size -lt 1 -or $size -gt 300) { continue }
        $n = [Math]::Min($size, 64)
        $buf = [HF]::Read($base, $n * 4); if ($buf -eq $null) { continue }
        for ($i = 0; $i -lt $n; $i++) {
          $e = [BitConverter]::ToUInt32($buf, $i * 4); if ($e -eq 0) { continue }
          if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000) { continue }
          if ([HF]::U32($e) -eq $HEALTH_VT) {
            $L = [HF]::U16($e + 0x5A); $M = [HF]::U16($e + 0x5C)
            "BODY {0:X8} d={1:F1} off=+0x{2:X} P={3:X8} vec@+0x{4:X}[{5}] elem[{6}]={7:X8} HEALTH L={8} M={9}" -f $body, $dist, $o, $P, $spec[0], $size, $i, $e, $L, $M
            $found = $true
          }
        }
      }
      if ($found) { break }
    }
    if (-not $found) { "BODY {0:X8} d={1:F1} : no direct health link" -f $body, $dist }
  }
  "done"
  exit 0
}
