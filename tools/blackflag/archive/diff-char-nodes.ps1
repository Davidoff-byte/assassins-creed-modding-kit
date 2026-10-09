$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class DIFF {
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

$h = [DIFF]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetMemAt2([int64]$a,[int]$n){ return [DIFF]::Read($h,$a,$n) }
$mgr = [BitConverter]::ToUInt32((GetMemAt2 0x2ABE588 4),0)
$holder = [BitConverter]::ToUInt32((GetMemAt2 ($mgr+0x4C) 4),0)
$camobj = [BitConverter]::ToUInt32((GetMemAt2 $holder 4),0)
$block = [BitConverter]::ToUInt32((GetMemAt2 ($camobj+0x68) 4),0)
$prov = [BitConverter]::ToUInt32((GetMemAt2 ($block+0x174) 4),0)
$fb = GetMemAt2 ($prov+0x110) 12
$fx=[BitConverter]::ToSingle($fb,0); $fy=[BitConverter]::ToSingle($fb,4)
"player feet = ({0:F2},{1:F2})" -f $fx,$fy

"scanning class instances..."
$hits = [DIFF]::FindValue($pidG, 0x01E4CE90)
$playerNode = 0; $crowdNode = 0; $crowdDist = 1e9
foreach ($hit in $hits) {
  $d = GetMemAt2 $hit 0x90
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($cnt -ge 24 -and $dist -lt 3) { $playerNode = $hit }
  if ($cnt -ge 16 -and $cnt -le 22 -and $dist -gt 5 -and $dist -lt 60 -and $dist -lt $crowdDist) { $crowdNode = $hit; $crowdDist = $dist }
}
"player node = 0x$('{0:X8}' -f $playerNode)   crowd node = 0x$('{0:X8}' -f $crowdNode) (d=$([Math]::Round($crowdDist,1)))"
if ($playerNode -eq 0 -or $crowdNode -eq 0) { "missing node; abort"; exit }

$pd = GetMemAt2 $playerNode 0x1C0
$cd = GetMemAt2 $crowdNode 0x1C0
""
"--- DIFF (offset: player | crowd) ---"
for ($off = 0; $off -lt 0x1C0; $off += 4) {
  $pv = [BitConverter]::ToUInt32($pd, $off)
  $cv = [BitConverter]::ToUInt32($cd, $off)
  if ($pv -eq $cv) { continue }
  $pf = [BitConverter]::ToSingle($pd, $off)
  $cf = [BitConverter]::ToSingle($cd, $off)
  $pnote = ""
  if ($pv -ge 0x400000 -and $pv -lt 0x2F00000) { $pnote = "IMG" }
  elseif ($pv -ge 0x10000 -and $pv -lt 0x7FFF0000) { $pnote = "ptr" }
  $cnote = ""
  if ($cv -ge 0x400000 -and $cv -lt 0x2F00000) { $cnote = "IMG" }
  elseif ($cv -ge 0x10000 -and $cv -lt 0x7FFF0000) { $cnote = "ptr" }
  "  +0x{0:X3}: P 0x{1:X8} {2,-4} ({3,10:F2})  |  C 0x{4:X8} {5,-4} ({6,10:F2})" -f $off, $pv, $pnote, $pf, $cv, $cnote, $cf
}
""
"--- children arrays ---"
$pcp = [BitConverter]::ToUInt32($pd, 0x60); $pcc = [BitConverter]::ToUInt16($pd, 0x66)
$ccp = [BitConverter]::ToUInt32($cd, 0x60); $ccc = [BitConverter]::ToUInt16($cd, 0x66)
"player: childPtr=0x{0:X8} count={1}" -f $pcp,$pcc
"crowd : childPtr=0x{0:X8} count={1}" -f $ccp,$ccc
if ($pcp -gt 0x10000) {
  $pa = GetMemAt2 $pcp 32
  "player children[0..7]: " + (($pa | ForEach-Object { '{0:X2}' -f $_ }) -join '')
}
[void][DIFF]::CloseHandle($h)