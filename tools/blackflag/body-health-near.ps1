# body-health-near.ps1 - find NPCs near the player and link each body to its CSrvNPCHealth object
# via the services-container chain (body+off -> P -> vec -> CSrvNPCHealth element).
param(
  [double]$Radius = 25,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\health"
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class BH {
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
[BH]::H = [BH]::OpenProcess(0x0410, $false, $game.Id)

$HEALTH_VT = [uint32]0x02712F60
$ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$px = 0.0; $py = 0.0
if ($f) {
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2] }
}
"player ~ ($px,$py)"
if ($px -eq 0 -and $py -eq 0) { "player pos zero (respawning?) - abort"; exit 1 }

$rawB = [BH]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
$bodies = @()
foreach ($h in $rawB) {
  $ch = [BH]::U16($h + 0x66); if ($ch -lt 16) { continue }
  $f7c = [BH]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
  $x = [BH]::F32($h + 0x40); $y = [BH]::F32($h + 0x44)
  $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2))
  if ($Radius -gt 0 -and $d -gt $Radius) { continue }
  $bodies += ,@($h, $x, $y, $d)
}
"bodies within $Radius m: $($bodies.Count)"

$offs = New-Object System.Collections.Generic.List[int]
foreach ($o in @(0x114, 0xE8, 0x118, 0x110, 0x10C)) { $offs.Add($o) }
for ($o = 0; $o -lt 0x1F0; $o += 4) { if (-not $offs.Contains($o)) { $offs.Add($o) } }

foreach ($b in ($bodies | Sort-Object { $_[3] })) {
  $body = $b[0]; $dist = $b[3]
  $found = $null
  foreach ($o in $offs) {
    $P = [BH]::U32($body + $o)
    if ($P -lt 0x10000000 -or $P -gt 0x7FFF0000 -or ($P -band 3) -ne 0) { continue }
    foreach ($spec in @(@(0x70, 0x76), @(0x70, 0x74), @(0x68, 0x6E), @(0x68, 0x6C))) {
      $base = [BH]::U32($P + $spec[0]); $size = [BH]::U16($P + $spec[1])
      if ($base -lt 0x10000000 -or $base -gt 0x7FFF0000 -or ($base -band 3) -ne 0) { continue }
      if ($size -lt 1 -or $size -gt 300) { continue }
      $n = [Math]::Min($size, 64)
      $buf = [BH]::Read($base, $n * 4); if ($buf -eq $null) { continue }
      for ($i = 0; $i -lt $n; $i++) {
        $e = [BitConverter]::ToUInt32($buf, $i * 4); if ($e -eq 0) { continue }
        if ($e -lt 0x10000000 -or $e -gt 0x7FFF0000) { continue }
        if ([BH]::U32($e) -eq $HEALTH_VT) {
          $L = [BH]::U16($e + 0x5C); $M = [BH]::U16($e + 0x5E)
          $found = "health={0:X8} LIFE={1} MAX={2} (body+0x{3:X} -> P={4:X8})" -f $e, $L, $M, $o, $P
          break
        }
      }
      if ($found) { break }
    }
    if ($found) { break }
  }
  if ($found) {
    "BODY {0:X8} ({1:F1},{2:F1}) d={3:F1}  ->  {4}" -f $body, $b[1], $b[2], $dist, $found
  } else {
    "BODY {0:X8} ({1:F1},{2:F1}) d={3:F1}  ->  (no health link)" -f $body, $b[1], $b[2], $dist
  }
}
"done"
