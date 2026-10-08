# classres.ps1 - runtime class resolver: object -> vtable -> descriptor-getter stub (mov eax,imm; ret) -> descriptor -> id/name.
param(
  [ValidateSet("objlist", "vtmap", "scanvt", "dumpobj", "dumpaddr", "desc")][string]$Mode = "objlist",
  [string]$Objs = "",
  [string]$VtHex = "",
  [long]$ScanLo = 0x30000000,
  [long]$ScanHi = 0x56000000,
  [string]$OutDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ai",
  [switch]$SkipStr
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class CLR2 {
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
[CLR2]::H = [CLR2]::OpenProcess(0x0410, $false, $game.Id)

$names = @{}
$crcf = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs\crc_all.txt"
if (Test-Path $crcf) {
  foreach ($l in [System.IO.File]::ReadLines($crcf)) {
    $p = $l.Split("`t")
    if ($p.Count -ge 2) { $names[$p[0].ToLower()] = $p[1] }
  }
}
"crc map entries: $($names.Count)"

function RN([uint32]$id) {
  $k = ("{0:x8}" -f $id)
  if ($names.ContainsKey($k)) { return $names[$k] }
  return "?"
}

function Read-Desc([long]$stub, [long]$obj) {
  $hops = 0
  while ($hops -lt 3) {
    $hops++
    if ($stub -lt 0x401000 -or $stub -gt 0x2B00000) { return $null }
    $code = [CLR2]::Read($stub, 12)
    if ($code -eq $null) { return $null }
    if ($code[0] -eq 0xE9) {
      $rel = [BitConverter]::ToInt32($code, 1)
      $stub = $stub + 5 + $rel
      continue
    }
    break
  }
  if ($code[0] -eq 0xA1) {
    $g = [BitConverter]::ToUInt32($code, 1)
    return [uint32][CLR2]::U32($g)
  }
  if ($code[0] -eq 0xB8) {
    return [uint32][BitConverter]::ToUInt32($code, 1)
  }
  if ($code[0] -eq 0x8B -and $code[1] -eq 0x41 -and $code[3] -eq 0xC3 -and $obj -gt 0) {
    return [uint32][CLR2]::U32($obj + $code[2])
  }
  return [uint32]0
}

function Resolve-Obj([long]$addr) {
  $vtv = [CLR2]::U32($addr)
  return Resolve-ObjVt $addr $vtv
}

function Resolve-ObjVt([long]$addr, [long]$vtv) {
  if ($vtv -lt 0x1800000 -or $vtv -gt 0x2B00000) { return $null }
  $fn = [CLR2]::U32($vtv + 0x14)
  $desc = Read-Desc $fn $addr
  if ($desc -eq 0) { return $null }
  $id = [CLR2]::U32($desc + 0x14)
  $res = @{vt = $vtv; fn = $fn; desc = $desc; id = $id; name = (RN $id); str = ""}
  if (-not $SkipStr) {
    $db = [CLR2]::Read($desc, 0x40)
    if ($db -ne $null) {
      for ($o = 0; $o -lt 0x40; $o += 4) {
        $p = [BitConverter]::ToUInt32($db, $o)
        if ($p -lt 0x400000 -or $p -gt 0x3000000) { continue }
        $sb = [CLR2]::Read($p, 48)
        if ($sb -eq $null) { continue }
        $s = ""
        foreach ($ch in $sb) { if ($ch -ge 32 -and $ch -lt 127) { $s += [char]$ch } else { break } }
        if ($s.Length -ge 3) { $res["str"] = "str@+$('{0:X}' -f $o)=$s"; break }
      }
    }
  }
  return $res
}

function Resolve-Vt([long]$vtv) {
  return Resolve-ObjVt 0 $vtv
}

if ($Mode -eq "objlist") {
  foreach ($a in $Objs.Split(',')) {
    if ($a.Trim() -eq "") { continue }
    $addr = [Convert]::ToInt64($a.Trim(), 16)
    $vtv = [CLR2]::U32($addr)
    $r = Resolve-Obj $addr
    if ($r -eq $null) {
      "OBJ {0:X8} -> unresolved (vt={1:X8})" -f $addr, $vtv
    }
    else {
      "OBJ {0:X8} -> vt={1:X8} id={2:X8} name={3} {4}" -f $addr, $r["vt"], $r["id"], $r["name"], $r["str"]
    }
  }
  exit 0
}

if ($Mode -eq "vtmap") {
  $vtf = "C:\Users\Administrator\bf4_re\analysis\vtables_sp.txt"
  $lines = @()
  $n = 0; $ok = 0
  foreach ($l in [System.IO.File]::ReadLines($vtf)) {
    if ($l -notmatch '^VT ([0-9a-fA-F]{8})') { continue }
    $n++
    $vtv = [Convert]::ToInt64($Matches[1], 16)
    $r = Resolve-Vt $vtv
    if ($r -eq $null) { continue }
    $ok++
    $lines += ("{0:X8} id={1:X8} name={2} {3}" -f $r["vt"], $r["id"], $r["name"], $r["str"])
  }
  "vtmap: total=$n resolved=$ok"
  $out = Join-Path $OutDir "vt_class_map.txt"
  $lines | Set-Content $out
  "saved -> $out"
  "--- interesting entries ---"
  $lines | Where-Object { $_ -match "NPCHealth|PlayerHealth|Damage|CSrvHealth|AIDataBuilder|BhvGenericNPC|EntityAI|Health" } | Select-Object -First 40
  exit 0
}

if ($Mode -eq "desc") {
  foreach ($a in $Objs.Split(',')) {
    $addr = [Convert]::ToInt64($a.Trim(), 16)
    $vtv = [CLR2]::U32($addr)
    $fn = [CLR2]::U32($vtv + 0x14)
    $code = [CLR2]::Read($fn, 8)
    if ($code -eq $null) { "no code {0:X8}" -f $fn; continue }
    $desc = 0
    if ($code[0] -eq 0xA1) { $g = [BitConverter]::ToUInt32($code, 1); $desc = [CLR2]::U32($g); "OBJ {0:X8} vt={1:X8} fn={2:X8} global={3:X8} desc={4:X8}" -f $addr, $vtv, $fn, $g, $desc }
    elseif ($code[0] -eq 0xB8) { $desc = [BitConverter]::ToUInt32($code, 1); "OBJ {0:X8} vt={1:X8} fn={2:X8} desc={3:X8}" -f $addr, $vtv, $fn, $desc }
    else { "OBJ {0:X8} unrecognized stub {1:X8}: {2}" -f $addr, $fn, (($code | ForEach-Object { $_.ToString('X2') }) -join ' '); continue }
    $db = [CLR2]::Read($desc, 0x300)
    if ($db -eq $null) { "desc unreadable"; continue }
    for ($o = 0; $o -lt 0x300; $o += 0x40) {
      $hex = ($db[$o..([Math]::Min($o + 0x3F, 0x2FF))] | ForEach-Object { $_.ToString("X2") }) -join ' '
      "  +{0:X3}: {1}" -f $o, $hex
    }
    "  -- strings in 0x300 --"
    $s = ""
    $sstart = -1
    for ($o = 0; $o -lt 0x300; $o++) {
      $c = $db[$o]
      if ($c -ge 32 -and $c -lt 127) {
        if ($s -eq "") { $sstart = $o }
        $s += [char]$c
      }
      else {
        if ($s.Length -ge 3) { "  +{0:X3}: {1}" -f $sstart, $s }
        $s = ""
        $sstart = -1
      }
    }
    if ($s.Length -ge 3) { "  +{0:X3}: {1}" -f $sstart, $s }
  }
  exit 0
}

if ($Mode -eq "dumpobj") {
  foreach ($a in $Objs.Split(',')) {
    $addr = [Convert]::ToInt64($a.Trim(), 16)
    "=== OBJ {0:X8} ===" -f $addr
    $hdr = [CLR2]::Read($addr, 0x40)
    if ($hdr -ne $null) { "  hdr: " + (($hdr | ForEach-Object { $_.ToString('X2') }) -join ' ') }
    $vtv = [CLR2]::U32($addr)
    "  vt={0:X8}" -f $vtv
    if ($vtv -ge 0x1800000 -and $vtv -le 0x2B00000) {
      $vtb = [CLR2]::Read($vtv, 0x30)
      if ($vtb -ne $null) { "  vtbl: " + (($vtb | ForEach-Object { $_.ToString('X2') }) -join ' ') }
      $fn = [CLR2]::U32($vtv + 0x14)
      "  fn(@vt+14)={0:X8}" -f $fn
      if ($fn -ge 0x401000 -and $fn -le 0x2B00000) {
        $fb = [CLR2]::Read($fn, 0x18)
        if ($fb -ne $null) { "  fn bytes: " + (($fb | ForEach-Object { $_.ToString('X2') }) -join ' ') }
      }
    }
  }
  exit 0
}

if ($Mode -eq "dumpaddr") {
  foreach ($a in $Objs.Split(',')) {
    $addr = [Convert]::ToInt64($a.Trim(), 16)
    $b = [CLR2]::Read($addr, 0x30)
    if ($b -eq $null) { "unreadable {0:X8}" -f $addr; continue }
    "=== {0:X8} ===`n  {1}" -f $addr, (($b | ForEach-Object { $_.ToString('X2') }) -join ' ')
  }
  exit 0
}

if ($Mode -eq "scanvt") {
  $vtv = [Convert]::ToUInt32($VtHex, 16)
  "scanning for objects with vt={0:X8} in [{1:X8}..{2:X8}]" -f $vtv, $ScanLo, $ScanHi
  $hits = [CLR2]::ScanU32($ScanLo, $ScanHi, $vtv, 0x800000)
  "hits: $($hits.Count)"
  foreach ($h in ($hits | Select-Object -First 60)) {
    $L = [CLR2]::U32($h + 0x5A); $M = [CLR2]::U32($h + 0x5C)
    "  OBJ {0:X8} +5A={1:X8} +5C={2:X8} +60={3:X8}" -f $h, $L, $M, ([CLR2]::U32($h + 0x60))
  }
  exit 0
}
