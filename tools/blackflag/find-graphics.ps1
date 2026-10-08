# Read-only: find the link between character nodes and their "graphic" (visual) objects.
# Scans for the player graphic class (0x02595BC8) and civ graphic class (0x02595050) instances,
# then correlates: node fields pointing to a graphic, graphic fields pointing to a node.
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class GRP {
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

$h = [GRP]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [GRP]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [GRP]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [GRP]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [GRP]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [GRP]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $f = [GRP]::Read($h, $prov + 0x110, 12)
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
$eye = GetFeet
"in-world; player feet = ({0:F2},{1:F2})" -f $eye.x, $eye.y

"finding player + civ nodes..."
$hitList = [GRP]::Find($pidG, 0x01E4CE90)
$playerNode = 0; $civNodes = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [GRP]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($cnt -ge 24 -and $dist -lt 5) { $playerNode = $hit }
  if ($civNodes.Count -lt 4 -and $cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 4 -and $dist -lt 60) {
    [void]$civNodes.Add([Int64]$hit)
  }
}
"player node  = 0x$('{0:X8}' -f $playerNode)"
$civNodes | ForEach-Object { "civ node     = 0x$('{0:X8}' -f $_)" }
if ($playerNode -eq 0 -or $civNodes.Count -eq 0) { "missing nodes; abort"; exit }

"scanning for player graphic class 0x02595BC8 instances..."
$plHits = [GRP]::Find($pidG, 0x02595BC8)
"  found $($plHits.Count)"
$plSet = @{}
foreach ($x in $plHits) { $plSet[$x] = $true }

"scanning for civ graphic class 0x02595050 instances..."
$cvHits = [GRP]::Find($pidG, 0x02595050)
"  found $($cvHits.Count)"
$cvSet = @{}
foreach ($x in $cvHits) { $cvSet[$x] = $true }

"matching by node pointers (scan node bytes +0x80..+0x100 for graphic addrs)..."
function NodeMatches([int64]$node, $set, [string]$label) {
  $b = [GRP]::Read($h, $node, 0x100)
  if ($b.Length -lt 0x100) { return }
  for ($off = 0x80; $off -le 0xFC; $off += 4) {
    $v = [int64]([BitConverter]::ToUInt32($b, $off))
    if ($v -ge 0x10000 -and $set.ContainsKey($v)) {
      "$label node 0x$('{0:X8}' -f $node) +0x$('{0:X2}' -f $off) -> graphic 0x$('{0:X8}' -f $v)"
    }
  }
}
NodeMatches $playerNode $plSet "PLAYER"
NodeMatches $playerNode $cvSet "PLAYER(vs civ class)"
foreach ($n in $civNodes) { NodeMatches $n $cvSet "CIV" }
foreach ($n in $civNodes) { NodeMatches $n $plSet "CIV(vs pl class)" }

"matching by node addr inside graphic objects (scan graphic bytes +0x00..+0x100)..."
function GraphMatches($set, $nodes, [string]$label) {
  $i = 0
  foreach ($g in $set.Keys) {
    $b = [GRP]::Read($h, $g, 0x100)
    if ($b.Length -lt 0x100) { continue }
    for ($off = 0; $off -le 0xFC; $off += 4) {
      $v = [int64]([BitConverter]::ToUInt32($b, $off))
      if ($v -ge 0x10000 -and $nodes.ContainsKey($v)) {
        "$label graphic 0x$('{0:X8}' -f $g) +0x$('{0:X2}' -f $off) -> node 0x$('{0:X8}' -f $v)"
        $i++
      }
    }
  }
  if ($i -eq 0) { "$label : no node pointers found in $($set.Count) graphic objects" }
}
$nodeSet = @{}
foreach ($n in $civNodes) { $nodeSet[[int64]$n] = $true }
GraphMatches $plSet $nodeSet "PLAYER-class"
GraphMatches $cvSet $nodeSet "CIV-class"

# dump first 0x80 bytes of the first player-class graphic and first civ-class graphic
$pg = $plHits | Select-Object -First 1
if ($pg) {
  ""
  "--- player-class graphic 0x$('{0:X8}' -f $pg) first 0x80 bytes ---"
  $b = [GRP]::Read($h, $pg, 0x80)
  for ($i = 0; $i -lt 0x80; $i += 16) {
    $line = "  +0x{0:X2} | " -f $i
    for ($j = 0; $j -lt 16; $j += 4) { $line += ("{0:X8} " -f [BitConverter]::ToUInt32($b, $i+$j)) }
    $line
  }
}
$cg = $cvHits | Select-Object -First 1
if ($cg) {
  ""
  "--- civ-class graphic 0x$('{0:X8}' -f $cg) first 0x80 bytes ---"
  $b = [GRP]::Read($h, $cg, 0x80)
  for ($i = 0; $i -lt 0x80; $i += 16) {
    $line = "  +0x{0:X2} | " -f $i
    for ($j = 0; $j -lt 16; $j += 4) { $line += ("{0:X8} " -f [BitConverter]::ToUInt32($b, $i+$j)) }
    $line
  }
}
""
"done."
[void][GRP]::CloseHandle($h)
