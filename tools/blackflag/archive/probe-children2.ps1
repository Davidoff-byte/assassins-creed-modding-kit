$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class TN {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
  public static bool CanRead(IntPtr h, long addr) { byte[] b = new byte[4]; IntPtr r; return ReadProcessMemory(h, (IntPtr)addr, b, 4, out r); }
}
"@
$h = [TN]::Open($p.Id)
function ReadAt([int64]$a,[int]$n){ return [TN]::Read($h,$a,$n) }
function ShowHead([int64]$a,[string]$label){
  if (-not [TN]::CanRead($h,$a)) { "  $label 0x$('{0:X8}' -f $a): UNREADABLE"; return }
  $d = ReadAt $a 0x40
  $line = ""
  for ($i=0; $i -lt 0x40; $i+=4) {
    $v = [BitConverter]::ToUInt32($d,$i)
    $note = ""
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) { $note = "IMG" } elseif ($v -ge 0x10000 -and $v -lt 0x7FFF0000) { $note = "ptr" }
    $line += ("+{0:X2}:{1:X8}{2} " -f $i,$v,$note)
  }
  "  $label 0x$('{0:X8}' -f $a): $line"
}
function ShowChildren([int64]$ptr,[int]$count,[string]$label){
  "### $label children @0x$('{0:X8}' -f $ptr) count=$count ###"
  if ($count -gt 12) { $count = 12 }
  for ($i=0; $i -lt $count; $i++) {
    $cp = [BitConverter]::ToUInt32((ReadAt ($ptr + $i*4) 4),0)
    if ($cp -lt 0x10000) { "  child[$i] = 0x$('{0:X8}' -f $cp) (null)"; continue }
    ShowHead $cp "child[$i]"
  }
}
# player node 0x41C00C00 children 0x46D6A9A0 count 27
ShowChildren 0x46D6A9A0 27 "PLAYER"
""
# visible crowd node 0x3743BD40 children 0xFC569150 count 20
ShowChildren 0xFC569150 20 "VISIBLE-CROWD 0x3743BD40"
""
# second crowd for comparison 0x43746AF0 children 0xFC569420 count 19
ShowChildren 0xFC569420 19 "CROWD 0x43746AF0"
[void][TN]::CloseHandle($h)