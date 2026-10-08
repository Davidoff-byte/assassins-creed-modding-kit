# probe-body-services.ps1 - for nearby bodies, one hop over their pointers, check every candidate
# for the PC service vec pair (base@+0x68/size@+0x6E and base@+0x70/size@+0x76, plus alt size offsets).
param(
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ai",
  [switch]$Hop2,
  [string]$Inspect = ""
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class PSB {
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
        if (BitConverter.ToUInt32(buf, i) == pattern) found.Add(p + i);
      }
    }
    return found;
  }
}
'@
[PSB]::H = [PSB]::OpenProcess(0x0410, $false, $game.Id)

$VtLo = [uint32]0x01E00000; $VtHi = [uint32]0x02ACD814
$vtf = "C:\Users\Administrator\bf4_re\analysis\vtables_sp.txt"
if (Test-Path $vtf) {
  $mn = [uint32]::MaxValue; $mx = [uint32]0
  foreach ($l in [System.IO.File]::ReadLines($vtf)) { if ($l -match '^VT ([0-9a-fA-F]{8})') { $v = [Convert]::ToUInt32($Matches[1], 16); if ($v -lt $mn) { $mn = $v }; if ($v -gt $mx) { $mx = $v } } }
  if ($mx -gt 0) { $VtLo = [uint32]([int64]$mn - 0x10000); $VtHi = [uint32]([int64]$mx + 0x10000) }
}
"vtable window: {0:X8} .. {1:X8}" -f $VtLo, $VtHi

function Check-Container([long]$P, [string]$tag) {
  $res = @()
  foreach ($spec in @(@(0x68, 0x6E), @(0x68, 0x6C), @(0x70, 0x76), @(0x70, 0x74))) {
    $base = [PSB]::U32($P + $spec[0]); $size = [PSB]::U16($P + $spec[1])
    if ($base -lt 0x10000000 -or $base -gt 0x7FFF0000 -or ($base -band 3) -ne 0) { continue }
    if ($size -lt 1 -or $size -gt 64) { continue }
    $buf = [PSB]::Read($base, $size * 4); if ($buf -eq $null) { continue }
    $vtok = 0; $nn = 0; $health = @()
    for ($i = 0; $i -lt $size; $i++) {
      $e = [BitConverter]::ToUInt32($buf, $i * 4); if ($e -eq 0) { continue }
      if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000) { continue }
      $nn++
      $eb = [PSB]::Read($e, 0x64); if ($eb -eq $null) { continue }
      $vt = [BitConverter]::ToUInt32($eb, 0)
      if ($vt -ge $VtLo -and $vt -le $VtHi) { $vtok++ }
      $life = [BitConverter]::ToUInt16($eb, 0x5A); $maxl = [BitConverter]::ToUInt16($eb, 0x5C)
      if ($maxl -ge 10 -and $maxl -le 5000 -and $life -le $maxl) {
        $health += ("{0:X8}(L{1}/M{2},vt{3:X8})" -f $e, $life, $maxl, $vt)
      }
    }
    if ($nn -gt 0 -and $vtok -ge [Math]::Max(1, [int]($nn * 0.8))) {
      $res += ("{0} vec@+0x{1:X} size={2} nn={3} vt={4} health=[{5}]" -f $tag, $spec[0], $size, $nn, $vtok, ($health -join '; '))
    }
  }
  return $res
}

if ($Inspect -ne "") {
  foreach ($a in $Inspect.Split(',')) {
    $addr = [Convert]::ToInt64($a, 16)
    "=== inspect {0:X8} ===" -f $addr
    $mem = [PSB]::Read($addr, 0x2C0)
    if ($mem -eq $null) { " unreadable"; continue }
    for ($o = 0; $o -lt 0x2C0; $o += 0x40) {
      $hex = ($mem[$o..([Math]::Min($o + 0x3F, 0x2BF))] | ForEach-Object { $_.ToString("X2") }) -join ' '
      "  +{0:X3}: {1}" -f $o, $hex
    }
    foreach ($t in (Check-Container $addr "self")) { " SELF $t" }
    # also follow a few interesting offsets as containers
    foreach ($o in @(0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0xE0, 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0xF8, 0xFC, 0x100)) {
      $p = [PSB]::U32($addr + $o)
      if ($p -lt 0x10000000 -or $p -gt 0x7FFF0000 -or ($p -band 3) -ne 0) { continue }
      foreach ($t in (Check-Container $p ("+0x{0:X}" -f $o))) { "  HOP $t" }
    }
  }
  exit 0
}

# ---- bodies near player
$ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$px = 0.0; $py = 0.0; $havePos = $false
if ($f) {
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2]; $havePos = $true }
}
"player ~ ($px,$py)"
$bodies = @()
$rawB = [PSB]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
foreach ($h in $rawB) {
  $ch = [PSB]::U16($h + 0x66); if ($ch -lt 16) { continue }
  $f7c = [PSB]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
  $x = [PSB]::F32($h + 0x40); $y = [PSB]::F32($h + 0x44)
  $d = -1.0
  if ($havePos) { $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2)) }
  $bodies += ,@($h, $x, $y, $d)
}
$all = @()
foreach ($b in ($bodies | Sort-Object { $_[3] })) {
  $body = $b[0]; $dist = $b[3]
  $ps = @()
  $ps += ,@("self", [int64]$body)
  for ($o = 0; $o -lt 0x1D0; $o += 4) {
    $p = [PSB]::U32($body + $o)
    if ($p -lt 0x10000000 -or $p -gt 0x7FFF0000 -or ($p -band 3) -ne 0) { continue }
    if ($p -eq $body) { continue }
    $ps += ,@(("+0x{0:X}" -f $o), [int64]$p)
  }
  $hitLines = @()
  foreach ($pair in $ps) {
    $r = Check-Container $pair[1] $pair[0]
    foreach ($x in $r) {
      $line = ("BODY {0:X8} d={1:F1} :: {2}" -f $body, $dist, $x)
      $hitLines += $line
      $all += $line
    }
  }
  if ($hop2) {
    foreach ($pair in $ps) {
      $pvt = [PSB]::U32($pair[1])
      if ($pvt -lt $VtLo -or $pvt -gt $VtHi) { continue }
      for ($o2 = 0; $o2 -lt 0x120; $o2 += 4) {
        $p2 = [PSB]::U32($pair[1] + $o2)
        if ($p2 -lt 0x10000000 -or $p2 -gt 0x7FFF0000 -or ($p2 -band 3) -ne 0) { continue }
        foreach ($t in (Check-Container $p2 ($pair[0] + "->+0x{0:X}" -f $o2))) {
          $line = ("BODY {0:X8} d={1:F1} :: {2}" -f $body, $dist, $t)
          $hitLines += $line
          $all += $line
        }
      }
    }
  }
  if ($hitLines.Count -gt 0) {
    "BODY {0:X8} ({1:F1},{2:F1}) d={3:F1}" -f $body, $b[1], $b[2], $dist
    $hitLines | ForEach-Object { "   " + $_ }
  }
}
"bodies scanned: $($bodies.Count) ; container hits: $($all.Count)"
$out = Join-Path $OutDir "body_service_hits.txt"
$all | Set-Content $out
"saved -> $out"
