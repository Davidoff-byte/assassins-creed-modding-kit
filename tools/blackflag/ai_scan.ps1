# ai_scan.ps1 - find service-group containers ("AI objects"): two vecs {begin@+0x68,size@+0x6E} and {begin@+0x70,size@+0x76}
# validates all elements (vtable in .rdata), finds health-shaped services, and body backlinks.
param(
  [long]$Lo = 0x30000000,
  [long]$Hi = 0x56000000,
  [int]$MaxCand = 3500,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ai"
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class AS {
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
  public static List<long> ScanAI(long lo, long hi, int chunk, uint lo32, uint hi32) {
    var found = new List<long>();
    var buf = new byte[chunk + 0x80];
    for (long p = lo; p < hi; p += chunk) {
      IntPtr r;
      int size = (int)Math.Min(chunk + 0x80, hi - p);
      if (!ReadProcessMemory(H, (IntPtr)p, buf, size, out r)) continue;
      for (int i = 0; i + 0x7C <= size; i += 4) {
        uint pA = BitConverter.ToUInt32(buf, i + 0x68);
        if (pA < lo32 || pA > hi32 || (pA & 3) != 0) continue;
        ushort sA = BitConverter.ToUInt16(buf, i + 0x6E);
        if (sA < 1 || sA > 64) continue;
        uint pB = BitConverter.ToUInt32(buf, i + 0x70);
        if (pB < lo32 || pB > hi32 || (pB & 3) != 0) continue;
        ushort sB = BitConverter.ToUInt16(buf, i + 0x76);
        if (sB < 1 || sB > 64) continue;
        found.Add(p + i);
        if (found.Count > 200000) return found;
      }
    }
    return found;
  }
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
[AS]::H = [AS]::OpenProcess(0x0410, $false, $game.Id)

# dynamic vtable window from the export
$VtLo = [uint32]0x01E00000; $VtHi = [uint32]0x02680000
$vtf = "C:\Users\Administrator\bf4_re\analysis\vtables_sp.txt"
if (Test-Path $vtf) {
  $mn = [uint32]::MaxValue; $mx = [uint32]0
  foreach ($l in [System.IO.File]::ReadLines($vtf)) { if ($l -match '^VT ([0-9a-fA-F]{8})') { $v = [Convert]::ToUInt32($Matches[1], 16); if ($v -lt $mn) { $mn = $v }; if ($v -gt $mx) { $mx = $v } } }
  if ($mx -gt 0) { $VtLo = [uint32]([int64]$mn - 0x10000); $VtHi = [uint32]([int64]$mx + 0x10000) }
}
"vtable window: {0:X8} .. {1:X8}" -f $VtLo, $VtHi

# ---- phase 0: bodies near player
$ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$px = 0.0; $py = 0.0; $havePos = $false
if ($f) {
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2]; $havePos = $true }
}
"player ~ ($px,$py) havePos=$havePos"
$bodies = @()
$rawB = [AS]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
foreach ($h in $rawB) {
  $ch = [AS]::U16($h + 0x66); if ($ch -lt 16) { continue }
  $f7c = [AS]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
  $x = [AS]::F32($h + 0x40); $y = [AS]::F32($h + 0x44)
  $d = -1.0
  if ($havePos) { $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2)) }
  $bodies += ,@($h, $x, $y, $d)
}
"bodies: $($bodies.Count) (raw vt hits $($rawB.Count))"
$bodies | Sort-Object { $_[3] } | Select-Object -First 12 | ForEach-Object { "  BODY {0:X8} ({1:F1},{2:F1}) d={3:F1}" -f $_[0], $_[1], $_[2], $_[3] }

# ---- phase 1: scan
"scanning AI candidates ..."
$cands = [AS]::ScanAI($Lo, $Hi, 0x800000, 0x10000000, 0x7FFF0000)
"raw AI candidates: $($cands.Count)"
$raw = Join-Path $OutDir "ai_candidates_raw.txt"
($cands | Select-Object -First 20000 | ForEach-Object { "{0:X8}" -f $_ }) | Set-Content $raw
"raw saved -> $raw"
"first raw: " + (($cands | Select-Object -First 10 | ForEach-Object { "{0:X8}" -f $_ }) -join ' ')

