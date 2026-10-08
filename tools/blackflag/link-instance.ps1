# link-instance.ps1 - given a CSrvNPCHealth instance, find its owner NPC body (via the services
# container pointer at inst+0x20/+0x28 and a body scan).
param(
  [Parameter(Mandatory = $true)][string]$Inst,
  [double]$Radius = 200
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class LI {
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
[LI]::H = [LI]::OpenProcess(0x0410, $false, $game.Id)

$inst = [Convert]::ToInt64($Inst, 16)
"instance {0:X8}" -f $inst
$p1 = [LI]::U32($inst + 0x20)
$p2 = [LI]::U32($inst + 0x28)
"inst+0x20 = {0:X8} ; inst+0x28 = {1:X8}" -f $p1, $p2

$ph = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
$f = Get-ChildItem $ph -Filter "AC.BlackFlag.PatchFix*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$px = 0.0; $py = 0.0; $havePos = $false
if ($f) {
  $line = Select-String -Path $f.FullName -Pattern "PlayerTransform: pos=\(" | Select-Object -Last 1 | ForEach-Object { $_.Line }
  if ($line -match "pos=\(([-0-9.]+),([-0-9.]+),") { $px = [double]$Matches[1]; $py = [double]$Matches[2]; $havePos = $true }
}
"player ~ ($px,$py)"

$rawB = [LI]::ScanVt(0x30000000, 0x50000000, 0x01E4CE90, 0x800000)
$bodies = @()
foreach ($h in $rawB) {
  $ch = [LI]::U16($h + 0x66); if ($ch -lt 16) { continue }
  $f7c = [LI]::F32($h + 0x7C); if ([Math]::Abs($f7c + 0.5) -gt 0.05) { continue }
  $x = [LI]::F32($h + 0x40); $y = [LI]::F32($h + 0x44)
  $d = -1.0
  if ($havePos) { $d = [Math]::Sqrt([Math]::Pow($x - $px, 2) + [Math]::Pow($y - $py, 2)) }
  if ($Radius -gt 0 -and $d -gt $Radius) { continue }
  $bodies += ,@($h, $x, $y, $d)
}
"bodies: $($bodies.Count)"

foreach ($target in @($p1, $p2, [uint32]$inst)) {
  if ($target -lt 0x10000000 -or $target -gt 0x7FFF0000) { continue }
  "--- searching bodies for pointer to {0:X8} ---" -f $target
  foreach ($b in $bodies) {
    $body = $b[0]
    $mem = [LI]::Read($body, 0x300)
    if ($mem -eq $null) { continue }
    for ($o = 0; $o -lt (0x300 - 3); $o += 4) {
      $v = [BitConverter]::ToUInt32($mem, $o)
      if ($v -eq $target) {
        "  FOUND: BODY {0:X8} (d={1:F1} at {2:F1},{3:F1}) +0x{4:X} -> {5:X8}" -f $body, $b[3], $b[1], $b[2], $o, $target
      }
    }
  }
}
"done"
