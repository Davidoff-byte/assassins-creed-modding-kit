# set-health.ps1 - write a value into a CSrvNPCHealth instance field (default +0x5C LIFE, u16).
param(
  [Parameter(Mandatory = $true)][string]$Addr,
  [string]$Offset = "0x5C",
  [int]$Value = -1,
  [switch]$U32,
  [switch]$Or32
)
$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SH {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr written);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size];
    IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static bool Write(long addr, byte[] data) {
    IntPtr w;
    return WriteProcessMemory(H, (IntPtr)addr, data, data.Length, out w);
  }
  public static ushort U16(long a) { var b = Read(a, 2); return b == null ? (ushort)0 : BitConverter.ToUInt16(b, 0); }
}
'@
[SH]::H = [SH]::OpenProcess(0x0438, $false, $game.Id)  # QUERY|OPERATION|VM_READ|VM_WRITE

$a = [Convert]::ToInt64($Addr, 16)
$off = [Convert]::ToInt64($Offset, 16)
$old = [SH]::U16($a + $off)
if ($Value -lt 0) {
  "READ {0:X8} +0x{1:X} : {2}   (vt={3:X8})" -f $a, $off, $old, ([BitConverter]::ToUInt32([SH]::Read($a, 4), 0))
  $life = [SH]::U16($a + 0x5C); $max = [SH]::U16($a + 0x5E)
  $fl = [BitConverter]::ToUInt32([SH]::Read($a + 0x60, 4), 0)
  "LIFE={0} MAX={1} FLAGS={2:X8}" -f $life, $max, $fl
  exit 0
}
if ($Or32) {
  $cur = [BitConverter]::ToUInt32([SH]::Read($a + $off, 4), 0)
  $newv = $cur -bor [uint32]$Value
  $ok = [SH]::Write($a + $off, [BitConverter]::GetBytes([uint32]$newv))
  $new = [BitConverter]::ToUInt32([SH]::Read($a + $off, 4), 0)
  "OR32 {0:X8} +0x{1:X} : {2:X8} | {3:X8} -> {4:X8}  (ok={5}, readback={6:X8})" -f $a, $off, $cur, [uint32]$Value, $newv, $ok, $new
  exit 0
}
if ($U32) {
  $cur = [BitConverter]::ToUInt32([SH]::Read($a + $off, 4), 0)
  $ok = [SH]::Write($a + $off, [BitConverter]::GetBytes([uint32]$Value))
  $new = [BitConverter]::ToUInt32([SH]::Read($a + $off, 4), 0)
  "WRITE32 {0:X8} +0x{1:X} : {2:X8} -> {3:X8}  (ok={4}, readback={5:X8})" -f $a, $off, $cur, [uint32]$Value, $ok, $new
  exit 0
}
$bytes = [BitConverter]::GetBytes([uint16]$Value)
$ok = [SH]::Write($a + $off, $bytes)
$new = [SH]::U16($a + $off)
"WRITE {0:X8} +0x{1:X} : {2} -> {3}  (ok={4}, readback={5})" -f $a, $off, $old, $Value, $ok, $new
"vt check: {0:X8}" -f ([BitConverter]::ToUInt32([SH]::Read($a, 4), 0))
