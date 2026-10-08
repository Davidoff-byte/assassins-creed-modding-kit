$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class WN {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI {
    public IntPtr BaseAddress;
    public IntPtr AllocationBase;
    public uint AllocationProtect;
    public IntPtr RegionSize;
    public uint State;
    public uint Protect;
    public uint Type;
  }
  public static IntPtr Open(int pid) { return OpenProcess(0x38, false, pid); }
  public static byte[] Read(IntPtr h, long addr, int size) {
    byte[] b = new byte[size];
    IntPtr r;
    ReadProcessMemory(h, (IntPtr)addr, b, size, out r);
    return b;
  }
  public static long ReadPtr(IntPtr h, long addr) { return BitConverter.ToUInt32(Read(h, addr, 4), 0); }
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
      long ba = (long)m.BaseAddress;
      long sz = (long)m.RegionSize;
      bool ok = (m.State == 0x1000) && ((m.Protect & 0x01) == 0) && ((m.Protect & 0x100) == 0) && ((m.Protect & 0xEE) != 0);
      if (ok) {
        for (long off = 0; off < sz; off += buf.Length) {
          int want = (int)Math.Min((long)buf.Length, sz - off);
          IntPtr got;
          if (ReadProcessMemory(h, (IntPtr)(ba + off), buf, want, out got) && got.ToInt32() > 0) {
            int n = got.ToInt32();
            for (int i = 0; i + 4 <= n; i += 4) {
              if (BitConverter.ToUInt32(buf, i) == value) hits.Add(ba + off + i);
            }
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

$h = [WN]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function PlayerEye {
  $mgr = [WN]::ReadPtr($h, 0x2ABE588)
  if ($mgr -eq 0) { return $null }
  $holder = [WN]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [WN]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [WN]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [WN]::Read($h, $block + 0x50, 12)
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8) }
}

# ---- collect self-node objects now (readable even while paused) ----
$hits = [WN]::Find($pidG, 0x01E4CE90)
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hits) {
  $d = [WN]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([BitConverter]::ToUInt32($d, 8) -ne ($hit + 0x110)) { continue }
  [void]$cands.Add([pscustomobject]@{
    base = [Int64]$hit
    id = [BitConverter]::ToUInt32($d, 4)
    x = [BitConverter]::ToSingle($d, 0x40)
    y = [BitConverter]::ToSingle($d, 0x44)
    z = [BitConverter]::ToSingle($d, 0x48)
    f64 = [BitConverter]::ToUInt32($d, 0x64)
    f74 = [BitConverter]::ToSingle($d, 0x74)
  })
}
"self-node candidates: $($cands.Count)"
$pe = PlayerEye
if ($pe) { "player eye now = ({0:F2}, {1:F2}, {2:F2})" -f $pe.x, $pe.y, $pe.z }
$cands | Sort-Object { [Math]::Sqrt([Math]::Pow($_.x - $pe.x, 2) + [Math]::Pow($_.y - $pe.y, 2)) } | Select-Object -First 40 | ForEach-Object {
  $dist = [Math]::Sqrt([Math]::Pow($_.x - $pe.x, 2) + [Math]::Pow($_.y - $pe.y, 2))
  "  base=0x{0:X8} id=0x{1:X8} pos=({2:F2},{3:F2},{4:F2}) d={5:F1} f64=0x{6:X8} f74={7:F2}" -f $_.base, $_.id, $_.x, $_.y, $_.z, $dist, $_.f64, $_.f74
}

# ---- wait until the simulation actually runs (player moves), max 12 min ----
""
"waiting for movement (up to 12 min)..."
$deadline = (Get-Date).AddMinutes(12)
$last = PlayerEye
$moving = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $cur = PlayerEye
  if ($cur -and $last) {
    $d = [Math]::Sqrt([Math]::Pow($cur.x - $last.x, 2) + [Math]::Pow($cur.y - $last.y, 2) + [Math]::Pow($cur.z - $last.z, 2))
    if ($d -gt 0.4) { $moving = $true; "movement detected at $(Get-Date -Format HH:mm:ss) (d=$([Math]::Round($d,2)))"; break }
  }
  $last = $cur
  if ((Get-Date).Second % 30 -eq 0) { "  ... still waiting $(Get-Date -Format HH:mm:ss)" }
}
if (-not $moving) { "no movement detected - game likely paused/still. Results above only."; exit }

# ---- sample movers ----
Start-Sleep -Milliseconds 200
$sample = New-Object System.Collections.ArrayList
foreach ($c in $cands) {
  $d = [WN]::Read($h, $c.base + 0x40, 12)
  $o = [pscustomobject]@{ base = $c.base; id = $c.id; x0 = [BitConverter]::ToSingle($d,0); y0 = [BitConverter]::ToSingle($d,4); z0 = [BitConverter]::ToSingle($d,8) }
  [void]$sample.Add($o)
}
$pe0 = PlayerEye
Start-Sleep -Seconds 4
$moved = New-Object System.Collections.ArrayList
foreach ($o in $sample) {
  $d = [WN]::Read($h, $o.base + 0x40, 12)
  $x1 = [BitConverter]::ToSingle($d,0); $y1 = [BitConverter]::ToSingle($d,4); $z1 = [BitConverter]::ToSingle($d,8)
  if ([Math]::Abs($x1) -gt 9000 -or [Math]::Abs($y1) -gt 9000 -or [Math]::Abs($z1) -gt 300) { continue }
  $dd = [Math]::Sqrt([Math]::Pow($x1-$o.x0,2) + [Math]::Pow($y1-$o.y0,2) + [Math]::Pow($z1-$o.z0,2))
  if ($dd -gt 0.3 -and $dd -lt 40) {
    [void]$moved.Add([pscustomobject]@{ base = $o.base; id = $o.id; x0=$o.x0; y0=$o.y0; z0=$o.z0; x1=$x1; y1=$y1; z1=$z1; delta=$dd; distP=[Math]::Sqrt([Math]::Pow($x1-$pe0.x,2)+[Math]::Pow($y1-$pe0.y,2)) })
  }
}
"candidates that moved in 4s: $($moved.Count) of $($sample.Count)"
$moved | Sort-Object delta -Descending | Select-Object -First 50 | ForEach-Object {
  "  MOVER base=0x{0:X8} id=0x{1:X8} d={2:F2} distToPlayer={3:F1}  ({4:F1},{5:F1},{6:F1}) -> ({7:F1},{8:F1},{9:F1})" -f $_.base, $_.id, $_.delta, $_.distP, $_.x0, $_.y0, $_.z0, $_.x1, $_.y1, $_.z1
}
[void][WN]::CloseHandle($h)
"done $(Get-Date -Format HH:mm:ss)"
