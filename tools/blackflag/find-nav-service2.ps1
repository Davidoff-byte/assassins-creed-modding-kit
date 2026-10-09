# find-nav-service2.ps1 - locate live CSrvNavigation instances via known CSrvNPCHealth anchors.
# Chain: CSrvNPCHealth instances (vt 0x02712F60) -> owner back-link +0x20/+0x28 -> P (services
# container) -> vector base@P+0x70 size@P+0x76 (also +0x68/+0x6E) -> resolve each service class id
# via the vt+0x14 descriptor stub -> report CSrvNavigation (id 0x6328D910).
# Read-only.
param([long]$ScanLo = 0x2E000000, [long]$ScanHi = 0x56000000, [int]$MaxHealth = 60)

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class FNS2 {
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
[FNS2]::H = [FNS2]::OpenProcess(0x0410, $false, $game.Id)
"pid $($game.Id) opened"

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
    $code = [FNS2]::Read($stub, 12)
    if ($code -eq $null) { return 0 }
    if ($code[0] -eq 0xE9) {
      $rel = [BitConverter]::ToInt32($code, 1)
      $stub = $stub + 5 + $rel
      continue
    }
    break
  }
  if ($code[0] -eq 0xA1) { $g = [BitConverter]::ToUInt32($code, 1); return [FNS2]::U32($g) }
  if ($code[0] -eq 0xB8) { return [uint32][BitConverter]::ToUInt32($code, 1) }
  if ($code[0] -eq 0x8B -and $code[1] -eq 0x41 -and $code[3] -eq 0xC3 -and $obj -gt 0) {
    return [FNS2]::U32($obj + $code[2])
  }
  return 0
}
function ResolveId([long]$obj) {
  $vt = [FNS2]::U32($obj)
  if ($vt -lt 0x1800000 -or $vt -gt 0x2B00000) { return $null }
  $fn = [FNS2]::U32($vt + 0x14)
  $desc = Read-Desc $fn $obj
  if ($desc -eq 0) { return $null }
  $id = [FNS2]::U32($desc + 0x14)
  return @{ vt = $vt; fn = $fn; desc = $desc; id = $id }
}

"scanning CSrvNPCHealth instances (vt 0x02712F60)..."
$health = [FNS2]::ScanU32($ScanLo, $ScanHi, 0x02712F60, 0x800000)
"health instances: $($health.Count)"
# dedupe consecutive-ish (instances are objects; the vt might appear once per object)
$TARGET_ID = [uint32]0x6328D910
$seenP = @{}
$found = $false
$tryCount = 0
foreach ($h in $health) {
  if ($tryCount -ge $MaxHealth) { break }
  $tryCount++
  foreach ($off in @(0x20, 0x28)) {
    $P = [FNS2]::U32($h + $off)
    if ($P -lt 0x10000 -or $seenP.ContainsKey($P)) { continue }
    $seenP[$P] = 1
    foreach ($vecOff in @(0x70, 0x68)) {
      $base = [FNS2]::U32($P + $vecOff)
      $size = [FNS2]::U16($P + $vecOff + 6)
      if ($base -lt 0x10000 -or $size -lt 2 -or $size -gt 200) { continue }
      $names = @()
      for ($i = 0; $i -lt $size; $i++) {
        $svc = [FNS2]::U32($base + $i * 4)
        if ($svc -lt 0x10000) { continue }
        $r = ResolveId $svc
        if ($r -eq $null) { continue }
        $names += (RN $r.id)
        if ($r.id -eq $TARGET_ID) {
          "================ FOUND CSrvNavigation ================"
          "health=0x{0:X8} P=0x{1:X8} (via +0x{2:X2}) vecOff=0x{3:X2} idx={4} service=0x{5:X8}" -f $h, $P, $off, $vecOff, $i, $svc
          "vt=0x{0:X8} desc=0x{1:X8} id=0x{2:X8} name={3}" -f $r.vt, $r.desc, $r.id, (RN $r.id)
          $slot20 = [FNS2]::U32($r.vt + 20 * 4)
          $slot21 = [FNS2]::U32($r.vt + 21 * 4)
          $slot54 = [FNS2]::U32($r.vt + 54 * 4)
          $slot76 = [FNS2]::U32($r.vt + 76 * 4)
          "slot20=0x{0:X8} slot21=0x{1:X8} slot54=0x{2:X8} slot76=0x{3:X8}" -f $slot20, $slot21, $slot54, $slot76
          $b54 = [FNS2]::Read($slot54, 16)
          if ($b54) { "slot54 bytes: " + (($b54 | ForEach-Object { $_.ToString('X2') }) -join ' ') }
          $inst = [FNS2]::Read($svc, 0x40)
          if ($inst) { "instance hdr: " + (($inst | ForEach-Object { $_.ToString('X2') }) -join ' ') }
          $pat = [FNS2]::U32($svc + 0x84)
          "pattern ptr @svc+0x84 = 0x$('{0:X8}' -f $pat)"
          if ($pat -gt 0x10000) { $pr = ResolveId $pat; if ($pr) { "pattern class: vt=0x$('{0:X8}' -f $pr.vt) id=0x$('{0:X8}' -f $pr.id) name=$(RN $pr.id)" } }
          $found = $true
          break
        }
      }
      if ($found) { break }
      if ($names.Count -gt 0) {
        "  P=0x{0:X8} vecOff=0x{1:X2} size={2} resolved={3} :: {4}" -f $P, $vecOff, $size, $names.Count, (($names | Select-Object -First 10) -join ', ')
      }
    }
    if ($found) { break }
  }
  if ($found) { break }
}
if (-not $found) { "not found (tried $tryCount health anchors, $($seenP.Count) containers)" }
