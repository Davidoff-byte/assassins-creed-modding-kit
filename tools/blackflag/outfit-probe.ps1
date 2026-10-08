# Outfit-probe: writes Edward's values for 4 unexplained node fields onto a civ body, one test at a
# time (~9 s each) with full revert after each. Watch the body for ANY change (clothes/model/glitch).
# All writes are tiny + reverted; worst case if the game crashes: relaunch (saves are backed up).
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class OPR {
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

$h = [OPR]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [OPR]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [OPR]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [OPR]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [OPR]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [OPR]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $q = [OPR]::Read($h, $prov + 0x100, 16)
  $f = [OPR]::Read($h, $prov + 0x110, 12)
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
"in-world; player feet = ({0:F2},{1:F2})" -f $eye.x, $eye.y

"finding player + civ node..."
$hitList = [OPR]::Find($pidG, 0x01E4CE90)
$playerNode = 0; $civNode = 0; $civKids = 0
foreach ($hit in $hitList) {
  $d = [OPR]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($cnt -ge 24 -and $dist -lt 5) { $playerNode = $hit }
  if ($civNode -eq 0 -and $cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 4 -and $dist -lt 60) {
    $civNode = $hit
    $civKids = [int64]([uint32]([BitConverter]::ToUInt32($d, 0x60)))
  }
}
"player node = 0x$('{0:X8}' -f $playerNode)  civ node = 0x$('{0:X8}' -f $civNode)"
if ($playerNode -eq 0 -or $civNode -eq 0) { "missing nodes; abort"; exit }

# Edward's values for the four tests
$pl = [OPR]::Read($h, $playerNode, 0x100)
$pvB4 = [BitConverter]::ToUInt32($pl, 0xB4)
$pv28 = [BitConverter]::ToUInt32($pl, 0x28)
$pv30 = [BitConverter]::ToUInt32($pl, 0x30)
$pv6C = [BitConverter]::ToUInt32($pl, 0x6C)
$pvD8 = [BitConverter]::ToUInt32($pl, 0xD8)
$pvDC = [BitConverter]::ToUInt32($pl, 0xDC)
$pvE0 = [BitConverter]::ToUInt32($pl, 0xE0)
$pvEC = [BitConverter]::ToUInt32($pl, 0xEC)
"edward fields: B4=0x{0:X8} 28=0x{1:X8} 30=0x{2:X8} 6C=0x{3:X8} D8..EC=0x{4:X8} 0x{5:X8} 0x{6:X8} 0x{7:X8}" -f $pvB4,$pv28,$pv30,$pv6C,$pvD8,$pvDC,$pvE0,$pvEC

# mirrors for the two hash values (inside node+0x98 and node+0xB0 targets)
$m98 = [OPR]::Ptr($h, $playerNode + 0x98)
$mB0 = [OPR]::Ptr($h, $playerNode + 0xB0)
# civ's mirror targets (write the same values there)
$c98 = [OPR]::Ptr($h, $civNode + 0x98)
$cB0 = [OPR]::Ptr($h, $civNode + 0xB0)
"mirrors: player 0x98->0x$('{0:X8}' -f $m98) 0xB0->0x$('{0:X8}' -f $mB0) ; civ 0x98->0x$('{0:X8}' -f $c98) 0xB0->0x$('{0:X8}' -f $cB0)"

# snapshot civ originals
$orig = @{}
$orig['B4'] = [OPR]::Read($h, $civNode + 0xB4, 4)
$orig['28'] = [OPR]::Read($h, $civNode + 0x28, 4)
$orig['30'] = [OPR]::Read($h, $civNode + 0x30, 4)
$orig['6C'] = [OPR]::Read($h, $civNode + 0x6C, 4)
$orig['D8'] = [OPR]::Read($h, $civNode + 0xD8, 16)
$origM = @{}
if ($c98 -ge 0x10000) { $origM['98_18'] = [OPR]::Read($h, $c98 + 0x18, 4); $origM['98_20'] = [OPR]::Read($h, $c98 + 0x20, 4) }
if ($cB0 -ge 0x10000) { $origM['B0_58'] = [OPR]::Read($h, $cB0 + 0x58, 4); $origM['B0_60'] = [OPR]::Read($h, $cB0 + 0x60, 4) }

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
      [void][OPR]::Write($h, $civNode + 0x40, $pb)
      $dx = $eye.x - $tx; $dy = $eye.y - $ty
      $dl = [Math]::Sqrt($dx*$dx + $dy*$dy)
      if ($dl -gt 0.05) {
        $yaw = [Math]::Atan2(-$dx/$dl, $dy/$dl)
        $cc = [Math]::Cos($yaw); $ss = [Math]::Sin($yaw)
        $z0 = [BitConverter]::GetBytes([single]0)
        $rb = [BitConverter]::GetBytes([single]$cc) + [BitConverter]::GetBytes([single]$ss) + $z0 + $z0
        $rb = $rb + [BitConverter]::GetBytes([single](-$ss)) + [BitConverter]::GetBytes([single]$cc) + $z0 + $z0
        [void][OPR]::Write($h, $civNode + 0x10, $rb)
      }
    }
    Start-Sleep -Milliseconds 150
  }
}
""
"=== LIVE TESTS: watch the civ body in front of you; call out ANY change ==="
"bringing the body in front..."
DriveHold 4

