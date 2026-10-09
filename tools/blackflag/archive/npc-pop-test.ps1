$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class POP {
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

$h = [POP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [POP]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [POP]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [POP]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [POP]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [POP]::Read($h, $block + 0x50, 12)
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}
function Vec3Str($x, $y, $z) { return ("({0:F2}, {1:F2}, {2:F2})" -f $x, $y, $z) }

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
"movement detected $(Get-Date -Format HH:mm:ss)"
$eye = GetEye
"player eye = " + (Vec3Str $eye.x $eye.y $eye.z)

# choose target: prefer the previously walking one, else scan
$target = 0
$known = 0x47661230
$d = [POP]::Read($h, $known, 0x90)
if ($d.Length -ge 0x90 -and [BitConverter]::ToUInt32($d,0) -eq 0x01E4CE90 -and [BitConverter]::ToUInt32($d,0x68) -eq 0x04DD5F8C) {
  $kx = [BitConverter]::ToSingle($d,0x40); $ky = [BitConverter]::ToSingle($d,0x44)
  $kdist = [Math]::Sqrt([Math]::Pow($kx-$eye.x,2) + [Math]::Pow($ky-$eye.y,2))
  "known walker 0x47661230 alive, dist=$([Math]::Round($kdist,1))"
  if ($kdist -gt 3 -and $kdist -lt 60) { $target = $known }
}
if ($target -eq 0) {
  "scanning for a fallback target..."
  $hits = [POP]::Find($pidG, 0x01E4CE90)
  $best = 0; $bestScore = 1e9
  foreach ($hit in $hits) {
    $dd = [POP]::Read($h, $hit, 0x90)
    if ($dd.Length -lt 0x90) { continue }
    if ([BitConverter]::ToUInt32($dd,0x68) -ne 0x04DD5F8C) { continue }
    $x = [BitConverter]::ToSingle($dd,0x40); $y = [BitConverter]::ToSingle($dd,0x44); $z = [BitConverter]::ToSingle($dd,0x48)
    if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
    $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
    if ($dist -lt 3 -or $dist -gt 45) { continue }
    # prefer self-node objects
    $selfN = ([BitConverter]::ToUInt32($dd,8) -eq ($hit + 0x110))
    $score = $dist + $(if ($selfN) { 0 } else { 40 })
    if ($score -lt $bestScore) { $bestScore = $score; $best = $hit }
  }
  $target = $best
}
if ($target -eq 0) { "no suitable target found; aborting"; exit }
$tinfo = [POP]::Read($h, $target, 0x90)
"TARGET base=0x{0:X8} id=0x{1:X8}" -f $target, [BitConverter]::ToUInt32($tinfo,4)

$orig = [POP]::Read($h, $target + 0x40, 12)
$ox = [BitConverter]::ToSingle($orig,0); $oy = [BitConverter]::ToSingle($orig,4); $oz = [BitConverter]::ToSingle($orig,8)
"target original pos = " + (Vec3Str $ox $oy $oz)

"popping it next to the player for ~6s..."
for ($i = 1; $i -le 6; $i++) {
  $side = 2.5
  if ($i % 2 -eq 0) { $side = -2.5 }
  $nx = [single]($eye.x + $side)
  $ny = [single]($eye.y + 1.0)
  $nz = [single]($eye.z - 1.2)
  $bytes = [BitConverter]::GetBytes([single]$nx) + [BitConverter]::GetBytes([single]$ny) + [BitConverter]::GetBytes([single]$nz)
  [void][POP]::Write($h, $target + 0x40, $bytes)
  Start-Sleep -Milliseconds 900
}
$now = [POP]::Read($h, $target + 0x40, 12)
"while held, target pos = " + (Vec3Str ([BitConverter]::ToSingle($now,0)) ([BitConverter]::ToSingle($now,4)) ([BitConverter]::ToSingle($now,8)))

# restore
$bytes = [BitConverter]::GetBytes([single]$ox) + [BitConverter]::GetBytes([single]$oy) + [BitConverter]::GetBytes([single]$oz)
[void][POP]::Write($h, $target + 0x40, $bytes)
Start-Sleep -Milliseconds 400
$fin = [POP]::Read($h, $target + 0x40, 12)
"restored; target pos now = " + (Vec3Str ([BitConverter]::ToSingle($fin,0)) ([BitConverter]::ToSingle($fin,4)) ([BitConverter]::ToSingle($fin,8)))
[void][POP]::CloseHandle($h)
"done $(Get-Date -Format HH:mm:ss)"
