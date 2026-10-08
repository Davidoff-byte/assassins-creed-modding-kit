# scan-services.ps1 - find health-like service objects (vt in .rdata window, life/max u16 pair)
# Modes: scan | diff   (diff compares against the last scan)
param(
  [Parameter(Mandatory=$true)][ValidateSet("scan","diff")][string]$Mode,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\services"
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SS {
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
  // scan for u32 in [lo,hi) at 4-aligned offsets, then validate the +0x5A pair pattern inline
  public static List<long> ScanLike(long lo, long hi, uint vtlo, uint vthi, int chunk) {
    var found = new List<long>();
    var buf = new byte[chunk + 0x70];
    for (long p = lo; p < hi; p += chunk) {
      IntPtr r;
      int size = (int)Math.Min(chunk + 0x70, hi - p);
      if (!ReadProcessMemory(H, (IntPtr)p, buf, size, out r)) continue;
      for (int i = 0; i + 0x70 <= size; i += 4) {
        uint v = BitConverter.ToUInt32(buf, i);
        if (v < vtlo || v > vthi) continue;
        ushort life = BitConverter.ToUInt16(buf, i + 0x5A);
        ushort maxl = BitConverter.ToUInt16(buf, i + 0x5C);
        if (maxl < 10 || maxl > 3000) continue;
        if (life > maxl) continue;
        found.Add(p + i);
      }
    }
    return found;
  }
}
'@
[SS]::H = [SS]::OpenProcess(0x0410, $false, $game.Id)

$listFile = Join-Path $OutDir "services_snapshot.txt"

if ($Mode -eq "scan") {
  "scanning for health-service-like objects ..."
  $cands = [SS]::ScanLike(0x30000000, 0x50000000, 0x01E00000, 0x02600000, 0x800000)
  "candidates: " + $cands.Count
  $lines = @()
  foreach ($a in $cands) {
    $life = [SS]::U16($a + 0x5A)
    $maxl = [SS]::U16($a + 0x5C)
    $lim  = [SS]::U16($a + 0x5E)
    $fl   = [SS]::U32($a + 0x60)
    $vt   = [SS]::U32($a)
    $lines += ("{0:X8} vt={1:X8} life={2} max={3} lim={4} flags={5:X8}" -f $a, $vt, $life, $maxl, $lim, $fl)
  }
  $lines | Set-Content $listFile
  "saved " + $lines.Count + " -> " + $listFile
  $lines | Select-Object -First 20
}

if ($Mode -eq "diff") {
  $old = @{}
  foreach ($l in (Get-Content $listFile)) {
    $p = $l.Split(' ')
    $old[$p[0]] = [int]($p[2].Split('=')[1])
  }
  "old entries: " + $old.Count
  $cands = [SS]::ScanLike(0x30000000, 0x50000000, 0x01E00000, 0x02600000, 0x800000)
  "now: " + $cands.Count
  foreach ($a in $cands) {
    $key = "{0:X8}" -f $a
    if (-not $old.ContainsKey($key)) { continue }
    $life = [SS]::U16($a + 0x5A)
    if ($life -lt $old[$key]) {
      $maxl = [SS]::U16($a + 0x5C)
      $fl   = [SS]::U32($a + 0x60)
      "DROPPED {0}: life {1} -> {2}  (max={3} flags={4:X8})" -f $key, $old[$key], $life, $maxl, $fl
    }
  }
  "done"
}