""
"[TEST B] node+0xB4 := edward's model-ish id 0x{0:X8} (was 0x{1:X8}) - 9s" -f $pvB4, ([BitConverter]::ToUInt32($orig['B4'],0))
[void][OPR]::Write($h, $civNode + 0xB4, [BitConverter]::GetBytes([uint32]$pvB4))
DriveHold 9
[void][OPR]::Write($h, $civNode + 0xB4, $orig['B4'])
"[B reverted]"

"[TEST C] node+0x28/+0x30 + mirrors := edward's ids 0x{0:X8} / 0x{1:X8} - 9s" -f $pv28, $pv30
[void][OPR]::Write($h, $civNode + 0x28, [BitConverter]::GetBytes([uint32]$pv28))
[void][OPR]::Write($h, $civNode + 0x30, [BitConverter]::GetBytes([uint32]$pv30))
if ($c98 -ge 0x10000) { [void][OPR]::Write($h, $c98 + 0x18, [BitConverter]::GetBytes([uint32]$pv28)); [void][OPR]::Write($h, $c98 + 0x20, [BitConverter]::GetBytes([uint32]$pv30)) }
if ($cB0 -ge 0x10000) { [void][OPR]::Write($h, $cB0 + 0x58, [BitConverter]::GetBytes([uint32]$pv28)); [void][OPR]::Write($h, $cB0 + 0x60, [BitConverter]::GetBytes([uint32]$pv30)) }
DriveHold 9
[void][OPR]::Write($h, $civNode + 0x28, $orig['28'])
[void][OPR]::Write($h, $civNode + 0x30, $orig['30'])
if ($c98 -ge 0x10000) { [void][OPR]::Write($h, $c98 + 0x18, $origM['98_18']); [void][OPR]::Write($h, $c98 + 0x20, $origM['98_20']) }
if ($cB0 -ge 0x10000) { [void][OPR]::Write($h, $cB0 + 0x58, $origM['B0_58']); [void][OPR]::Write($h, $cB0 + 0x60, $origM['B0_60']) }
"[C reverted]"

"[TEST D] node+0x6C := edward's float 0x{0:X8} (was 0x{1:X8}) - 9s" -f $pv6C, ([BitConverter]::ToUInt32($orig['6C'],0))
[void][OPR]::Write($h, $civNode + 0x6C, [BitConverter]::GetBytes([uint32]$pv6C))
DriveHold 9
[void][OPR]::Write($h, $civNode + 0x6C, $orig['6C'])
"[D reverted]"

"[TEST A] node+0xD8..0xEC := edward's index bytes 0x{0:X8} 0x{1:X8} 0x{2:X8} 0x{3:X8} - 9s" -f $pvD8, $pvDC, $pvE0, $pvEC
$ab = [BitConverter]::GetBytes($pvD8) + [BitConverter]::GetBytes($pvDC) + [BitConverter]::GetBytes($pvE0) + [BitConverter]::GetBytes($pvEC)
[void][OPR]::Write($h, $civNode + 0xD8, $ab)
DriveHold 9
[void][OPR]::Write($h, $civNode + 0xD8, $orig['D8'])
"[A reverted]"

""
"DONE. Did the body visibly change during any test (B, C, D, A)? Report: which test + what changed."
[void][OPR]::CloseHandle($h)
