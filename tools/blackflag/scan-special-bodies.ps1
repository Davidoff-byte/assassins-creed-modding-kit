# Children-count histogram of character-node instances near the player.
# Shows the rig-size distribution (player 27, crowd 18-20, inactive proxies 8-14,
# markers 1) and lists any non-standard rigs. Read-only.
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class RIG {
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
$h = [RIG]::Open($pidG)
function BytesAt3([int64]$a,[int]$n){ return [RIG]::Read($h,$a,$n) }
$mgr = [BitConverter]::ToUInt32((BytesAt3 0x2ABE588 4),0)
$holder = [BitConverter]::ToUInt32((BytesAt3 ($mgr+0x4C) 4),0)
$camobj = [BitConverter]::ToUInt32((BytesAt3 $holder 4),0)
$block = [BitConverter]::ToUInt32((BytesAt3 ($camobj+0x68) 4),0)
$prov = [BitConverter]::ToUInt32((BytesAt3 ($block+0x174) 4),0)
$fb = BytesAt3 ($prov+0x110) 12
$fx=[BitConverter]::ToSingle($fb,0); $fy=[BitConverter]::ToSingle($fb,4)
"player feet = ({0:F2},{1:F2})" -f $fx,$fy
$hitList = [RIG]::FindValue($pidG, 0x01E4CE90)
$rows = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = BytesAt3 $hit 0x90
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($dist -gt 250) { continue }
  [void]$rows.Add([pscustomobject]@{ base=$hit; id=[BitConverter]::ToUInt32($d,4); cnt=[BitConverter]::ToUInt16($d,0x66); dist=$dist })
}
"humanoids within 250m: $($rows.Count)"
""
"--- children-count histogram ---"
$rows | Group-Object cnt | Sort-Object { [int]$_.Name } | ForEach-Object { "  children={0,2}: {1}" -f $_.Name, $_.Count }
""
"--- bodies with children >= 21 (non-player rigs) ---"
$rows | Where-Object { $_.cnt -ge 21 } | Sort-Object dist | Select-Object -First 15 | ForEach-Object { "  base=0x{0:X8} id=0x{1:X8} children={2} d={3:F1}" -f $_.base, $_.id, $_.cnt, $_.dist }
[void][RIG]::CloseHandle($h)
