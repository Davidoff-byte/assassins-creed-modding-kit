$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class PUP {
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

$h = [PUP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [PUP]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [PUP]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [PUP]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [PUP]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [PUP]::Read($h, $block + 0x50, 12)
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
"in-world $(Get-Date -Format HH:mm:ss); player eye = ({0:F2}, {1:F2}, {2:F2})" -f $eye.x, $eye.y, $eye.z

"scanning for character candidates (child count >= 10)..."
$hitList = [PUP]::Find($pidG, 0x01E4CE90)
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [PUP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $cc = [BitConverter]::ToUInt16($d, 0x66)
  if ($cc -lt 10) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 3 -or $dist -gt 30) { continue }
  [void]$cands.Add([pscustomobject]@{ base=[Int64]$hit; id=[BitConverter]::ToUInt32($d,4); cc=$cc; x=$x; y=$y; z=$z; dist=$dist; f74=[BitConverter]::ToSingle($d,0x74) })
}
"character candidates 3-30m: $($cands.Count)"
$cands | Sort-Object dist | Select-Object -First 12 | ForEach-Object {
  "   base=0x{0:X8} id=0x{1:X8} children={2} f74={3:F2} dist={4:F1} pos=({5:F2},{6:F2},{7:F2})" -f $_.base, $_.id, $_.cc, $_.f74, $_.dist, $_.x, $_.y, $_.z
}
$t = $cands | Sort-Object dist | Select-Object -First 1
if (-not $t) { "no character candidate found; abort"; exit }
"CHOSEN: base=0x{0:X8} id=0x{1:X8} children={2} at ({3:F2},{4:F2},{5:F2}), {6:F1}m away" -f $t.base, $t.id, $t.cc, $t.x, $t.y, $t.z, $t.dist

# target: 2m to the +X side of the player, at ground level of the player's feet
$tx = [single]($eye.x + 2.0)
$ty = [single]($eye.y + 0.5)
$tz = [single]($eye.z - 1.2)

"walking it over (12 steps)..."
for ($i = 1; $i -le 12; $i++) {
  $f = $i / 12.0
  $px = [single]($t.x + ($tx - $t.x) * $f)
  $py = [single]($t.y + ($ty - $t.y) * $f)
  $pz = [single]($t.z + ($tz - $t.z) * $f)
  $bytes = [BitConverter]::GetBytes($px) + [BitConverter]::GetBytes($py) + [BitConverter]::GetBytes($pz)
  [void][PUP]::Write($h, $t.base + 0x40, $bytes)
  Start-Sleep -Milliseconds 420
}
"holding next to you (4s)..."
$held = 0
for ($i = 1; $i -le 10; $i++) {
  $bytes = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
  [void][PUP]::Write($h, $t.base + 0x40, $bytes)
  Start-Sleep -Milliseconds 400
  $chk = [PUP]::Read($h, $t.base + 0x40, 12)
  $cx = [BitConverter]::ToSingle($chk,0); $cy = [BitConverter]::ToSingle($chk,4); $cz = [BitConverter]::ToSingle($chk,8)
  $dd = [Math]::Sqrt([Math]::Pow($cx-$tx,2) + [Math]::Pow($cy-$ty,2) + [Math]::Pow($cz-$tz,2))
  if ($dd -lt 0.7) { $held++ }
}
"held at target in $held / 10 checks"
$chk = [PUP]::Read($h, $t.base + 0x40, 12)
"final pos = ({0:F2}, {1:F2}, {2:F2})   (you were at ({3:F2}, {4:F2}))" -f ([BitConverter]::ToSingle($chk,0)), ([BitConverter]::ToSingle($chk,4)), ([BitConverter]::ToSingle($chk,8)), $eye.x, $eye.y
"leaving it there - its own AI will take over now."
[void][PUP]::CloseHandle($h)
"done $(Get-Date -Format HH:mm:ss)"
