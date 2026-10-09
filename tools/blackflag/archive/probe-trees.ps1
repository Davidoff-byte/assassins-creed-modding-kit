$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class TT {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
  public static bool CanRead(IntPtr h, long addr) { byte[] b = new byte[4]; IntPtr r; return ReadProcessMemory(h, (IntPtr)addr, b, 4, out r); }
}
"@
$h = [TT]::Open($p.Id)
function B4([int64]$a,[int]$n){ return [TT]::Read($h,$a,$n) }
function Head([int64]$a,[string]$label){
  if (-not [TT]::CanRead($h,$a)) { "  $label 0x$('{0:X8}' -f $a): UNREADABLE"; return }
  $d = B4 $a 0x30
  $parts = ""
  for ($i=0; $i -lt 0x30; $i+=4) {
    $v = [BitConverter]::ToUInt32($d,$i)
    $note = ""
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) { $note = "IMG" } elseif ($v -ge 0x10000 -and $v -lt 0x7FFF0000) { $note = "ptr" }
    $parts += ("+{0:X2}:{1:X8}{2} " -f $i,$v,$note)
  }
  "  $label 0x$('{0:X8}' -f $a): $parts"
}
function Dir([int64]$a,[string]$label){
  if (-not [TT]::CanRead($h,$a)) { "  $label 0x$('{0:X8}' -f $a): UNREADABLE"; return }
  $d = B4 $a 8
  $vt = [BitConverter]::ToUInt32($d,0)
  $f4 = [BitConverter]::ToUInt32($d,4)
  "  $label 0x$('{0:X8}' -f $a): vtable=0x$('{0:X8}' -f $vt) +4=0x$('{0:X8}' -f $f4)"
}

"### player-only object (P node +0x8 ->) ###"
Head 0x477C1D60 "P+8 obj"
""
"### player node head ###"
Head 0x41C00C00 "P node"
"### visible crowd node head ###"
Head 0x3743BD40 "cA node"
""
"### player children (ptr 0x46D6A9A0, cnt 27) ###"
$pa = B4 0x46D6A9A0 40
for ($i=0; $i -lt 40; $i+=4) {
  $cp = [BitConverter]::ToUInt32($pa,$i)
  if ($cp -ge 0x10000 -and $cp -lt 0x7FFF0000) { Dir $cp ("Pchild[$i/4]") }
}
""
"### cA children (ptr 0xFC569150, cnt 20) ###"
$ca = B4 0xFC569150 40
for ($i=0; $i -lt 40; $i+=4) {
  $cp = [BitConverter]::ToUInt32($ca,$i)
  if ($cp -ge 0x10000 -and $cp -lt 0x7FFF0000) { Dir $cp ("cAchild[$i/4]") }
}
""
"### cA node +0x170 target (0x3837D628) ###"
Head 0x3837D628 "cA+170"
"### player child[0] target (0x3837D060) ###"
Head 0x3837D060 "Pchild0"
""
"### player node +0x50 area vs cA ###"
"  P    +0x50: " + (Head (0x41C00C00+0x50) "P+50").Trim()
[void][TT]::CloseHandle($h)