# ---- phase 2: validate
$okList = @()
$tested = 0
$kept = 0
foreach ($c in ($cands | Select-Object -First $MaxCand)) {
  $tested++
  if (($tested % 500) -eq 0) { "  ... tested $tested kept $kept" }
  $sA = [AS]::U16($c + 0x6E); $sB = [AS]::U16($c + 0x76)
  $pA = [AS]::U32($c + 0x68); $pB = [AS]::U32($c + 0x70)
  $bufA = [AS]::Read($pA, $sA * 4); $bufB = [AS]::Read($pB, $sB * 4)
  if ($bufA -eq $null -or $bufB -eq $null) { continue }
  $elemsA = @(); $elemsB = @()
  $bad = $false
  for ($i = 0; $i -lt $sA; $i++) {
    $e = [BitConverter]::ToUInt32($bufA, $i * 4)
    if ($e -eq 0) { $elemsA += [int64]0; continue }
    if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000 -or ($e -band 3) -ne 0) { $bad = $true; break }
    $elemsA += [int64]$e
  }
  if ($bad) { continue }
  for ($i = 0; $i -lt $sB; $i++) {
    $e = [BitConverter]::ToUInt32($bufB, $i * 4)
    if ($e -eq 0) { $elemsB += [int64]0; continue }
    if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000 -or ($e -band 3) -ne 0) { $bad = $true; break }
    $elemsB += [int64]$e
  }
  if ($bad) { continue }
  $nonNullA = 0; $nonNullB = 0; $vtOkA = 0; $vtOkB = 0
  $healthB = @()
  foreach ($e in $elemsA) {
    if ($e -eq 0) { continue }
    $nonNullA++
    $eb = [AS]::Read($e, 4)
    if ($eb -ne $null) { $vt = [BitConverter]::ToUInt32($eb, 0); if ($vt -ge $VtLo -and $vt -le $VtHi) { $vtOkA++ } }
  }
  foreach ($e in $elemsB) {
    if ($e -eq 0) { continue }
    $nonNullB++
    $eb = [AS]::Read($e, 0x64)
    if ($eb -eq $null) { continue }
    $vt = [BitConverter]::ToUInt32($eb, 0)
    if ($vt -ge $VtLo -and $vt -le $VtHi) { $vtOkB++ }
    $life = [BitConverter]::ToUInt16($eb, 0x5A); $maxl = [BitConverter]::ToUInt16($eb, 0x5C)
    if ($maxl -ge 10 -and $maxl -le 3000 -and $life -le $maxl) {
      $lim = [BitConverter]::ToUInt16($eb, 0x5E); $fl = [BitConverter]::ToUInt32($eb, 0x60)
      $healthB += ,@($e, $life, $maxl, $lim, $fl, $vt)
    }
  }
  if ($nonNullA -lt 1 -or $nonNullB -lt 1) { continue }
  if ($vtOkA -lt ($nonNullA * 0.9) -or $vtOkB -lt ($nonNullB * 0.9)) { continue }
  $kept++
  # body backlinks
  $bl = @()
  $mem = [AS]::Read($c, 0x600)
  if ($mem -ne $null -and $bodies.Count -gt 0) {
    for ($i = 0; $i -lt (0x600 - 3); $i += 4) {
      $v = [BitConverter]::ToUInt32($mem, $i)
      foreach ($b in $bodies) { if ($v -eq [uint32]$b[0]) { $bl += ("+0x{0:X} -> {1:X8} d={2:F1}" -f $i, $b[0], $b[3]) } }
    }
  }
  $line = "KEEP {0:X8} sA={1}({2} nn,{3} vt) sB={4}({5} nn,{6} vt) healthB={7} bodyLinks={8}" -f $c, $sA, $nonNullA, $vtOkA, $sB, $nonNullB, $vtOkB, $healthB.Count, $bl.Count
  $line
  $okList += $line
  foreach ($hh in $healthB) {
    "     health svc {0:X8} life={1} max={2} lim={3} flags={4:X8} vt={5:X8}" -f $hh[0], $hh[1], $hh[2], $hh[3], $hh[4], $hh[5]
  }
  if ($healthB.Count -gt 0) {
    $dump = [AS]::Read($c, 0x80)
    if ($dump) { $hex = ($dump | ForEach-Object { $_.ToString("X2") }) -join ' '; "     cand bytes: $hex" }
  }
  if ($bl.Count -gt 0) { foreach ($b in $bl) { "     bodylink $b" } }
}
"tested=$tested kept=$kept"
$out = Join-Path $OutDir "ai_candidates.txt"
$okList | Set-Content $out
"saved -> $out"
