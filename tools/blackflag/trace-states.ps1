# trace-states.ps1 - samples the player's node + controllers while the user performs actions,
# logging every field CHANGE (offset, old -> new) with a timestamp, so we can map which fields
# flip on walk/run/jump/vault/climb. Read-only. Run while in-game; do the scripted sequence.
param([int]$DurationSec = 240, [int]$IntervalMs = 300)

$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  tracing up to ${DurationSec}s @ ${IntervalMs}ms"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class TRS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long a, int s) { byte[] b = new byte[s]; IntPtr r; ReadProcessMemory(h, (IntPtr)a, b, s, out r); return b; }
  public static long Ptr(IntPtr h, long a) { return BitConverter.ToUInt32(Read(h, a, 4), 0); }
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

$h = [TRS]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [TRS]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [TRS]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [TRS]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [TRS]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [TRS]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $f = [TRS]::Read($h, $prov + 0x110, 12)
  return [pscustomobject]@{ x=[BitConverter]::ToSingle($f,0); y=[BitConverter]::ToSingle($f,4); z=[BitConverter]::ToSingle($f,8) }
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

"finding player node + controllers..."
$hitList = [TRS]::Find($pidG, 0x01E4CE90)
$playerNode = 0
foreach ($hit in $hitList) {
  $d = [TRS]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  if ($cnt -lt 24) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
  $e = GetFeet
  $dist = [Math]::Sqrt([Math]::Pow($x-$e.x,2) + [Math]::Pow($y-$e.y,2))
  if ($dist -lt 5) { $playerNode = $hit; break }
}
"player node = 0x$('{0:X8}' -f $playerNode)"
if ($playerNode -eq 0) { "player node not found; abort"; exit }

$ctrlE8 = [int64]([uint32]([TRS]::Ptr($h, $playerNode + 0xE8)))
$ctrlC8 = [int64]([uint32]([TRS]::Ptr($h, $playerNode + 0xC8)))
"controller@E8 = 0x$('{0:X8}' -f $ctrlE8)   controller@C8 = 0x$('{0:X8}' -f $ctrlC8)"

function Sample([int64]$base, [int]$size) {
  $b = [TRS]::Read($h, $base, $size)
  if ($b.Length -lt $size) { return $null }
  return ,$b
}

$regions = @()
if ($ctrlE8 -ge 0x10000) { $regions += ,@($ctrlE8, 0x940, "CTL_E8") }
if ($ctrlC8 -ge 0x10000) { $regions += ,@($ctrlC8, 0x200, "CTL_C8") }
if ($playerNode -ge 0x10000) { $regions += ,@($playerNode, 0x100, "NODE") }
if ($regions.Count -eq 0) { "no regions to trace; abort"; exit }

$prev = @{}
foreach ($r in $regions) { $prev[$r[2]] = Sample $r[0] $r[1] }

$t0 = Get-Date
$tick = 0
$lastPos = GetFeet
"TRACE START $($t0.ToString('HH:mm:ss')) - do your action sequence now (see chat)."
$endT = (Get-Date).AddSeconds($DurationSec)
while ((Get-Date) -lt $endT) {
  Start-Sleep -Milliseconds $IntervalMs
  $tick++
  $t = [Math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
  $e = GetFeet
  $spd = 0
  if ($e -and $lastPos) {
    $spd = [Math]::Round([Math]::Sqrt([Math]::Pow($e.x-$lastPos.x,2)+[Math]::Pow($e.y-$lastPos.y,2)+[Math]::Pow($e.z-$lastPos.z,2)) / ($IntervalMs/1000.0), 1)
    $lastPos = $e
  }
  foreach ($r in $regions) {
    $cur = Sample $r[0] $r[1]
    if ($null -eq $cur) { continue }
    $pv = $prev[$r[2]]
    $changes = 0
    for ($off = 0; $off -lt $r[1]; $off += 4) {
      $a = [BitConverter]::ToUInt32($cur, $off)
      $b2 = [BitConverter]::ToUInt32($pv, $off)
      if ($a -ne $b2) {
        $changes++
        if ($changes -le 24) {
          "t={0}s [{1}+0x{2:X3}] 0x{3:X8} -> 0x{4:X8}" -f $t, $r[2], $off, $b2, $a
        }
      }
    }
    if ($changes -gt 24) { "t={0}s [{1}] ... +{2} more fields changed" -f $t, $r[2], ($changes-24) }
    $prev[$r[2]] = $cur
  }
  "t={0}s -- pos=({1:F1},{2:F1},{3:F1}) speed={4} m/s" -f $t, $e.x, $e.y, $e.z, $spd
}
"TRACE END $(Get-Date -Format HH:mm:ss)"
[void][TRS]::CloseHandle($h)
