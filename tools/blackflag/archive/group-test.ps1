$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class GRP {
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

$h = [GRP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [GRP]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [GRP]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [GRP]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [GRP]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [GRP]::Read($h, $block + 0x50, 12)
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

"scanning..."
$hitList = [GRP]::Find($pidG, 0x01E4CE90)
$all = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [GRP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 2.5 -or $dist -gt 15) { continue }
  [void]$all.Add([pscustomobject]@{
    base=[Int64]$hit; id=[BitConverter]::ToUInt32($d,4); cnt=[BitConverter]::ToUInt16($d,0x66)
    f74=[BitConverter]::ToSingle($d,0x74); f7c=[BitConverter]::ToSingle($d,0x7C)
    x=$x; y=$y; z=$z; dist=$dist
  })
}
"objects 2.5-15m: $($all.Count)"

$gA = $all | Where-Object { [Math]::Abs($_.f7c + 0.5) -lt 0.02 -and $_.cnt -ge 8 }
$gB = $all | Where-Object { [Math]::Abs($_.f7c + 2.0) -lt 0.05 }
$gC = $all | Where-Object { ($_.base -notin $gA.base) -and ($_.base -notin $gB.base) }
"group A (humanoid f7c=-0.5, children>=8): $($gA.Count)"
$gA | Select-Object -First 10 | ForEach-Object { "    0x{0:X8} id=0x{1:X8} cnt={2} f7c={3:F2} d={4:F1}" -f $_.base, $_.id, $_.cnt, $_.f7c, $_.dist }
"group B (marker f7c=-2.0): $($gB.Count)"
"group C (other): $($gC.Count)"

function ShoveGroup($name, $group) {
  if ($group.Count -eq 0) { "   [$name] empty"; return }
  $entries = New-Object System.Collections.ArrayList
  foreach ($o in $group) { [void]$entries.Add([pscustomobject]@{ base=$o.base; x=$o.x; y=$o.y; z=$o.z }) }
  "   [$name] shoving $($entries.Count) objects +5m sideways, hold 2.5s"
  for ($k = 1; $k -le 5; $k++) {
    foreach ($en in $entries) {
      $bytes = [BitConverter]::GetBytes([single]($en.x + 5.0)) + [BitConverter]::GetBytes([single]$en.y) + [BitConverter]::GetBytes([single]($en.z + 1.0))
      [void][GRP]::Write($h, $en.base + 0x40, $bytes)
    }
    Start-Sleep -Milliseconds 500
  }
  $held = 0
  foreach ($en in $entries) {
    $b = [GRP]::Read($h, $en.base + 0x40, 12)
    if ([Math]::Abs([BitConverter]::ToSingle($b,0) - ($en.x + 5.0)) -lt 0.7) { $held++ }
  }
  "   [$name] held: $held / $($entries.Count)"
  foreach ($en in $entries) {
    $bytes = [BitConverter]::GetBytes([single]$en.x) + [BitConverter]::GetBytes([single]$en.y) + [BitConverter]::GetBytes([single]$en.z)
    [void][GRP]::Write($h, $en.base + 0x40, $bytes)
  }
  Start-Sleep -Milliseconds 1500
}

""
"== group A =="
ShoveGroup "A" $gA
"== group B =="
ShoveGroup "B" $gB
"== group C =="
ShoveGroup "C" $gC

""
"== follower (humanoid pick) =="
$t = $gA | Sort-Object dist | Select-Object -First 1
if (-not $t) { $t = $all | Where-Object { [Math]::Abs($_.f7c + 0.5) -lt 0.02 } | Sort-Object dist | Select-Object -First 1 }
if (-not $t) { "no humanoid target; done"; exit }
"follower: base=0x{0:X8} id=0x{1:X8} children={2} d={3:F1}" -f $t.base, $t.id, $t.cnt, $t.dist
$lastX = $eye.x; $lastY = $eye.y
$dirX = 0.0; $dirY = 0.0
for ($i = 1; $i -le 100; $i++) {
  $e = GetEye
  if (-not $e) { Start-Sleep -Milliseconds 320; continue }
  $mx = $e.x - $lastX; $my = $e.y - $lastY
  $ml = [Math]::Sqrt($mx*$mx + $my*$my)
  if ($ml -gt 0.03) { $dirX = $mx / $ml; $dirY = $my / $ml }
  $lastX = $e.x; $lastY = $e.y
  $tx = [single]($e.x - $dirX * 2.5)
  $ty = [single]($e.y - $dirY * 2.5)
  $tz = [single]($e.z - 1.2)
  $bytes = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
  [void][GRP]::Write($h, $t.base + 0x40, $bytes)
  if ($i % 10 -eq 0) {
    $chk = [GRP]::Read($h, $t.base + 0x40, 12)
    $bx = [BitConverter]::ToSingle($chk,0); $by = [BitConverter]::ToSingle($chk,4)
    "   t={0,5:F1}s player=({1:F1},{2:F1}) body=({3:F1},{4:F1}) gap={5:F1}m" -f ($i*0.32), $e.x, $e.y, $bx, $by, ([Math]::Sqrt([Math]::Pow($bx-$e.x,2) + [Math]::Pow($by-$e.y,2)))
  }
  Start-Sleep -Milliseconds 320
}
"done $(Get-Date -Format HH:mm:ss)"
[void][GRP]::CloseHandle($h)
