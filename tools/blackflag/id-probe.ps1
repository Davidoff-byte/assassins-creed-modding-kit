# id-probe.ps1 - search a body object (and its first-level pointers) for known character ids (CRCs).
param([Parameter(Mandatory=$true)][string]$Body)

Add-Type @"
using System;using System.Runtime.InteropServices;
public static class IDP {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
}
"@
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }
$h = [IDP]::OpenProcess(0x0410, $false, $game.Id)

$targets = @{
 0x4fa94a64 = 'CHR_G_M_Assassin'
 0xb749b193 = 'CHR_G_F_Assassin'
 0xd95baa3e = 'CHR_C_M_Generic_Sailors'
 0x97f49f82 = 'CHR_C_Generic_Pirates'
 0x05b33c6b = 'CHR_Crowd'
 0x2e89b751 = 'CHR_C_M_Crowd_Male_ID1'
 0xb780e6eb = 'CHR_C_M_Crowd_Male_ID2'
 0xc087d67d = 'CHR_C_M_Crowd_Male_ID3'
 0x5fe884d3 = 'CHR_U_Assassins'
 0x42fae08c = 'CHR_G_TPL_Guard'
 0xd0713c43 = 'CHR_G_Pirate_Sailor'
 0xc1deb691 = 'CHR_G_Pirate_Agile'
}

function ReadMem([int64]$a,[int]$n){ $b=New-Object byte[] $n; $r=[IntPtr]::Zero; [void][IDP]::ReadProcessMemory($h,[IntPtr]$a,$b,$n,[ref]$r); return $b }

$body = [Convert]::ToUInt32(($Body -replace '^0x',''),16)
"body 0x{0:X}" -f $body

# 1) the object itself
$b = ReadMem $body 0x400
for ($i = 0; $i + 4 -le $b.Length; $i += 4) {
  $v = [BitConverter]::ToUInt32($b, $i)
  if ($targets.ContainsKey($v)) { "  OBJ+0x{0:X3} = 0x{1:X8}  {2}" -f $i, $v, $targets[$v] }
}
# 2) first-level pointers from the first 0x100 bytes -> read 0x300 each and search
for ($i = 0; $i + 4 -le 0x100; $i += 4) {
  $p = [BitConverter]::ToUInt32($b, $i)
  if ($p -lt 0x10000 -or $p -gt 0x7FFF0000) { continue }
  $d = ReadMem $p 0x300
  for ($j = 0; $j + 4 -le $d.Length; $j += 4) {
    $v = [BitConverter]::ToUInt32($d, $j)
    if ($targets.ContainsKey($v)) { "  [OBJ+0x{0:X3}] -> 0x{1:X} +0x{2:X3} = 0x{3:X8}  {4}" -f $i, $p, $j, $v, $targets[$v] }
  }
}
"done"
