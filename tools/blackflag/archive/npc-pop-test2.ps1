$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class PO2 {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) { byte[] b = new byte[size]; IntPtr r; ReadProcessMemory(h, (IntPtr)addr, b, size, out r); return b; }
  public static long ReadPtr(IntPtr h, long addr) { return BitConverter.ToUInt32(Read(h, addr, 4), 0); }
  public static bool Write(IntPtr h, long addr, byte[] b) { IntPtr w; return WriteProcessMemory(h, (IntPtr)addr, b, b.Length, out w); }
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

$h = [PO2]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [PO2]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [PO2]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [PO2]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [PO2]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [PO2]::Read($h, $block + 0x50, 12)
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}

"waiting for the game to run (movement)..."
$deadline = (Get-Date).AddMinutes(10)
$last = GetEye
$moving = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $cur = GetEye
  if ($cur -and $last) {
    $d = [Math]::Sqrt([Math]::Pow($cur.x-$last.x,2) + [Math]::Pow($cur.y-$last.y,2) + [Math]::Pow($cur.z-$last.z,2))
    if ($d -gt 0.4) { $moving = $true; break }
  }
  $last = $cur
}
if (-not $moving) { "game never started running; aborting"; exit }
$eye = GetEye
"movement detected $(Get-Date -Format HH:mm:ss); player eye = ({0:F2}, {1:F2}, {2:F2})" -f $eye.x, $eye.y, $eye.z

"scanning class instances..."
$hits = [PO2]::Find($pidG, 0x01E4CE90)
$objs = New-Object System.Collections.ArrayList
foreach ($hit in $hits) {
  $d = [PO2]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 4 -or $dist -gt 20) { continue }
  [void]$objs.Add([pscustomobject]@{ base=[Int64]$hit; id=[BitConverter]::ToUInt32($d,4); x=$x; y=$y; z=$z; dist=$dist })
}
"candidates 4-20m: $($objs.Count)"
if ($objs.Count -eq 0) { "none; abort"; exit }

"sampling 2.5s to drop movers (player's own stuff)..."
Start-Sleep -Milliseconds 2500
$calm = New-Object System.Collections.ArrayList
foreach ($o in $objs) {
  $d = [PO2]::Read($h, $o.base + 0x40, 12)
  $nx = [BitConverter]::ToSingle($d,0); $ny = [BitConverter]::ToSingle($d,4); $nz = [BitConverter]::ToSingle($d,8)
  $dd = [Math]::Sqrt([Math]::Pow($nx-$o.x,2) + [Math]::Pow($ny-$o.y,2) + [Math]::Pow($nz-$o.z,2))
  if ($dd -lt 1.5) { $o.x = $nx; $o.y = $ny; $o.z = $nz; [void]$calm.Add($o) }
}
"calm candidates: $($calm.Count)"
$targets = $calm | Sort-Object dist | Select-Object -First 4
$i = 0
foreach ($t in $targets) {
  $i++
  "--- test $i : base=0x{0:X8} id=0x{1:X8} dist={2:F1} pos=({3:F2},{4:F2},{5:F2})" -f $t.base, $t.id, $t.dist, $t.x, $t.y, $t.z
  $orig = [PO2]::Read($h, $t.base + 0x40, 12)
  $ox = [BitConverter]::ToSingle($orig,0); $oy = [BitConverter]::ToSingle($orig,4); $oz = [BitConverter]::ToSingle($orig,8)
  $sticky = 0; $tries = 0
  for ($k = 1; $k -le 6; $k++) {
    $side = 3.0
    if ($k % 2 -eq 0) { $side = -3.0 }
    $nx = [single]($eye.x + $side)
    $ny = [single]($eye.y + 1.0)
    $nz = [single]($eye.z - 1.2)
    $bytes = [BitConverter]::GetBytes([single]$nx) + [BitConverter]::GetBytes([single]$ny) + [BitConverter]::GetBytes([single]$nz)
    [void][PO2]::Write($h, $t.base + 0x40, $bytes)
    Start-Sleep -Milliseconds 500
    $chk = [PO2]::Read($h, $t.base + 0x40, 12)
    $cx = [BitConverter]::ToSingle($chk,0); $cy = [BitConverter]::ToSingle($chk,4); $cz = [BitConverter]::ToSingle($chk,8)
    $tries++
    if ([Math]::Sqrt([Math]::Pow($cx-$nx,2) + [Math]::Pow($cy-$ny,2) + [Math]::Pow($cz-$nz,2)) -lt 0.5) { $sticky++ }
  }
  "    sticky writes: $sticky / $tries"
  $bytes = [BitConverter]::GetBytes([single]$ox) + [BitConverter]::GetBytes([single]$oy) + [BitConverter]::GetBytes([single]$oz)
  [void][PO2]::Write($h, $t.base + 0x40, $bytes)
  Start-Sleep -Milliseconds 1500
}
[void][PO2]::CloseHandle($h)
"done $(Get-Date -Format HH:mm:ss)"
