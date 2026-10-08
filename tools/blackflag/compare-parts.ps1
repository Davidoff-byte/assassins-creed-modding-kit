$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class PC {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
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
$h = [PC]::Open($pidG)
function BytesAt([int64]$a,[int]$n){ return [PC]::Read($h,$a,$n) }
$mgr = [BitConverter]::ToUInt32((BytesAt 0x2ABE588 4),0)
$holder = [BitConverter]::ToUInt32((BytesAt ($mgr+0x4C) 4),0)
$camobj = [BitConverter]::ToUInt32((BytesAt $holder 4),0)
$block = [BitConverter]::ToUInt32((BytesAt ($camobj+0x68) 4),0)
$prov = [BitConverter]::ToUInt32((BytesAt ($block+0x174) 4),0)
$fb = BytesAt ($prov+0x110) 12
$fx=[BitConverter]::ToSingle($fb,0); $fy=[BitConverter]::ToSingle($fb,4)
"player feet = ({0:F2},{1:F2})" -f $fx,$fy
$hitList = [PC]::FindValue($pidG, 0x01E4CE90)
$player = 0; $visible = 0
foreach ($hit in $hitList) {
  $d = BytesAt $hit 0x90
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($cnt -ge 24 -and $dist -lt 3) { $player = $hit }
  if ($player -ne 0 -and $cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x10000 -and $dist -gt 4 -and $dist -lt 120 -and $visible -eq 0) { $visible = $hit }
}
"player node = 0x$('{0:X8}' -f $player)   visible crowd = 0x$('{0:X8}' -f $visible)"
function Kids([int64]$n){
  $cp = [int64]([uint32]([BitConverter]::ToUInt32((BytesAt ($n + 0x60) 4),0)))
  $cc = [BitConverter]::ToUInt16((BytesAt ($n + 0x66) 2), 0)
  $res = @()
  for ($i=0; $i -lt $cc; $i++) {
    $c = [int64]([uint32]([BitConverter]::ToUInt32((BytesAt ($cp + $i*4) 4),0)))
    $res += $c
  }
  return ,$res
}
$pk = Kids $player
$vk = Kids $visible
"player children: $($pk.Count)   crowd children: $($vk.Count)"
""
"--- part comparison (index: P vtable/fields | C vtable/fields) ---"
$max = [Math]::Min([Math]::Min($pk.Count, $vk.Count), 22)
for ($i=0; $i -lt $max; $i++) {
  $pcp = $pk[$i]; $vcp = $vk[$i]
  $pb = BytesAt $pcp 0x40
  $vb = BytesAt $vcp 0x40
  $pl = ""; $vl = ""
  for ($j=0; $j -lt 0x40; $j+=4) {
    $pv = [BitConverter]::ToUInt32($pb,$j)
    $vv = [BitConverter]::ToUInt32($vb,$j)
    if ($pv -eq $vv -and $pv -ne 0) { continue }
    $pl += ("+{0:X2}:{1:X8} " -f $j,$pv)
    $vl += ("+{0:X2}:{1:X8} " -f $j,$vv)
  }
  "part[$i]  P 0x$('{0:X8}' -f $pcp) vs C 0x$('{0:X8}' -f $vcp)"
  "    P: $pl"
  "    C: $vl"
}
[void][PC]::CloseHandle($h)