$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class SCN {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI {
    public IntPtr BaseAddress;
    public IntPtr AllocationBase;
    public uint AllocationProtect;
    public IntPtr RegionSize;
    public uint State;
    public uint Protect;
    public uint Type;
  }

  public static List<long> Find(int pid, uint value) {
    var hits = new List<long>();
    IntPtr h = OpenProcess(0x0410, false, pid);
    if (h == IntPtr.Zero) return hits;
    long addr = 0x10000, max = 0x7FFF0000;
    byte[] buf = new byte[1 << 20];
    int msz = Marshal.SizeOf(typeof(MBI));
    while (addr < max) {
      MBI m;
      if (VirtualQueryEx(h, (IntPtr)addr, out m, (IntPtr)msz) == IntPtr.Zero) break;
      long ba = (long)m.BaseAddress;
      long sz = (long)m.RegionSize;
      bool ok = (m.State == 0x1000) && ((m.Protect & 0x01) == 0) && ((m.Protect & 0x100) == 0) && ((m.Protect & 0xEE) != 0);
      if (ok) {
        for (long off = 0; off < sz; off += buf.Length) {
          int want = (int)Math.Min((long)buf.Length, sz - off);
          IntPtr got;
          if (ReadProcessMemory(h, (IntPtr)(ba + off), buf, want, out got) && got.ToInt32() > 0) {
            int n = got.ToInt32();
            for (int i = 0; i + 4 <= n; i += 4) {
              if (BitConverter.ToUInt32(buf, i) == value) hits.Add(ba + off + i);
            }
          }
        }
      }
      addr = ba + sz;
    }
    CloseHandle(h);
    return hits;
  }

  public static byte[] ReadAt(int pid, long addr, int size) {
    IntPtr h = OpenProcess(0x0410, false, pid);
    byte[] b = new byte[size];
    if (h == IntPtr.Zero) return b;
    IntPtr r;
    ReadProcessMemory(h, (IntPtr)addr, b, size, out r);
    CloseHandle(h);
    return b;
  }
}
"@

$t0 = Get-Date
$hitsA = [SCN]::Find($pidG, 0x04DD5F8C)
"scan A (value 0x04DD5F8C): $($hitsA.Count) hits  [$([int]((Get-Date)-$t0).TotalSeconds)s]"

$shown = 0
$vtMatch = 0
foreach ($h in $hitsA) {
  $base = [Int64]$h - 0x68
  if ($base -lt 0x10000) { continue }
  $d = [SCN]::ReadAt($pidG, $base, 0x90)
  if ($d.Length -lt 0x90) { continue }
  $vt = [BitConverter]::ToUInt32($d, 0)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d, 0x40)
  $y = [BitConverter]::ToSingle($d, 0x44)
  $z = [BitConverter]::ToSingle($d, 0x48)
  $f60 = [BitConverter]::ToSingle($d, 0x60)
  $f74 = [BitConverter]::ToSingle($d, 0x74)
  $f7c = [BitConverter]::ToSingle($d, 0x7C)
  if ($vt -eq 0x01E4CE90) { $vtMatch++ }
  if ([Math]::Abs($x) -lt 20000 -and [Math]::Abs($y) -lt 20000 -and [Math]::Abs($z) -lt 2000 -and $z -gt -2000) {
    $shown++
    if ($shown -le 60) {
      "  base=0x{0:X8} vt=0x{1:X8} id=0x{2:X8} pos=({3:F2}, {4:F2}, {5:F2}) f60={6:F2} f74={7:F2} f7c={8:F2}" -f $base, $vt, $id, $x, $y, $z, $f60, $f74, $f7c
    }
  }
}
"  (plausible: $shown of $($hitsA.Count); vtable==0x01E4CE90: $vtMatch)"

""
$t1 = Get-Date
$hitsB = [SCN]::Find($pidG, 0x44B38810)
"scan B (pointers to player source 0x44B38810): $($hitsB.Count) hits  [$([int]((Get-Date)-$t1).TotalSeconds)s]"
$n = 0
foreach ($h in $hitsB) {
  $n++
  if ($n -gt 40) { break }
  $start = [Int64]$h - 0x10
  if ($start -lt 0x10000) { continue }
  $d = [SCN]::ReadAt($pidG, $start, 0x40)
  $line = "  @0x{0:X8}: " -f $h
  for ($i = 0; $i -lt 0x40; $i += 4) {
    $v = [BitConverter]::ToUInt32($d, $i)
    $mark = if (($start + $i) -eq $h) { "*" } else { " " }
    $line += ("{0}{1:X8} " -f $mark, $v)
  }
  $line
}
