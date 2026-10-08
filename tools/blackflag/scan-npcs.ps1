$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class NP {
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

  public static long ReadPtr(IntPtr h, long addr) {
    byte[] b = Read(h, addr, 4);
    return BitConverter.ToUInt32(b, 0);
  }

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

$h = [NP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

# player reference
$mgr = [NP]::ReadPtr($h, 0x2ABE588)
$holder = [NP]::ReadPtr($h, $mgr + 0x4C)
$camobj = [NP]::ReadPtr($h, $holder)
$block = [NP]::ReadPtr($h, $camobj + 0x68)
$pb = [NP]::Read($h, $block + 0x50, 12)
$px = [BitConverter]::ToSingle($pb, 0); $py = [BitConverter]::ToSingle($pb, 4); $pz = [BitConverter]::ToSingle($pb, 8)
"player eye = ({0:F2}, {1:F2}, {2:F2})" -f $px, $py, $pz

$hits = [NP]::Find($pidG, 0x01E4CE90)
"vtable occurrences: $($hits.Count)"

$objs = New-Object System.Collections.ArrayList
$selfNode = 0
foreach ($hit in $hits) {
  $d = [NP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $node = [BitConverter]::ToUInt32($d, 8)
  $isSelf = ($node -eq ($hit + 0x110))
  if ($isSelf) { $selfNode++ }
  $o = [pscustomobject]@{
    base = [Int64]$hit
    id = [BitConverter]::ToUInt32($d, 4)
    node = $node
    selfNode = $isSelf
    x = [BitConverter]::ToSingle($d, 0x40)
    y = [BitConverter]::ToSingle($d, 0x44)
    z = [BitConverter]::ToSingle($d, 0x48)
    f64 = [BitConverter]::ToUInt32($d, 0x64)
    f74 = [BitConverter]::ToSingle($d, 0x74)
  }
  [void]$objs.Add($o)
}
"instances: $($objs.Count)   with self-node (+8 == base+0x110): $selfNode"

# sample of id families / flags
"id families (top):"
$objs | Group-Object { "{0:X5}" -f ($_.id -shr 8) } | Sort-Object Count -Descending | Select-Object -First 12 | ForEach-Object {
  "   family {0}xx  count={1}" -f $_.Name, $_.Count
}

# sanity filter
$good = $objs | Where-Object { $_.x -gt -9000 -and $_.x -lt 9000 -and $_.y -gt -9000 -and $_.y -lt 9000 -and $_.z -gt -300 -and $_.z -lt 300 }
"good (sane coords): $($good.Count)"

""
"---- sampling 3.5s ----"
Start-Sleep -Milliseconds 3500
$moved = New-Object System.Collections.ArrayList
foreach ($o in $good) {
  $d = [NP]::Read($h, $o.base + 0x40, 12)
  if ($d.Length -lt 12) { continue }
  $nx = [BitConverter]::ToSingle($d, 0); $ny = [BitConverter]::ToSingle($d, 4); $nz = [BitConverter]::ToSingle($d, 8)
  if (-not (($nx -gt -9000) -and ($nx -lt 9000) -and ($ny -gt -9000) -and ($ny -lt 9000) -and ($nz -gt -300) -and ($nz -lt 300))) { continue }
  $dd = [Math]::Sqrt([Math]::Pow($nx - $o.x, 2) + [Math]::Pow($ny - $o.y, 2) + [Math]::Pow($nz - $o.z, 2))
  if ($dd -gt 0.15 -and $dd -lt 30) {
    $distP = [Math]::Sqrt([Math]::Pow($nx - $px, 2) + [Math]::Pow($ny - $py, 2))
    [void]$moved.Add([pscustomobject]@{ base = $o.base; id = $o.id; selfNode = $o.selfNode; x = $nx; y = $ny; z = $nz; delta = $dd; distP = $distP; f64 = $o.f64 })
  }
}
"movers (0.15..30m): $($moved.Count)   (player cluster excluded separately)"

$playerCluster = $moved | Where-Object { $_.distP -lt 4 }
$others = $moved | Where-Object { $_.distP -ge 4 }
"  movers within 4m of player (his own body): $($playerCluster.Count)"
"  movers >=4m away (other characters/props): $($others.Count)"

""
"---- groups (>=3 objects moving together) ----"
$groups = New-Object System.Collections.ArrayList
$used = New-Object 'System.Collections.Generic.HashSet[long]'
foreach ($a in $others) {
  if ($used.Contains($a.base)) { continue }
  $members = New-Object System.Collections.ArrayList
  [void]$members.Add($a)
  [void]$used.Add($a.base)
  foreach ($b in $others) {
    if ($used.Contains($b.base)) { continue }
    if ([Math]::Sqrt([Math]::Pow($b.x - $a.x, 2) + [Math]::Pow($b.y - $a.y, 2) + [Math]::Pow($b.z - $a.z, 2)) -lt 3.0) {
      [void]$members.Add($b)
      [void]$used.Add($b.base)
    }
  }
  if ($members.Count -ge 3) { [void]$groups.Add($members) }
}
"groups: $($groups.Count)"
$gi = 0
foreach ($g in ($groups | Sort-Object { -$_.Count } | Select-Object -First 10)) {
  $gi++
  $cx = ($g | Measure-Object x -Average).Average
  $cy = ($g | Measure-Object y -Average).Average
  $cz = ($g | Measure-Object z -Average).Average
  $selfN = ($g | Where-Object { $_.selfNode }).Count
  "  group {0}: n={1} centroid=({2:F1}, {3:F1}, {4:F1}) distToPlayer={5:F1} selfNodes={6}" -f $gi, $g.Count, $cx, $cy, $cz, [Math]::Sqrt([Math]::Pow($cx - $px, 2) + [Math]::Pow($cy - $py, 2)), $selfN
  $g | Select-Object -First 6 | ForEach-Object {
    "      base=0x{0:X8} id=0x{1:X8} selfNode={2} d={3:F2} f64=0x{4:X8}" -f $_.base, $_.id, $_.selfNode, $_.delta, $_.f64
  }
}
""
"---- largest movers (>=4m away) ----"
$others | Sort-Object delta -Descending | Select-Object -First 25 | ForEach-Object {
  "  base=0x{0:X8} id=0x{1:X8} selfNode={2} d={3:F2} distToPlayer={4:F1} pos=({5:F1},{6:F1},{7:F1}) f64=0x{8:X8}" -f $_.base, $_.id, $_.selfNode, $_.delta, $_.distP, $_.x, $_.y, $_.z, $_.f64
}
[void][NP]::CloseHandle($h)
