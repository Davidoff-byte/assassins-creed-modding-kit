# scan-classes.ps1 - scan memory for instances of given class vtables; print field rows.
param(
  [Parameter(Mandatory = $true)][string]$Vts,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\health",
  [int]$MaxPerClass = 10
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SC {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static ushort U16(long a) { var b = Read(a, 2); return b == null ? (ushort)0 : BitConverter.ToUInt16(b, 0); }
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
[SC]::H = [SC]::OpenProcess(0x0410, $false, $game.Id)

$ranges = @(@(0x00400000L, 0x0E000000L), @(0x0E000000L, 0x2E000000L), @(0x2E000000L, 0x31000000L), @(0x30000000L, 0x56000000L), @(0x56000000L, 0x80000000L), @(0x80000000L, 0xF0000000L), @(0xF0000000L, 0xFFF00000L), @(0xFFF00000L, 0xFFFF0000L))

foreach ($v in $Vts.Split(',')) {
  $vt = [Convert]::ToUInt32($v.Trim(), 16)
  $all = New-Object System.Collections.Generic.List[long]
  foreach ($r in $ranges) {
    $f = [SC]::ScanU32($r[0], $r[1], $vt, 0x800000)
    foreach ($x in $f) { if (-not $all.Contains($x)) { $all.Add($x) } }
  }
  "=== vt={0:X8}  count={1} ===" -f $vt, $all.Count
  $n = 0
  foreach ($h in $all) {
    if ($n -ge $MaxPerClass) { break }
    $n++
    $row = (0x40..0x70 | Where-Object { $_ % 2 -eq 0 } | ForEach-Object { "{0:X}={1}" -f $_, [SC]::U16($h + $_) }) -join ' '
    "  {0:X8}: {1}" -f $h, $row
  }
}
"done"
