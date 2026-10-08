# Calibration: hops ONE nearby body around the player to 4 candidate "front" spots (90 deg apart),
# 9 s per spot, with readback so we know the drive actually landed. The human reports which spot
# (1-4) was DIRECTLY in front of them. Spots: 1=+Y convention, 2=+X, 3=-Y, 4=-X.
param([int]$HoldSec = 9)

$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class CLB {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long a, int s) { byte[] b = new byte[s]; IntPtr r; ReadProcessMemory(h, (IntPtr)a, b, s, out r); return b; }
  public static long Ptr(IntPtr h, long a) { return BitConverter.ToUInt32(Read(h, a, 4), 0); }
  public static bool Write(IntPtr h, long a, byte[] b) { IntPtr w; return WriteProcessMemory(h, (IntPtr)a, b, b.Length, out w); }
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

$h = [CLB]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [CLB]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [CLB]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [CLB]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [CLB]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [CLB]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $q = [CLB]::Read($h, $prov + 0x100, 16)
  $f = [CLB]::Read($h, $prov + 0x110, 12)
  return [pscustomobject]@{
    x=[BitConverter]::ToSingle($f,0); y=[BitConverter]::ToSingle($f,4); z=[BitConverter]::ToSingle($f,8);
    qx=[BitConverter]::ToSingle($q,0); qy=[BitConverter]::ToSingle($q,4); qz=[BitConverter]::ToSingle($q,8); qw=[BitConverter]::ToSingle($q,12)
  }
}

function RotateVec([double]$vx,[double]$vy,[double]$vz,[double]$qx,[double]$qy,[double]$qz,[double]$qw) {
  $cx = $qy*$vz - $qz*$vy; $cy = $qz*$vx - $qx*$vz; $cz = $qx*$vy - $qy*$vx
  $tx = 2*$cx; $ty = 2*$cy; $tz = 2*$cz
  $ux = $qy*$tz - $qz*$ty; $uy = $qz*$tx - $qx*$tz; $uz = $qx*$ty - $qy*$tx
  return @(($vx + $qw*$tx + $ux), ($vy + $qw*$ty + $uy), ($vz + $qw*$tz + $uz))
}

"waiting for in-world (keep AC4 focused)..."
$deadline = (Get-Date).AddMinutes(10)
$sane = 0
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $e = GetFeet
  if ($e -and ([Math]::Abs($e.x) + [Math]::Abs($e.y) -gt 10)) { $sane++ } else { $sane = 0 }
  if ($sane -ge 2) { break }
}
if ($sane -lt 2) { "never got in-world; abort"; exit }
$eye = GetFeet
"in-world; player feet = ({0:F2},{1:F2},{2:F2}) quat=({3:F3},{4:F3},{5:F3},{6:F3})" -f $eye.x,$eye.y,$eye.z,$eye.qx,$eye.qy,$eye.qz,$eye.qw

"scanning for one nearby body..."
$hitList = [CLB]::Find($pidG, 0x01E4CE90)
$best = $null
foreach ($hit in $hitList) {
  $d = [CLB]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  if ($cnt -lt 16 -or $cnt -gt 22) { continue }
  $id = [BitConverter]::ToUInt32($d, 4)
  if ($id -ge 0x00010000) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 5 -or $dist -gt 60) { continue }
  if (-not $best -or $dist -lt $best.dist) {
    $best = [pscustomobject]@{ base=[Int64]$hit; id=$id; cnt=$cnt; x=$x; y=$y; z=$z; dist=$dist }
  }
}
if (-not $best) { "no body found; abort"; exit }
"chosen: id=0x{0:X8} cnt={1} dist={2:F1}" -f $best.id, $best.cnt, $best.dist

# four candidate front directions, 90 deg apart
$vY  = RotateVec 0 1 0 $eye.qx $eye.qy $eye.qz $eye.qw
$vX  = RotateVec 1 0 0 $eye.qx $eye.qy $eye.qz $eye.qw
function Norm2([double]$a,[double]$b) {
  $L = [Math]::Sqrt($a*$a + $b*$b)
  if ($L -lt 0.001) { return @(1.0, 0.0) }
  return @(($a/$L), ($b/$L))
}
$p1 = Norm2 $vY[0] $vY[1]
$p2 = Norm2 $vX[0] $vX[1]
$p3 = @(-$p1[0], -$p1[1])
$p4 = @(-$p2[0], -$p2[1])
$spots = @($p1, $p2, $p3, $p4)
"directly in front? spots: 1=(+Y)2=( +X)3=(-Y), 4=(-X) <-- report the number where it stands IN FRONT"
"starting in 3 s - watch the character hop around you, one spot every ${HoldSec}s..."
Start-Sleep -Seconds 3

for ($k = 1; $k -le 4; $k++) {
  $sp = $spots[$k-1]
  "[SPOT $k/4] dir=({0:F3},{1:F3}) - holding ${HoldSec}s" -f $sp[0], $sp[1]
  $end = (Get-Date).AddSeconds($HoldSec)
  $t2 = 0
  while ((Get-Date) -lt $end) {
    $eye = GetFeet
    if ($eye -and ([Math]::Abs($eye.x) + [Math]::Abs($eye.y) -gt 10)) {
      $tx = [single]($eye.x + $sp[0]*4.0)
      $ty = [single]($eye.y + $sp[1]*4.0)
      $tz = [single]$eye.z
      $pb = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
      [void][CLB]::Write($h, $best.base + 0x40, $pb)
      $dx = $eye.x - $tx; $dy = $eye.y - $ty
      $dl = [Math]::Sqrt($dx*$dx + $dy*$dy)
      if ($dl -gt 0.05) {
        $yaw = [Math]::Atan2(-$dx/$dl, $dy/$dl)
        $cc = [Math]::Cos($yaw); $ss = [Math]::Sin($yaw)
        $z0 = [BitConverter]::GetBytes([single]0)
        $rb = [BitConverter]::GetBytes([single]$cc) + [BitConverter]::GetBytes([single]$ss) + $z0 + $z0
        $rb = $rb + [BitConverter]::GetBytes([single](-$ss)) + [BitConverter]::GetBytes([single]$cc) + $z0 + $z0
        [void][CLB]::Write($h, $best.base + 0x10, $rb)
      }
      $t2++
      if ($t2 % 15 -eq 0) {
        $chk = [CLB]::Read($h, $best.base + 0x40, 12)
        $cx = [BitConverter]::ToSingle($chk,0); $cy = [BitConverter]::ToSingle($chk,4)
        $err = [Math]::Sqrt([Math]::Pow($cx-$tx,2) + [Math]::Pow($cy-$ty,2))
        "   t~{0:F1}s landed err={1:F2} m" -f ($t2 * 0.15), $err
      }
    }
    Start-Sleep -Milliseconds 150
  }
  # 1 s gap at home
  $ob = [BitConverter]::GetBytes([single]$best.x) + [BitConverter]::GetBytes([single]$best.y) + [BitConverter]::GetBytes([single]$best.z)
  $end2 = (Get-Date).AddSeconds(1)
  while ((Get-Date) -lt $end2) { [void][CLB]::Write($h, $best.base + 0x40, $ob); Start-Sleep -Milliseconds 200 }
}
""
"DONE. Which spot number (1-4) had the character DIRECTLY in front of you?"
[void][CLB]::CloseHandle($h)
