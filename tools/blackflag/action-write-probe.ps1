# action-write-probe.ps1 - B4 make-or-break: write the player's action-state fields
# (0xE0=0x2A, hang 0x8D8=0x3F, flags 0x138/0x8D0 bit0, blend 0x8D4=0xBC) into a CROWD body's
# controller and watch whether it animates the action. Guarded: snapshot + revert; pointer-looking
# fields are only read-modify-written, never blindly overwritten.
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class AWP {
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

$h = [AWP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [AWP]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [AWP]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [AWP]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [AWP]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [AWP]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $q = [AWP]::Read($h, $prov + 0x100, 16)
  $f = [AWP]::Read($h, $prov + 0x110, 12)
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
"in-world; player feet = ({0:F1},{1:F1},{2:F1})" -f $eye.x, $eye.y, $eye.z

"finding player + civ nodes..."
$hitList = [AWP]::Find($pidG, 0x01E4CE90)
$playerNode = 0; $civNode = 0
foreach ($hit in $hitList) {
  $d = [AWP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($cnt -ge 24 -and $dist -lt 5) { $playerNode = $hit }
  if ($civNode -eq 0 -and $cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 4 -and $dist -lt 60) { $civNode = $hit }
}
"player node = 0x$('{0:X8}' -f $playerNode)  civ node = 0x$('{0:X8}' -f $civNode)"
if ($playerNode -eq 0 -or $civNode -eq 0) { "missing nodes; abort"; exit }

$pCtl = [int64]([uint32]([AWP]::Ptr($h, $playerNode + 0xE8)))
$cCtl = [int64]([uint32]([AWP]::Ptr($h, $civNode + 0xE8)))
"player ctl@E8 = 0x$('{0:X8}' -f $pCtl)   civ ctl@E8 = 0x$('{0:X8}' -f $cCtl)"
if ($pCtl -lt 0x10000 -or $cCtl -lt 0x10000) { "controller pointers bad; abort"; exit }

# player's reference values
"player ctl fields: E0=0x{0:X8} 8D4=0x{1:X8} 8D8=0x{2:X8} 138=0x{3:X8} 8D0=0x{4:X8}" -f ([uint32]([AWP]::Ptr($h,$pCtl+0xE0))), ([uint32]([AWP]::Ptr($h,$pCtl+0x8D4))), ([uint32]([AWP]::Ptr($h,$pCtl+0x8D8))), ([uint32]([AWP]::Ptr($h,$pCtl+0x138))), ([uint32]([AWP]::Ptr($h,$pCtl+0x8D0)))

# snapshot civ controller fields + originals
function Snap([int64]$c) {
  $r = @{}
  foreach ($k in @('E0','8D4','8D8','138','8D0')) {
    $off = switch ($k) { 'E0' {0xE0} '8D4' {0x8D4} '8D8' {0x8D8} '138' {0x138} '8D0' {0x8D0} }
    $r[$k] = [uint32]([AWP]::Ptr($h, $c + $off))
  }
  return $r
}
$orig = Snap $cCtl
"civ  ctl fields: E0=0x{0:X8} 8D4=0x{1:X8} 8D8=0x{2:X8} 138=0x{3:X8} 8D0=0x{4:X8}" -f $orig['E0'], $orig['8D4'], $orig['8D8'], $orig['138'], $orig['8D0']

# bring the body in front + keep it there
function DriveHold([int]$sec) {
  $end = (Get-Date).AddSeconds($sec)
  while ((Get-Date) -lt $end) {
    $eye = GetFeet
    if ($eye -and ([Math]::Abs($eye.x) + [Math]::Abs($eye.y) -gt 10)) {
      $v = RotateVec 0 1 0 $eye.qx $eye.qy $eye.qz $eye.qw
      $vx = [double]$v[0]; $vy = [double]$v[1]
      $L = [Math]::Sqrt($vx*$vx + $vy*$vy)
      if ($L -lt 0.1) { $vx = 1.0; $vy = 0.0; $L = 1.0 }
      $vx = $vx/$L; $vy = $vy/$L
      $tx = [single]($eye.x + $vx*4.0)
      $ty = [single]($eye.y + $vy*4.0)
      $tz = [single]$eye.z
      $pb = [BitConverter]::GetBytes($tx) + [BitConverter]::GetBytes($ty) + [BitConverter]::GetBytes($tz)
      [void][AWP]::Write($h, $civNode + 0x40, $pb)
      $dx = $eye.x - $tx; $dy = $eye.y - $ty
      $dl = [Math]::Sqrt($dx*$dx + $dy*$dy)
      if ($dl -gt 0.05) {
        $yaw = [Math]::Atan2(-$dx/$dl, $dy/$dl)
        $cc = [Math]::Cos($yaw); $ss = [Math]::Sin($yaw)
        $z0 = [BitConverter]::GetBytes([single]0)
        $rb = [BitConverter]::GetBytes([single]$cc) + [BitConverter]::GetBytes([single]$ss) + $z0 + $z0
        $rb = $rb + [BitConverter]::GetBytes([single](-$ss)) + [BitConverter]::GetBytes([single]$cc) + $z0 + $z0
        [void][AWP]::Write($h, $civNode + 0x10, $rb)
      }
    }
    Start-Sleep -Milliseconds 150
  }
}
function W32([int64]$addr, [uint32]$v) { [void][AWP]::Write($h, $addr, [BitConverter]::GetBytes($v)) }
function Revert() {
  W32 ($cCtl+0xE0) $orig['E0']; W32 ($cCtl+0x8D4) $orig['8D4']; W32 ($cCtl+0x8D8) $orig['8D8']; W32 ($cCtl+0x138) $orig['138']; W32 ($cCtl+0x8D0) $orig['8D0']
}

""
"=== bringing the body in front... ==="
DriveHold 4

""
"[TEST A] action flag: E0:=0x2A + flags|=1 (8s) - does the NPC animate a vault/climb?"
W32 ($cCtl+0xE0) 0x2A
if ($orig['138'] -ge 0x100000) { W32 ($cCtl+0x138) ($orig['138'] -bor 1) } else { "  (skip 138 - not pointer-ish)" }
if ($orig['8D0'] -ge 0x100000) { W32 ($cCtl+0x8D0) ($orig['8D0'] -bor 1) } else { "  (skip 8D0 - not pointer-ish)" }
DriveHold 8
Revert
"[A reverted]"

"[TEST B] hang flag: 8D8:=0x3F (8s) - does it hang/cling?"
W32 ($cCtl+0x8D8) 0x3F
DriveHold 8
Revert
"[B reverted]"

"[TEST C] blend run: 8D4:=0xBC + E0:=0x2A (8s)"
W32 ($cCtl+0x8D4) 0xBC
W32 ($cCtl+0xE0) 0x2A
DriveHold 8
Revert
"[C reverted]"

""
"DONE - which test (A/B/C) made the NPC visibly DO something?"
[void][AWP]::CloseHandle($h)
