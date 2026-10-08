# Compares one render-part child (class 0x01E7F568) of the player vs a civilian.
# Differences that look like shared-resource pointers are candidate MODEL references.
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class RP {
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
$h = [RP]::Open($pidG)
function RB([int64]$a,[int]$n){ return [RP]::Read($h,$a,$n) }
"waiting for in-world..."
$deadline = (Get-Date).AddMinutes(10)
$fx = 0.0; $fy = 0.0; $got = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $mgr = [BitConverter]::ToUInt32((RB 0x2ABE588 4),0); if ($mgr -eq 0) { continue }
  $holder = [BitConverter]::ToUInt32((RB ($mgr+0x4C) 4),0); if ($holder -eq 0) { continue }
  $camobj = [BitConverter]::ToUInt32((RB $holder 4),0); if ($camobj -eq 0) { continue }
  $block = [BitConverter]::ToUInt32((RB ($camobj+0x68) 4),0); if ($block -eq 0) { continue }
  $prov = [BitConverter]::ToUInt32((RB ($block+0x174) 4),0); if ($prov -eq 0) { continue }
  $fb = RB ($prov+0x110) 12
  $x=[BitConverter]::ToSingle($fb,0); $y=[BitConverter]::ToSingle($fb,4)
  if ([Math]::Abs($x) + [Math]::Abs($y) -gt 100) { $fx=$x; $fy=$y; $got=$true; break }
}
if (-not $got) { "never got in-world; abort"; exit }
"player feet = ({0:F2},{1:F2})" -f $fx,$fy
$hitList = [RP]::FindValue($pidG, 0x01E4CE90)
$player = 0; $crowd = 0
foreach ($hit in $hitList) {
  $d = RB $hit 0x90
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($cnt -ge 24 -and $dist -lt 3) { $player = $hit }
  if ($crowd -eq 0 -and $cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 3 -and $dist -lt 120) { $crowd = $hit }
}
"player node = 0x$('{0:X8}' -f $player)  crowd node = 0x$('{0:X8}' -f $crowd)"
if ($player -eq 0 -or $crowd -eq 0) { "missing node; abort"; exit }

function RenderParts([int64]$n){
  $cp = [int64]([uint32]([BitConverter]::ToUInt32((RB ($n + 0x60) 4),0)))
  $cc = [BitConverter]::ToUInt16((RB ($n + 0x66) 2), 0)
  $res = @()
  for ($i=0; $i -lt $cc; $i++) {
    $c = [int64]([uint32]([BitConverter]::ToUInt32((RB ($cp + $i*4) 4),0)))
    if ($c -lt 0x10000) { continue }
    $vt = [BitConverter]::ToUInt32((RB $c 4),0)
    $res += [pscustomobject]@{ idx=$i; base=$c; vt=$vt }
  }
  return ,$res
}
$pr = RenderParts $player
$cr = RenderParts $crowd
"player parts of class 0x01E7F568: " + (($pr | Where-Object { $_.vt -eq 0x01E7F568 } | ForEach-Object { $_.idx }) -join ',')
"crowd  parts of class 0x01E7F568: " + (($cr | Where-Object { $_.vt -eq 0x01E7F568 } | ForEach-Object { $_.idx }) -join ',')
$pp = ($pr | Where-Object { $_.vt -eq 0x01E7F568 } | Select-Object -First 1)
$cp2 = ($cr | Where-Object { $_.vt -eq 0x01E7F568 } | Select-Object -First 1)
if (-not $pp -or -not $cp2) { "no render part found; abort"; exit }
"player render part = 0x$('{0:X8}' -f $pp.base) (child[$($pp.idx)])"
"crowd  render part = 0x$('{0:X8}' -f $cp2.base) (child[$($cp2.idx)])"
$pd = RB $pp.base 0x120
$cd = RB $cp2.base 0x120
""
"--- diff (offset | PLAYER | CROWD) ---"
for ($off = 0; $off -lt 0x120; $off += 4) {
  $pv = [BitConverter]::ToUInt32($pd, $off)
  $cv = [BitConverter]::ToUInt32($cd, $off)
  if ($pv -eq $cv) { continue }
  $pn = ""; if ($pv -ge 0x400000 -and $pv -lt 0x2F00000) { $pn = "IMG" } elseif ($pv -ge 0x10000 -and $pv -lt 0x7FFF0000) { $pn = "ptr" }
  $cn = ""; if ($cv -ge 0x400000 -and $cv -lt 0x2F00000) { $cn = "IMG" } elseif ($cv -ge 0x10000 -and $cv -lt 0x7FFF0000) { $cn = "ptr" }
  "  +0x{0:X3}: P 0x{1:X8} {2,-4} | C 0x{3:X8} {4,-4}" -f $off, $pv, $pn, $cv, $cn
}
[void][RP]::CloseHandle($h)