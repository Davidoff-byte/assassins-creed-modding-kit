$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class PRB {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
}
"@
$h = [PRB]::Open($p.Id)
function GetBytesAt([int64]$a,[int]$n){ return [PRB]::Read($h,$a,$n) }
function Utf16At([int64]$a,[int]$maxChars){
  $b = GetBytesAt $a ($maxChars*2)
  $s = ""
  for ($i=0; $i -lt $b.Length-1; $i+=2) {
    $c = [BitConverter]::ToUInt16($b,$i)
    if ($c -eq 0) { break }
    if ($c -lt 32 -or $c -gt 126) { return "(non-ascii at char $($i/2))" }
    $s += [char]$c
  }
  return $s
}
function DumpDW([int64]$a,[int]$n){
  $b = GetBytesAt $a $n
  $out = ""
  for ($i=0; $i -lt $n; $i+=4) {
    $v = [BitConverter]::ToUInt32($b,$i)
    $note = ""
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) { $note = "IMG" }
    elseif ($v -ge 0x10000 -and $v -lt 0x7FFF0000) { $note = "ptr" }
    $out += ("+{0:X2}:{1:X8}{2} " -f $i, $v, $note)
  }
  return $out
}

"=== player node ==="
$P = 0x41C00C00
"  +0x110 -> 0x02595BC8 string: '" + (Utf16At 0x02595BC8 40) + "'"
"  +0xC8  -> 0x4692F85C:"
"     " + (DumpDW 0x4692F85C 0x30)
"     first dword string: '" + (Utf16At ([BitConverter]::ToUInt32((GetBytesAt 0x4692F85C 4),0)) 40) + "'"
"  +0xE8  -> 0x46CF9A40:"
"     " + (DumpDW 0x46CF9A40 0x30)
"     first dword string: '" + (Utf16At ([BitConverter]::ToUInt32((GetBytesAt 0x46CF9A40 4),0)) 40) + "'"
"  +0xD4  region: " + (DumpDW 0x41C00CC8 0x20)
""
"=== crowd node ==="
$C = 0x43746AF0
"  +0x170 -> 0x02595050 string: '" + (Utf16At 0x02595050 40) + "'"
"  +0xC8  -> 0x36EA1DA4:"
"     " + (DumpDW 0x36EA1DA4 0x30)
"     first dword string: '" + (Utf16At ([BitConverter]::ToUInt32((GetBytesAt 0x36EA1DA4 4),0)) 40) + "'"
"  +0xE8  -> 0x47B608B0:"
"     " + (DumpDW 0x47B608B0 0x30)
"     first dword string: '" + (Utf16At ([BitConverter]::ToUInt32((GetBytesAt 0x47B608B0 4),0)) 40) + "'"
"  +0x180 -> 0x43740360: " + (DumpDW 0x43740360 0x20)
[void][PRB]::CloseHandle($h)