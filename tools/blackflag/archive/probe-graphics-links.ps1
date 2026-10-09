$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class WK2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
}
"@
$h = [WK2]::Open($p.Id)
function B2([int64]$a,[int]$n){ return [WK2]::Read($h,$a,$n) }
function HexAscii([int64]$a,[int]$n){
  $b = B2 $a $n
  $hex = ""
  $asc = ""
  for ($i=0; $i -lt $b.Length; $i++) {
    $hex += ("{0:X2} " -f $b[$i])
    if ($b[$i] -ge 32 -and $b[$i] -lt 127) { $asc += [char]$b[$i] } else { $asc += "." }
    if (($i % 16) -eq 15) { $hex += "`n     "; $asc += "`n     " }
  }
  return "  hex: $hex`n  asc: $asc"
}
function Ptrs([int64]$a,[int]$n){
  $b = B2 $a $n
  $out = ""
  for ($i=0; $i -lt $n; $i+=4) {
    $v = [BitConverter]::ToUInt32($b,$i)
    $note = ""
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) { $note = "IMG" } elseif ($v -ge 0x10000 -and $v -lt 0x7FFF0000) { $note = "ptr" }
    $out += ("+{0:X2}:{1:X8}{2} " -f $i, $v, $note)
  }
  return $out
}

"### target of player node +0x110 (0x02595BC8) ###"
HexAscii 0x02595BC8 0x40
"  as dwords: " + (Ptrs 0x02595BC8 0x40)
""
"### target of crowd node +0x170 (0x02595050) ###"
HexAscii 0x02595050 0x40
"  as dwords: " + (Ptrs 0x02595050 0x40)
""
"### player node children (0x46D6A9A0, count 27) ###"
"  " + (Ptrs 0x46D6A9A0 0x40)
"### crowd node children (0xFC569420, count 19) ###"
"  " + (Ptrs 0xFC569420 0x40)
""
$pc0 = [BitConverter]::ToUInt32((B2 0x46D6A9A0 4),0)
$cc0 = [BitConverter]::ToUInt32((B2 0xFC569420 4),0)
"### player child[0] 0x$('{0:X8}' -f $pc0) head ###"
"  " + (Ptrs $pc0 0x40)
"  " + (HexAscii ($pc0+0x10) 0x30)
"### crowd child[0] 0x$('{0:X8}' -f $cc0) head ###"
"  " + (Ptrs $cc0 0x40)
"  " + (HexAscii ($cc0+0x10) 0x30)
[void][WK2]::CloseHandle($h)