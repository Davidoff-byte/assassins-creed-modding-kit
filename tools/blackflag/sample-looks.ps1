# Look-sampling tool: brings up to N distinct crowd clothing variants right in front of the
# player, one at a time, so the human can pick the closest "Edward look".
# Dedupes variants by FNV-1a hash of each body's child-part class (vtable) sequence.
# Default hold 12 s, gap 2 s (body returns home in the gap). Run with the game focused + in-world.
param([int]$Samples = 8, [int]$HoldSec = 12, [int]$GapSec = 2, [string]$FwdAxis = "Y", [switch]$All, [int]$MinDist = 4)

$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class LKS {
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

$h = [LKS]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [LKS]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [LKS]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [LKS]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [LKS]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [LKS]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $q = [LKS]::Read($h, $prov + 0x100, 16)
  $f = [LKS]::Read($h, $prov + 0x110, 12)
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

"waiting for in-world (k+1 = you, keep AC4 focused)..."
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

"scanning bodies (0xD family, 16-22 parts, id<0x10000, 4-150 m)..."
$hitList = [LKS]::Find($pidG, 0x01E4CE90)
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [LKS]::Read($h, $hit, 0x90)
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
  if ($dist -lt $MinDist -or $dist -gt 150) { continue }
  $kids = [int64]([uint32]([BitConverter]::ToUInt32($d, 0x60)))
  [void]$cands.Add([pscustomobject]@{ base=[Int64]$hit; id=$id; cnt=$cnt; x=$x; y=$y; z=$z; dist=$dist; kids=$kids })
}
"candidates: $($cands.Count)"

$sorted = @($cands | Sort-Object dist)
foreach ($c in $sorted) {
  $fh = [uint64]2166136261
  if ($c.kids -ge 0x10000) {
    for ($i = 0; $i -lt $c.cnt; $i++) {
      $cc = [int64]([uint32]([LKS]::Ptr($h, $c.kids + $i*4)))
      $vt = [uint64]0
      if ($cc -ge 0x10000) { $vt = [uint64]([uint32]([LKS]::Ptr($h, $cc))) }
      $fh = $fh -bxor $vt
      $fh = ($fh * 16777619) % 4294967296
    }
  }
  $c | Add-Member -NotePropertyName fp -NotePropertyValue ([uint32]$fh)
}
$picked = New-Object System.Collections.ArrayList
if ($All) {
  foreach ($c in $sorted) { [void]$picked.Add($c); if ($picked.Count -ge $Samples) { break } }
} else {
  $seen = @{}
  $fresh = New-Object System.Collections.ArrayList
  $dupes = New-Object System.Collections.ArrayList
  foreach ($c in $sorted) {
    $key = "" + $c.cnt + ":" + $c.fp
    if ($seen.ContainsKey($key)) { [void]$dupes.Add($c) } else { $seen[$key] = $true; [void]$fresh.Add($c) }
  }
  foreach ($c in $fresh) { [void]$picked.Add($c); if ($picked.Count -ge $Samples) { break } }
  if ($picked.Count -lt $Samples) { foreach ($c in $dupes) { [void]$picked.Add($c); if ($picked.Count -ge $Samples) { break } } }
}
if ($picked.Count -lt 2) { "only $($picked.Count) distinct candidate(s); abort"; exit }
"picked $($picked.Count) samples:"
$k = 0
foreach ($c in $picked) {
  $k++
  "   [{0}] id=0x{1:X8} cnt={2} fp=0x{3:X8} dist={4:F1} pos=({5:F1},{6:F1},{7:F1})" -f $k,$c.id,$c.cnt,$c.fp,$c.dist,$c.x,$c.y,$c.z
}
""
"NOTE: if bodies do NOT appear in front of you, tell the operator (one axis flag flips it)."
"starting in 3 s - watch the game, count the samples..."
Start-Sleep -Seconds 3

$k = 0
foreach ($c in $picked) {
  $k++
  $eye = GetFeet
  $wait = 0
  while ((-not $eye -or ([Math]::Abs($eye.x) + [Math]::Abs($eye.y) -le 10)) -and $wait -lt 120) {
    if ($wait -eq 0) { "waiting for player view (focus AC4 - waiting up to 120 s)..." }
    Start-Sleep -Seconds 1
    $wait++
    $eye = GetFeet
  }
  if (-not $eye -or ([Math]::Abs($eye.x) + [Math]::Abs($eye.y) -le 10)) { "player view not back after 120 s; stopping"; break }
  $v = RotateVec 0 1 0 $eye.qx $eye.qy $eye.qz $eye.qw
  $vx = [double]$v[0]; $vy = [double]$v[1]
  $L = [Math]::Sqrt($vx*$vx + $vy*$vy)
  if ($L -lt 0.1) { $vx = 1.0; $vy = 0.0; $L = 1.0 }
  $vx = $vx/$L; $vy = $vy/$L
  "[SAMPLE $k/$($picked.Count)] id=0x$('{0:X8}' -f $c.id) fp=0x$('{0:X8}' -f $c.fp) - holding ${HoldSec}s at ~3.4 m in front"
  $end = (Get-Date).AddSeconds($HoldSec)
  while ((Get-Date) -lt $end) {
    $eye = GetFeet
    if ($eye -and ([Math]::Abs($eye.x) + [Math]::Abs($eye.y) -gt 10)) {
      $tx = [single]($eye.x + $vx*3.4)
      $ty = [single]($eye.y + $vy*3.4)
      $tz = [single]$eye.z
      $pb = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
      [void][LKS]::Write($h, $c.base + 0x40, $pb)
      $dx = $eye.x - $tx; $dy = $eye.y - $ty
      $dl = [Math]::Sqrt($dx*$dx + $dy*$dy)
      if ($dl -gt 0.05) {
        $yaw = [Math]::Atan2(-$dx/$dl, $dy/$dl)
        $cc2 = [Math]::Cos($yaw); $ss2 = [Math]::Sin($yaw)
        $z0 = [BitConverter]::GetBytes([single]0)
        $rb = [BitConverter]::GetBytes([single]$cc2) + [BitConverter]::GetBytes([single]$ss2) + $z0 + $z0
        $rb = $rb + [BitConverter]::GetBytes([single](-$ss2)) + [BitConverter]::GetBytes([single]$cc2) + $z0 + $z0
        [void][LKS]::Write($h, $c.base + 0x10, $rb)
      }
    }
    Start-Sleep -Milliseconds 150
  }
  "[gap ${GapSec}s - returning it home]"
  $ob = [BitConverter]::GetBytes([single]$c.x) + [BitConverter]::GetBytes([single]$c.y) + [BitConverter]::GetBytes([single]$c.z)
  $end2 = (Get-Date).AddSeconds($GapSec)
  while ((Get-Date) -lt $end2) {
    [void][LKS]::Write($h, $c.base + 0x40, $ob)
    Start-Sleep -Milliseconds 200
  }
}
""
"DONE - all $($picked.Count) samples shown. Which number looked closest to Edward's outfit? (or none)"
[void][LKS]::CloseHandle($h)
