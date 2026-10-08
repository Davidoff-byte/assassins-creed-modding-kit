# ai-chain.ps1 - for each NPC body in radius: find its AI/service holder (first valid pointer offset
# whose +0x70 vec holds >=4 vt-valid service pointers). Report service lists + health-like elements.
param(
  [double]$Radius = 120,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ai",
  [string]$InspectBody = ""
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class AIC {
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
[AIC]::H = [AIC]::OpenProcess(0x0410, $false, $game.Id)

$VtLo = [uint32]0x01E00000; $VtHi = [uint32]0x02ACD814
$vtf = "C:\Users\Administrator\bf4_re\analysis\vtables_sp.txt"
if (Test-Path $vtf) {
  $mn = [uint32]::MaxValue; $mx = [uint32]0
  foreach ($l in [System.IO.File]::ReadLines($vtf)) { if ($l -match '^VT ([0-9a-fA-F]{8})') { $v = [Convert]::ToUInt32($Matches[1], 16); if ($v -lt $mn) { $mn = $v }; if ($v -gt $mx) { $mx = $v } } }
  if ($mx -gt 0) { $VtLo = [uint32]([int64]$mn - 0x10000); $VtHi = [uint32]([int64]$mx + 0x10000) }
}
"vtable window: {0:X8} .. {1:X8}" -f $VtLo, $VtHi

$ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$px = 0.0; $py = 0.0; $havePos = $false
if ($f) {
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2]; $havePos = $true }
}
"player ~ ($px,$py)"
$bodies = @()
$rawB = [AIC]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
foreach ($h in $rawB) {
  $ch = [AIC]::U16($h + 0x66); if ($ch -lt 16) { continue }
  $f7c = [AIC]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
  $x = [AIC]::F32($h + 0x40); $y = [AIC]::F32($h + 0x44)
  $d = -1.0
  if ($havePos) { $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2)) }
  if ($Radius -gt 0 -and $d -gt $Radius) { continue }
  $bodies += ,@($h, $x, $y, $d)
}
"bodies in radius: $($bodies.Count)"

$offs = New-Object System.Collections.Generic.List[int]
foreach ($o in @(0x114, 0xE8, 0x118, 0x110, 0x10C)) { $offs.Add($o) }
for ($o = 0; $o -lt 0x1F0; $o += 4) { if (-not $offs.Contains($o)) { $offs.Add($o) } }

$report = @()
$vtHist = @{}
$hit = 0; $noHit = 0

function Probe-Holder([long]$P, [string]$why) {
  foreach ($szOff in @(0x76, 0x74)) {
    $base = [AIC]::U32($P + 0x70); $size = [AIC]::U16($P + $szOff)
    if ($base -lt 0x10000000 -or $base -gt 0x7FFF0000 -or ($base -band 3) -ne 0) { continue }
    if ($size -lt 4 -or $size -gt 300) { continue }
    $n = [Math]::Min($size, 64)
    $buf = [AIC]::Read($base, $n * 4); if ($buf -eq $null) { continue }
    $nn = 0; $vtOk = 0; $elems = @()
    for ($i = 0; $i -lt $n; $i++) {
      $e = [BitConverter]::ToUInt32($buf, $i * 4); if ($e -eq 0) { continue }
      if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000 -or ($e -band 3) -ne 0) { continue }
      $nn++
      $eb = [AIC]::Read($e, 0x64); if ($eb -eq $null) { continue }
      $vt = [BitConverter]::ToUInt32($eb, 0)
      if ($vt -ge $VtLo -and $vt -le $VtHi) { $vtOk++ }
      $L = [BitConverter]::ToUInt16($eb, 0x5A); $M = [BitConverter]::ToUInt16($eb, 0x5C)
      $lim = [BitConverter]::ToUInt16($eb, 0x5E); $fl = [BitConverter]::ToUInt32($eb, 0x60)
      $elems += ,@($e, $vt, $L, $M, $lim, $fl)
    }
    if ($nn -ge 4 -and $vtOk -ge [int]($nn * 0.9)) {
      return ,@{base = $base; size = $size; szOff = $szOff; nn = $nn; vtOk = $vtOk; elems = $elems; why = $why }
    }
  }
  return $null
}

foreach ($b in ($bodies | Sort-Object { $_[3] })) {
  $body = $b[0]; $dist = $b[3]
  $res = $null
  foreach ($o in $offs) {
    $P = [AIC]::U32($body + $o)
    if ($P -lt 0x10000000 -or $P -gt 0x7FFF0000 -or ($P -band 3) -ne 0) { continue }
    $r = Probe-Holder $P ("+0x{0:X}" -f $o)
    if ($r -ne $null) { $r["off"] = $o; $r["P"] = $P; $res = $r; break }
  }
  if ($res -eq $null) { $noHit++; continue }
  $hit++
  $P = $res["P"]
  $pvt = [AIC]::U32($P); $fC = [AIC]::U32($P + 0xC); $f58 = [AIC]::U32($P + 0x58)
  $hl = @()
  foreach ($e in $res["elems"]) {
    $ea = $e[0]; $vt = $e[1]; $L = $e[2]; $M = $e[3]; $lim = $e[4]; $fl = $e[5]
    if ($M -ge 2 -and $M -le 5000 -and $L -le $M) {
      $hl += ("{0:X8}(L{1}/M{2},lim{3},fl{4:X8},vt{5:X8})" -f $ea, $L, $M, $lim, $fl, $vt)
      if ($vtHist.ContainsKey($vt)) { $vtHist[$vt]++ } else { $vtHist[$vt] = 1 }
    }
  }
  $line = "BODY {0:X8} d={1:F1} {2} P={3:X8} pvt={4:X8} fC={5:X8} f58={6:X8} vec={7}@{8:X} nn={9} vtok={10} HLTH[{11}]" -f $body, $dist, $res["why"], $P, $pvt, $fC, $f58, $res["size"], $res["szOff"], $res["nn"], $res["vtOk"], ($hl -join '; ')
  $line
  $report += $line
  $report += ("  elems: " + (($res["elems"] | ForEach-Object { "{0:X8}/vt{1:X8}/L{2}M{3}" -f $_[0], $_[1], $_[2], $_[3] }) -join ' '))
  if ($InspectBody -ne "" -and $body -eq [Convert]::ToInt64($InspectBody, 16)) {
    "=== inspect body $InspectBody ==="
    $mem = [AIC]::Read($body, 0x140)
    if ($mem) { for ($o = 0x100; $o -lt 0x140; $o += 0x40) { $hex = ($mem[$o..($o + 0x3F)] | ForEach-Object { $_.ToString("X2") }) -join ' '; "  +{0:X3}: {1}" -f $o, $hex } }
    if ($fC -gt 0x10000) { $m2 = [AIC]::Read($fC, 0x80); if ($m2) { $hex = ($m2 | ForEach-Object { $_.ToString("X2") }) -join ' '; "  fC({0:X8}): {1}" -f $fC, $hex } }
    if ($f58 -gt 0x10000) { $m3 = [AIC]::Read($f58, 0x80); if ($m3) { $hex = ($m3 | ForEach-Object { $_.ToString("X2") }) -join ' '; "  f58({0:X8}): {1}" -f $f58, $hex } }
  }
}
"hit bodies: $hit ; no-chain: $noHit"
"--- vt histogram (health-like elements) ---"
$vtHist.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 30 | ForEach-Object { "vt={0:X8} x{1}" -f [uint32]$_.Key, $_.Value }
$out = Join-Path $OutDir "ai_chain_report.txt"
$report | Set-Content $out
"saved -> $out"
