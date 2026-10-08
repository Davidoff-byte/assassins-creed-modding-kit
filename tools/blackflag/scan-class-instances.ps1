$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class SCN2 {
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

$hits = [SCN2]::Find($pidG, 0x01E4CE90)
"occurrences of vtable 0x01E4CE90: $($hits.Count)"

$objs = New-Object System.Collections.ArrayList
foreach ($h in $hits) {
  $d = [SCN2]::ReadAt($pidG, $h, 0x90)
  if ($d.Length -lt 0x90) { continue }
  $mark = [BitConverter]::ToUInt32($d, 0x68)
  if ($mark -ne 0x04DD5F8C) { continue }
  $o = [pscustomobject]@{
    base = [Int64]$h
    id = [BitConverter]::ToUInt32($d, 4)
    node = [BitConverter]::ToUInt32($d, 8)
    x = [BitConverter]::ToSingle($d, 0x40)
    y = [BitConverter]::ToSingle($d, 0x44)
    z = [BitConverter]::ToSingle($d, 0x48)
    f64 = [BitConverter]::ToUInt32($d, 0x64)
    f74 = [BitConverter]::ToSingle($d, 0x74)
    f7c = [BitConverter]::ToSingle($d, 0x7C)
  }
  [void]$objs.Add($o)
}
"signature objects (vtable + marker at +0x68): $($objs.Count)"

$player = $objs | Where-Object { $_.base -eq 0x44B38810 }
if ($player) {
  "player object: base=0x{0:X8} id=0x{1:X8} pos=({2:F2}, {3:F2}, {4:F2}) f64=0x{5:X8} f74={6:F2} f7c={7:F2}" -f $player.base, $player.id, $player.x, $player.y, $player.z, $player.f64, $player.f74, $player.f7c
  $px = $player.x; $py = $player.y
} else {
  "player object 0x44B38810 not in list"
  $px = $objs[0].x; $py = $objs[0].y
}

$near = $objs | Where-Object { [Math]::Abs($_.x - $px) -lt 400 -and [Math]::Abs($_.y - $py) -lt 400 } |
  Sort-Object { [Math]::Sqrt([Math]::Pow($_.x - $px, 2) + [Math]::Pow($_.y - $py, 2)) }
"objects within 400m of player: $($near.Count)"
$near | Select-Object -First 70 | ForEach-Object {
  $dist = [Math]::Sqrt([Math]::Pow($_.x - $px, 2) + [Math]::Pow($_.y - $py, 2))
  "  base=0x{0:X8} id=0x{1:X8} pos=({2:F2}, {3:F2}, {4:F2}) d={5:F1} f64=0x{6:X8} f74={7:F2}" -f $_.base, $_.id, $_.x, $_.y, $_.z, $dist, $_.f64, $_.f74
}

""
"---- movement check (1.6s) on objects within 400m ----"
$sample = $near | Select-Object -First 200
$t0 = $sample | ForEach-Object { $_.base }
Start-Sleep -Milliseconds 1600
$moved = @()
foreach ($b in $t0) {
  $d = [SCN2]::ReadAt($pidG, $b, 0x50)
  if ($d.Length -lt 0x50) { continue }
  $nx = [BitConverter]::ToSingle($d, 0x40)
  $ny = [BitConverter]::ToSingle($d, 0x44)
  $nz = [BitConverter]::ToSingle($d, 0x48)
  $old = $sample | Where-Object { $_.base -eq $b } | Select-Object -First 1
  $dd = [Math]::Sqrt([Math]::Pow($nx - $old.x, 2) + [Math]::Pow($ny - $old.y, 2) + [Math]::Pow($nz - $old.z, 2))
  if ($dd -gt 0.05) {
    $moved += [pscustomobject]@{ base = $b; id = $old.id; from = ("({0:F2},{1:F2},{2:F2})" -f $old.x, $old.y, $old.z); to = ("({0:F2},{1:F2},{2:F2})" -f $nx, $ny, $nz); delta = $dd }
  }
}
"moved: $($moved.Count) of $($t0.Count)"
$moved | Sort-Object delta -Descending | Select-Object -First 40 | ForEach-Object {
  "  base=0x{0:X8} id=0x{1:X8} {2} -> {3}  d={4:F2}" -f $_.base, $_.id, $_.from, $_.to, $_.delta
}
