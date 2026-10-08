param([Parameter(Mandatory=$true)][string]$Label)
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class SNP {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
  public static bool CanRead(IntPtr h, long addr) { byte[] b = new byte[4]; IntPtr r; return ReadProcessMemory(h, (IntPtr)addr, b, 4, out r); }
  public static long ReadPtr(IntPtr h, long addr) { return BitConverter.ToUInt32(Read(h, addr, 4), 0); }
  public static List<long> FindValue(int pid, uint value) {
    var hits = new List<long>();
    IntPtr h = OpenProcess(0x0410, false, pid);
    if (h == IntPtr.Zero) return hits;
    long addr = 0x10000, max = 0x7FFF0000;
    byte[] buf = new byte[1 << 20];
    int msz = Marshal.SizeOf(typeof(MBI));
    while (addr < max) {
      MBI m;
      if (VirtualQueryEx(h, (IntPtr)addr, out m, (IntPtr)msz) == IntPtr.Zero) break;
      long ba = (long)m.BaseAddress; long sz = (long)m.RegionSize;
      bool ok = (m.State == 0x1000) && ((m.Protect & 0x01) == 0) && ((m.Protect & 0x100) == 0) && ((m.Protect & 0xEE) != 0);
      if (ok) {
        for (long off = 0; off < sz; off += buf.Length) {
          int want = (int)Math.Min((long)buf.Length, sz - off); IntPtr got;
          if (ReadProcessMemory(h, (IntPtr)(ba + off), buf, want, out got) && got.ToInt32() > 0) {
            int n = got.ToInt32();
            for (int i = 0; i + 4 <= n; i += 4) if (BitConverter.ToUInt32(buf, i) == value) hits.Add(ba + off + i);
          }
        }
      }
      addr = ba + sz;
    }
    CloseHandle(h);
    return hits;
  }
}
"@
$h = [SNP]::Open($pidG)
$out = New-Object System.Collections.Generic.List[string]
function Dump([string]$tag,[int64]$a,[int]$n){
  if (-not [SNP]::CanRead($h,$a)) { [void]$out.Add("$tag 0x$('{0:X8}' -f $a) UNREADABLE"); return }
  $b = [SNP]::Read($h,$a,$n)
  for ($i=0; $i -lt $n; $i+=16) {
    $line = "$tag 0x{0:X8}:" -f ($a + $i)
    $cnt = [Math]::Min(16, $n - $i)
    for ($j=0; $j -lt $cnt; $j++) { $line += (" {0:X2}" -f $b[$i+$j]) }
    [void]$out.Add($line)
  }
}

# find player node
$mgr = [SNP]::ReadPtr($h, 0x2ABE588)
$holder = [SNP]::ReadPtr($h, $mgr + 0x4C)
$camobj = [SNP]::ReadPtr($h, $holder)
$block = [SNP]::ReadPtr($h, $camobj + 0x68)
$prov = [SNP]::ReadPtr($h, $block + 0x174)
$fb = [SNP]::Read($h, $prov + 0x110, 12)
$fx=[BitConverter]::ToSingle($fb,0); $fy=[BitConverter]::ToSingle($fb,4)
$hitList = [SNP]::FindValue($pidG, 0x01E4CE90)
$player = 0
foreach ($hit in $hitList) {
  $d = [SNP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($cnt -ge 24 -and $dist -lt 3) { $player = $hit; break }
}
if ($player -eq 0) { "player node not found"; exit }
[void]$out.Add("PLAYER NODE 0x$('{0:X8}' -f $player)")

# node itself (wide, covers property bag)
Dump "NODE" ($player - 0x40) 0x240
# pointer fields
$fields = @(0x08, 0x0C, 0x2C, 0x34, 0x4C, 0x58, 0x5C, 0x98, 0xA0, 0xA4, 0xA8, 0xAC, 0xB0, 0xC8, 0xE8, 0x110, 0x114, 0x120, 0x124, 0x128, 0x140, 0x144, 0x150, 0x154, 0x170, 0x174)
foreach ($f in $fields) {
  $ptr = [SNP]::ReadPtr($h, $player + $f)
  if ($ptr -ge 0x10000 -and $ptr -lt 0x7FFF0000) {
    Dump ("F{0:X3}" -f $f) $ptr 0x80
  }
}
# children
$cp = [SNP]::ReadPtr($h, $player + 0x60)
$cc = [BitConverter]::ToUInt16([SNP]::Read($h, $player + 0x66, 2), 0)
[void]$out.Add("CHILDREN ptr=0x$('{0:X8}' -f $cp) count=$cc")
for ($i=0; $i -lt [Math]::Min($cc,32); $i++) {
  $c = [SNP]::ReadPtr($h, $cp + $i*4)
  if ($c -lt 0x10000) { [void]$out.Add("CHILD[$i] null"); continue }
  [void]$out.Add("CHILD[$i] 0x$('{0:X8}' -f $c)")
  Dump "CHILD[$i]" $c 0x60
}

$dir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$path = Join-Path $dir ("snap-" + $Label + ".txt")
Set-Content -Path $path -Value $out -Encoding UTF8
"snapshot: $path  ($($out.Count) lines, player node 0x$('{0:X8}' -f $player))"
[void][SNP]::CloseHandle($h)