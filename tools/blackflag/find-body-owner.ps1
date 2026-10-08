$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class OWN {
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

$h = [OWN]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

# --- find the player's body (f7c=-0.5, cnt>=24, at the player's feet) ---
$mgr = [OWN]::ReadPtr($h, 0x2ABE588)
$holder = [OWN]::ReadPtr($h, $mgr + 0x4C)
$camobj = [OWN]::ReadPtr($h, $holder)
$block = [OWN]::ReadPtr($h, $camobj + 0x68)
$prov = [OWN]::ReadPtr($h, $block + 0x174)
$b = [OWN]::Read($h, $prov + 0x110, 12)
$fx = [BitConverter]::ToSingle($b,0); $fy = [BitConverter]::ToSingle($b,4); $fz = [BitConverter]::ToSingle($b,8)
"player feet = ({0:F2},{1:F2},{2:F2})" -f $fx, $fy, $fz

$hits = [OWN]::FindValue($pidG, 0x01E4CE90)
$playerBody = 0
$dumps = @{}
foreach ($hit in $hits) {
  $d = [OWN]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  if ($cnt -lt 24) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($dist -lt 3) { $playerBody = $hit; $dumps[$hit] = $d }
}
"player body object = 0x$('{0:X8}' -f $playerBody)"
if ($playerBody -eq 0) { "player body not found; abort"; exit }

# --- who points at it? ---
"scanning for pointers to the player body..."
$ptrs = [OWN]::FindValue($pidG, [uint32]$playerBody)
"pointers found: $($ptrs.Count)"
$i = 0
foreach ($pt in $ptrs) {
  $i++
  if ($i -gt 24) { break }
  $start = [int64]$pt - 0x20
  if ($start -lt 0x10000) { continue }
  $d = [OWN]::Read($h, $start, 0x60)
  $line = "  @0x{0:X8}: " -f $pt
  for ($k = 0; $k -lt 0x60; $k += 4) {
    $v = [BitConverter]::ToUInt32($d, $k)
    $mark = if ((($start + $k) -eq $pt)) { "*" } else { " " }
    $line += ("{0}{1:X8} " -f $mark, $v)
  }
  $line
}
[void][OWN]::CloseHandle($h)