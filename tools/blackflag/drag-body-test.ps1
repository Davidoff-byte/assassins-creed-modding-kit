$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class DRG {
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

$h = [DRG]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [DRG]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [DRG]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [DRG]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [DRG]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [DRG]::ReadPtr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $b = [DRG]::Read($h, $prov + 0x110, 12)
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}

"waiting for in-world..."
$deadline = (Get-Date).AddMinutes(10)
$sane = 0
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $e = GetEye
  if ($e -and ([Math]::Abs($e.x) + [Math]::Abs($e.y) -gt 100)) { $sane++ } else { $sane = 0 }
  if ($sane -ge 2) { break }
}
if ($sane -lt 2) { "game never got in-world; aborting"; exit }
$eye = GetEye
"in-world $(Get-Date -Format HH:mm:ss); player feet = ({0:F2}, {1:F2}, {2:F2})" -f $eye.x, $eye.y, $eye.z

"scanning for 0xD-family humanoids (id < 0x10000, f7c=-0.5, children>=16)..."
$hitList = [DRG]::Find($pidG, 0x01E4CE90)
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [DRG]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  if ([BitConverter]::ToUInt16($d, 0x66) -lt 16) { continue }
  $id = [BitConverter]::ToUInt32($d, 4)
  if ($id -ge 0x00010000) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 15 -or $dist -gt 250) { continue }
  [void]$cands.Add([pscustomobject]@{ base=[Int64]$hit; id=$id; cnt=[BitConverter]::ToUInt16($d,0x66); x=$x; y=$y; z=$z; dist=$dist })
}
"candidates: $($cands.Count)"
$cands | Sort-Object dist | Select-Object -First 10 | ForEach-Object {
  "   0x{0:X8} id=0x{1:X8} cnt={2} d={3:F1} pos=({4:F1},{5:F1},{6:F1})" -f $_.base, $_.id, $_.cnt, $_.dist, $_.x, $_.y, $_.z
}
$t = $cands | Sort-Object dist | Select-Object -First 1
if (-not $t) { "no candidate found; abort"; exit }
"CHOSEN: 0x{0:X8} id=0x{1:X8} children={2} at d={3:F1}" -f $t.base, $t.id, $t.cnt, $t.dist

# bring it right in front of the player and hold
$tx = [single]($eye.x + 2.0)
$ty = [single]($eye.y + 0.0)
$tz = [single]($eye.z + 0.2)
"reeling it in and holding at ({0:F1},{1:F1},{2:F1}) for ~8s..." -f $tx, $ty, $tz
for ($i = 1; $i -le 40; $i++) {
  $bytes = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
  [void][DRG]::Write($h, $t.base + 0x40, $bytes)
  if ($i % 10 -eq 0) {
    $chk = [DRG]::Read($h, $t.base + 0x40, 12)
    $cx=[BitConverter]::ToSingle($chk,0); $cy=[BitConverter]::ToSingle($chk,4); $cz=[BitConverter]::ToSingle($chk,8)
    $g = [Math]::Sqrt([Math]::Pow($cx-$eye.x,2)+[Math]::Pow($cy-$eye.y,2))
    "   t={0:F1}s body=({1:F1},{2:F1},{3:F1}) gapToPlayer={4:F1}m" -f ($i*0.2), $cx, $cy, $cz, $g
  }
  Start-Sleep -Milliseconds 200
}
"released. $(Get-Date -Format HH:mm:ss)"
[void][DRG]::CloseHandle($h)
