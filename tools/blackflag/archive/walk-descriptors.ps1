$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class WK {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
}
"@
$h = [WK]::Open($p.Id)
function GetBytesAt([int64]$a,[int]$n){ return [WK]::Read($h,$a,$n) }
function AsciiAt([int64]$a,[int]$max){
  $b = GetBytesAt $a $max
  $s = ""
  for ($i=0; $i -lt $b.Length; $i++) {
    if ($b[$i] -eq 0) { break }
    if ($b[$i] -lt 32 -or $b[$i] -gt 126) { return "" }
    $s += [char]$b[$i]
  }
  if ($s.Length -ge 4) { return $s } else { return "" }
}
function Dump([string]$label,[int64]$a,[int]$n){
  "--- $label  0x$('{0:X8}' -f $a) ---"
  $b = GetBytesAt $a $n
  for ($i=0; $i -lt $n; $i+=4) {
    $v = [BitConverter]::ToUInt32($b,$i)
    if ($v -eq 0) { continue }
    $note = ""
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) { $note = "IMG" } elseif ($v -ge 0x10000 -and $v -lt 0x7FFF0000) { $note = "ptr" }
    $s = ""
    if ($v -ge 0x10000) { $s = AsciiAt $v 48 }
    $extra = ""
    if ($s -ne "") { $extra = "  str='" + $s + "'" }
    "  +0x{0:X2}: 0x{1:X8} {2,-4}{3}" -f $i, $v, $note, $extra
  }
}

"### the two TYPE DESCRIPTORS ###"
Dump "player desc" 0x026FA898 0x50
Dump "crowd desc " 0x026E34D8 0x50
""
"### the two DATA INSTANCES ###"
Dump "player inst (+0xE8 obj)" 0x46CF9A40 0x50
Dump "crowd  inst (+0xE8 obj)" 0x47B608B0 0x50
""
"### per-character pointers from the instances ###"
Dump "P inst+0x1C ->" 0x46F82550 0x30
Dump "P inst+0x20 ->" 0x46F40420 0x30
Dump "P inst+0x24 ->" 0x46D66660 0x30
Dump "C inst+0x1C ->" 0x47B609D0 0x30
Dump "C inst+0x20 ->" 0x2B2E53F0 0x30
Dump "C inst+0x24 ->" 0x469E8590 0x30
[void][WK]::CloseHandle($h)