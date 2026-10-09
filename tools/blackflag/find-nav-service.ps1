# find-nav-service.ps1 - locate live CSrvNavigation service instances.
# Strategy: scan for character bodies (vt 0x01E4CE90 + marker), walk body+0x114 -> P,
# walk the service vectors at P+0x68 / P+0x70, resolve each service's class id via the
# vt+0x14 descriptor stub, and report services whose id == 0x6328D910 (CSrvNavigation).
# Read-only.
param([long]$ScanLo = 0x30000000, [long]$ScanHi = 0x50000000, [int]$MaxBodies = 40)

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class FNS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size]; IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static uint U32(long a) { var b = Read(a, 4); return b == null ? 0 : BitConverter.ToUInt32(b, 0); }
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
[FNS]::H = [FNS]::OpenProcess(0x0410, $false, $game.Id)
"pid $($game.Id) opened"

# crc names for ids we care about
$nameMap = @{}
foreach ($l in [System.IO.File]::ReadLines("C:\Users\Administrator\Documents\Default Project\bf-coop\logs\crc_all.txt")) {
  $p = $l.Split("`t")
  if ($p.Count -ge 2) { $nameMap[$p[0].ToLower()] = $p[1] }
}
function RN([uint32]$id) { $k = ("{0:x8}" -f $id); if ($nameMap.ContainsKey($k)) { return $nameMap[$k] } return "?" }

function Read-Desc([long]$stub, [long]$obj) {
  $hops = 0
  while ($hops -lt 4) {
    $hops++
    if ($stub -lt 0x401000 -or $stub -gt 0x2B00000) { return 0 }
    $code = [FNS]::Read($stub, 12)
    if ($code -eq $null) { return 0 }
    if ($code[0] -eq 0xE9) {
      $rel = [BitConverter]::ToInt32($code, 1)
      $stub = $stub + 5 + $rel
      continue
    }
    break
  }
  if ($code[0] -eq 0xA1) { $g = [BitConverter]::ToUInt32($code, 1); return [FNS]::U32($g) }
  if ($code[0] -eq 0xB8) { return [uint32][BitConverter]::ToUInt32($code, 1) }
  if ($code[0] -eq 0x8B -and $code[1] -eq 0x41 -and $code[3] -eq 0xC3 -and $obj -gt 0) {
    return [FNS]::U32($obj + $code[2])
  }
  return 0
}
function ResolveId([long]$obj) {
  $vt = [FNS]::U32($obj)
  if ($vt -lt 0x1800000 -or $vt -gt 0x2B00000) { return $null }
  $fn = [FNS]::U32($vt + 0x14)
  $desc = Read-Desc $fn $obj
  if ($desc -eq 0) { return $null }
  $id = [FNS]::U32($desc + 0x14)
  return @{ vt = $vt; fn = $fn; desc = $desc; id = $id }
}

"scanning bodies in [$('{0:X8}' -f $ScanLo)..$('{0:X8}' -f $ScanHi)]..."
$cands = [FNS]::ScanU32($ScanLo, $ScanHi, 0x01E4CE90, 0x800000)
"body vtable hits: $($cands.Count)"
$bodies = @()
foreach ($c in $cands) {
  if ([FNS]::U32($c + 0x68) -ne 0x04DD5F8C) { continue }
  if ([FNS]::U16($c + 0x66) -lt 8) { continue }
  $bodies += $c
  if ($bodies.Count -ge $MaxBodies) { break }
}
"valid bodies: $($bodies.Count)"

$TARGET_ID = [uint32]0x6328D910
foreach ($b in $bodies) {
  $P = [FNS]::U32($b + 0x114)
  if ($P -lt 0x10000) { continue }
  foreach ($vecOff in @(0x70, 0x68)) {
    $base = [FNS]::U32($P + $vecOff)
    $size = [FNS]::U16($P + $vecOff + 6)
    if ($base -lt 0x10000 -or $size -lt 2 -or $size -gt 200) { continue }
    for ($i = 0; $i -lt $size; $i++) {
      $svc = [FNS]::U32($base + $i * 4)
      if ($svc -lt 0x10000) { continue }
      $r = ResolveId $svc
      if ($r -eq $null) { continue }
      if ($r.id -eq $TARGET_ID) {
        "================ FOUND CSrvNavigation ================"
        "body=0x{0:X8} P=0x{1:X8} vecOff=0x{2:X2} idx={3} service=0x{4:X8}" -f $b, $P, $vecOff, $i, $svc
        "vt=0x{0:X8} desc=0x{1:X8} id=0x{2:X8} name={3}" -f $r.vt, $r.desc, $r.id, (RN $r.id)
        $slot8  = [FNS]::U32($r.vt + 8 * 4)
        $slot20 = [FNS]::U32($r.vt + 20 * 4)
        $slot21 = [FNS]::U32($r.vt + 21 * 4)
        $slot54 = [FNS]::U32($r.vt + 54 * 4)
        $slot76 = [FNS]::U32($r.vt + 76 * 4)
        "slot8(ClassDesc?)=0x{0:X8}  slot20(NavCancel?)=0x{1:X8}  slot21(GetNavCommands?)=0x{2:X8}" -f $slot8, $slot20, $slot21
        "slot54(NavigateToNavTarget?)=0x{0:X8}  slot76(IsTargetReached?)=0x{1:X8}" -f $slot54, $slot76
        $b54 = [FNS]::Read($slot54, 16)
        if ($b54) { "slot54 bytes: " + (($b54 | ForEach-Object { $_.ToString('X2') }) -join ' ') }
        $inst = [FNS]::Read($svc, 0x40)
        if ($inst) { "instance hdr: " + (($inst | ForEach-Object { $_.ToString('X2') }) -join ' ') }
        $pat = [FNS]::U32($svc + 0x84)
        "pattern ptr @svc+0x84 = 0x$('{0:X8}' -f $pat)"
        if ($pat -gt 0x10000) { $pr = ResolveId $pat; if ($pr) { "pattern class: vt=0x$('{0:X8}' -f $pr.vt) id=0x$('{0:X8}' -f $pr.id) name=$(RN $pr.id)" } }
        $s160 = [FNS]::U32($svc + 0x160)
        "svc+0x160 = 0x$('{0:X8}' -f $s160)"
        exit 0
      }
    }
  }
}
"CSrvNavigation instance not found in $($bodies.Count) bodies (tried both vectors)"
