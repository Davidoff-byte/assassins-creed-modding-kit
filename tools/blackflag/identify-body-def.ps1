# Identify which asset-def a body uses: walk pointer chains from the body and
# look for known def ids (crew/sailor/duncan/assassin) in pointee memory.
param(
  [Parameter(Mandatory=$true)][string]$Addr,
  [int]$MaxPtr = 96,
  [int]$Depth = 2
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MemI {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int access, bool inherit, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
}
"@
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit 1 }
$h = [MemI]::OpenProcess(0x0410, $false, $p.Id)
$ids = @{
  0xE78D9C36 = "CREW(Jackdaw)"
  0x8FB6DABC = "SAILOR"
  0x51BAB7D4 = "DUNCAN"
  0x815F7672 = "ASSASSIN"
}
function ReadBytes([int64]$a, [int]$n) {
  $b = New-Object byte[] $n
  $r = [IntPtr]::Zero
  $ok = [MemI]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r)
  if (-not $ok) { return $null }
  return $b
}
function ScanIds([byte[]]$buf, [string]$where) {
  if ($null -eq $buf) { return }
  for ($i = 0; $i -le $buf.Length - 4; $i += 4) {
    $v = [BitConverter]::ToUInt32($buf, $i)
    if ($ids.ContainsKey($v)) {
      "FOUND {0} ({1}) at {2}+0x{3:X}" -f ("0x{0:X8}" -f $v), $ids[$v], $where, $i
    }
  }
}
$base = [Convert]::ToInt64($Addr, 16)
$head = ReadBytes $base 0x200
if ($null -eq $head) { "cannot read body"; exit 1 }
ScanIds $head "body"
"=== pointer candidates in body head ==="
$ptrs = @()
for ($i = 0; $i -le 0x1FC; $i += 4) {
  $v = [BitConverter]::ToUInt32($head, $i)
  if ($v -gt 0x10000 -and $v -lt 0x7FFF0000 -and ($v % 4) -eq 0) {
    $ptrs += ,@($i, $v)
  }
}
"candidates: " + $ptrs.Count
$limit = [Math]::Min($ptrs.Count, $MaxPtr)
for ($k = 0; $k -lt $limit; $k++) {
  $off = $ptrs[$k][0]; $ptr = $ptrs[$k][1]
  $buf = ReadBytes $ptr 0x800
  ScanIds $buf ("body+0x{0:X}->0x{1:X}" -f $off, $ptr)
  if ($Depth -ge 2 -and $null -ne $buf) {
    # second level: pointers inside the pointee head
    for ($j = 0; $j -le 0x1FC; $j += 4) {
      $v2 = [BitConverter]::ToUInt32($buf, $j)
      if ($v2 -gt 0x10000 -and $v2 -lt 0x7FFF0000 -and ($v2 % 4) -eq 0) {
        $buf2 = ReadBytes $v2 0x400
        ScanIds $buf2 ("body+0x{0:X}->0x{1:X}->0x{2:X}" -f $off, $ptr, $v2)
      }
    }
  }
}
"done"
