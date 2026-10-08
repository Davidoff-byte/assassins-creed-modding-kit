# Scan a body's memory region for known asset ids (hash32 of defs) to find the visual linkage.
param(
  [Parameter(Mandatory=$true)][string]$Addr,
  [int]$Size = 4096
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MemScan {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int access, bool inherit, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
}
"@
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit 1 }
$h = [MemScan]::OpenProcess(0x0410, $false, $p.Id)
$base = [Convert]::ToInt64($Addr, 16)
$buf = New-Object byte[] $Size
$read = [IntPtr]::Zero
$ok = [MemScan]::ReadProcessMemory($h, [IntPtr]$base, $buf, $Size, [ref]$read)
if (-not $ok) { "ReadProcessMemory failed"; exit 1 }
$ids = @{
  0xE78D9C36 = "CHR_G_M_Pirate_Jackdaw_Sailors (crew)"
  0x8FB6DABC = "CHR_C_M_Generic_Sailors (sailor)"
  0x51BAB7D4 = "CHR_U_Duncan_Walpole (duncan)"
  0x815F7672 = "CHR_G_M_Assassin (assassin)"
  0x4AA83D02 = "CHR_C_Generic_Pirates"
  0x8915D370 = "CHR_G_Pirate_Captain"
  0x12CECF30 = "CHR_C_M_Spanish_Medium"
  0x12CECF22 = "CHR_C_M_Spanish_Poors"
  0x12CECF3F = "CHR_C_M_Spanish_Rich"
}
"scanning {0} bytes from {1} for {2} known ids" -f $Size, $Addr, $ids.Count
$found = @{}
for ($i = 0; $i -le $Size - 4; $i += 4) {
  $v = [BitConverter]::ToUInt32($buf, $i)
  if ($ids.ContainsKey($v)) {
    if (-not $found.ContainsKey($v)) { $found[$v] = @() }
    $found[$v] += ("0x{0:X3}" -f $i)
  }
}
if ($found.Count -eq 0) { "no known ids found in this window" }
foreach ($k in $found.Keys) { "{0} = {1}  at offsets: {2}" -f ("0x{0:X8}" -f $k), $ids[$k], ($found[$k] -join ", ") }
# also list candidate pointer-looking values in the body header area for context
"--- first 0x200 bytes hex ---"
for ($r = 0; $r -lt 0x200; $r += 16) {
  $hex = ($buf[$r..($r+15)] | ForEach-Object { $_.ToString("X2") }) -join " "
  ("0x{0:X3}  {1}" -f $r, $hex)
}
