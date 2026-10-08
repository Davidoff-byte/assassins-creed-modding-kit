$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class GI {
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
$h = [GI]::Open($pidG)
function ReadAt4([int64]$a,[int]$n){ return [GI]::Read($h,$a,$n) }
"waiting for in-world (focus the game)..."
$deadline = (Get-Date).AddMinutes(10)
$fx = 0.0; $fy = 0.0; $got = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $mgr = [BitConverter]::ToUInt32((ReadAt4 0x2ABE588 4),0)
  if ($mgr -eq 0) { continue }
  $holder = [BitConverter]::ToUInt32((ReadAt4 ($mgr+0x4C) 4),0); if ($holder -eq 0) { continue }
  $camobj = [BitConverter]::ToUInt32((ReadAt4 $holder 4),0); if ($camobj -eq 0) { continue }
  $block = [BitConverter]::ToUInt32((ReadAt4 ($camobj+0x68) 4),0); if ($block -eq 0) { continue }
  $prov = [BitConverter]::ToUInt32((ReadAt4 ($block+0x174) 4),0); if ($prov -eq 0) { continue }
  $fb = ReadAt4 ($prov+0x110) 12
  $x=[BitConverter]::ToSingle($fb,0); $y=[BitConverter]::ToSingle($fb,4)
  if ([Math]::Abs($x) + [Math]::Abs($y) -gt 100) { $fx = $x; $fy = $y; $got = $true; break }
}
if (-not $got) { "never got in-world; abort"; exit }
"player feet = ({0:F2},{1:F2})" -f $fx,$fy
$hitList = [GI]::FindValue($pidG, 0x01E4CE90)
$player = 0
$crowds = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = ReadAt4 $hit 0x90
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$fx,2) + [Math]::Pow($y-$fy,2))
  if ($cnt -ge 24 -and $dist -lt 3) { $player = $hit; continue }
  if ($cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 3 -and $dist -lt 120) {
    [void]$crowds.Add([pscustomobject]@{ base=[int64]$hit; id=$id; cnt=$cnt; dist=$dist })
  }
}
"player node = 0x$('{0:X8}' -f $player)"
$crowds | Sort-Object dist | Select-Object -First 4 | ForEach-Object { "crowd 0x{0:X8} id=0x{1:X8} cnt={2} d={3:F1}" -f $_.base,$_.id,$_.cnt,$_.dist }
if ($player -eq 0) { "no player node; abort"; exit }
$sel = $crowds | Sort-Object dist | Select-Object -First 2
$bases = @($player) + ($sel | ForEach-Object { $_.base })
$names = @("PLAYER") + ($sel | ForEach-Object { "crowd-{0:X4}" -f $_.id })
$dumps = @{}
foreach ($b in $bases) { $dumps[$b] = ReadAt4 ($b + 0xF0) 0x130 }
""
"--- window node+0xF0 .. node+0x21F (16 bytes per line, hex + ascii) ---"
for ($li = 0; $li -lt 0x130; $li += 16) {
  $off = $dumps[$bases[0]].Length
  $line = "  node+0x{0:X3}  " -f (0xF0 + $li)
  foreach ($b in $bases) {
    $d = $dumps[$b]
    $seg = ""
    for ($j = 0; $j -lt 16; $j += 4) { $seg += ("{0:X8} " -f [BitConverter]::ToUInt32($d, $li + $j)) }
    $line += "| " + $seg + " "
  }
  $line
}
""
"--- also: the dword values at the first 'object-like' offsets (node+0x110 for player, node+0x170 for crowd) ---"
foreach ($b in $bases) {
  $d = ReadAt4 $b 0x240
  for ($off = 0x100; $off -lt 0x200; $off += 0x10) {
    $v = [BitConverter]::ToUInt32($d, $off)
    if ($v -ge 0x400000 -and $v -lt 0x2F00000) {
      # candidate object start (IMG pointer = vtable-ish)
      $head = ReadAt4 $v 0x40
      $line = "  0x{0:X8} (+0x{1:X}) first=0x{2:X8}" -f ($b + $off), $off, $v
      for ($j = 4; $j -lt 0x40; $j += 4) { $line += (" {0:X8}" -f [BitConverter]::ToUInt32($head, $j)) }
      $line
    }
  }
}
[void][GI]::CloseHandle($h)