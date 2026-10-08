# Shared-reference hunt (READ-ONLY): finds pointer fields that are IDENTICAL across several
# same-variant civ bodies but DIFFERENT on the player (Edward). Those are candidate
# model/clothes resource references on the character node graph (depth <= 1).
$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SHR {
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

$h = [SHR]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetFeet {
  $mgr = [SHR]::Ptr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [SHR]::Ptr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [SHR]::Ptr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [SHR]::Ptr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $prov = [SHR]::Ptr($h, $block + 0x174); if ($prov -eq 0) { return $null }
  $f = [SHR]::Read($h, $prov + 0x110, 12)
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
$hitList = [SHR]::Find($pidG, 0x01E4CE90)
$playerNode = 0
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [SHR]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  if ([Math]::Abs([BitConverter]::ToSingle($d, 0x7C) + 0.5) -gt 0.02) { continue }
  $cnt = [BitConverter]::ToUInt16($d, 0x66)
  $id = [BitConverter]::ToUInt32($d, 4)
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($cnt -ge 24 -and $dist -lt 5) { $playerNode = $hit }
  if ($cnt -ge 16 -and $cnt -le 22 -and $id -lt 0x00010000 -and $dist -gt 3 -and $dist -lt 80 -and $cands.Count -lt 40) {
    [void]$cands.Add([pscustomobject]@{ base=[Int64]$hit; cnt=$cnt; kids=[int64]([uint32]([BitConverter]::ToUInt32($d, 0x60))); dist=$dist })
  }
}
"player node = 0x$('{0:X8}' -f $playerNode)  civ candidates: $($cands.Count)"
if ($playerNode -eq 0 -or $cands.Count -lt 3) { "not enough nodes; abort"; exit }

# fingerprint (child class sequence) to group same-variant bodies
$groups = @{}
foreach ($c in $cands) {
  $fh = [uint64]2166136261
  if ($c.kids -ge 0x10000) {
    for ($i = 0; $i -lt $c.cnt; $i++) {
      $cc = [int64]([int64]([SHR]::Ptr($h, $c.kids + $i*4)))
      $vt = [uint64]0
      if ($cc -ge 0x10000) { $vt = [uint64]([uint32]([SHR]::Ptr($h, $cc))) }
      $fh = $fh -bxor $vt
      $fh = ($fh * 16777619) % 4294967296
    }
  }
  $key = "" + $c.cnt + ":" + $fh
  if (-not $groups.ContainsKey($key)) { $groups[$key] = New-Object System.Collections.ArrayList }
  [void]$groups[$key].Add($c)
}
$keys = @($groups.Keys | Sort-Object { -($groups[$_].Count) })
"variant groups: " + (($keys | ForEach-Object { "$_ x$($groups[$_].Count)" }) -join "  ")
$gA = @($groups[$keys[0]])
$gB = @()
if ($keys.Count -gt 1 -and $groups[$keys[1]].Count -ge 2) { $gB = @($groups[$keys[1]]) }
if ($gA.Count -gt 4) { $gA = $gA[0..3] }
if ($gB.Count -gt 4) { $gB = $gB[0..3] }
"group A: $($gA.Count) bodies  group B: $($gB.Count) bodies"

function MapBody([int64]$node) {
  $map = @{}
  $b = [SHR]::Read($h, $node, 0x100)
  if ($b.Length -lt 0x100) { return $map }
  for ($off = 0; $off -lt 0x100; $off += 4) {
    $v = [int64]([BitConverter]::ToUInt32($b, $off))
    $map["n+0x{0:X2}" -f $off] = $v
  }
  for ($off = 0; $off -lt 0x100; $off += 4) {
    $v = [int64]([BitConverter]::ToUInt32($b, $off))
    if ($v -ge 0x10000 -and $v -lt 0x7FFF0000 -and ($v -band 3) -eq 0) {
      $t = [SHR]::Read($h, $v, 0x80)
      if ($t.Length -ge 0x80) {
        for ($o2 = 0; $o2 -lt 0x80; $o2 += 4) {
          $map[("n+0x{0:X2}/+0x{1:X2}" -f $off, $o2)] = [int64]([BitConverter]::ToUInt32($t, $o2))
        }
      }
    }
  }
  return $map
}

"mapping bodies..."
$mapP = MapBody $playerNode
$mapsA = @(); foreach ($c in $gA) { $mapsA += ,(MapBody $c.base) }
$mapsB = @(); foreach ($c in $gB) { $mapsB += ,(MapBody $c.base) }
"map sizes: player $($mapP.Count) A $($mapsA.Count)x$($mapsA[0].Count)"

function TargetInfo([int64]$v) {
  if ($v -lt 0x10000) { return "" }
  $b = [SHR]::Read($h, $v, 16)
  if ($b.Length -lt 16) { return " (unreadable)" }
  $t0 = [BitConverter]::ToUInt32($b,0)
  $tag = ""
  if ($t0 -ge 0x400000 -and $t0 -lt 0x2F00000) { $tag = " [vt=0x$('{0:X8}' -f $t0)]" }
  return (" d0=0x{0:X8} d1=0x{1:X8} d2=0x{2:X8}{3}" -f $t0, [BitConverter]::ToUInt32($b,4), [BitConverter]::ToUInt32($b,8), $tag)
}

""
"=== candidates: identical across ALL group-A civs, different on player ==="
$n = 0
foreach ($path in $mapP.Keys) {
  $okAll = $true
  $vA = $null
  foreach ($m in $mapsA) {
    if (-not $m.ContainsKey($path)) { $okAll = $false; break }
    if ($null -eq $vA) { $vA = $m[$path] } elseif ($m[$path] -ne $vA) { $okAll = $false; break }
  }
  if (-not $okAll) { continue }
  $vP = $mapP[$path]
  if ($vA -eq $vP) { continue }
  $n++
  if ($n -gt 120) { continue }
  $line = "  {0,-16} civs=0x{1:X8} player=0x{2:X8}" -f $path, $vA, $vP
  "  " + $line.Trim()
  if ($vA -ge 0x10000) { "        civ ->" + (TargetInfo $vA) }
  if ($vP -ge 0x10000) { "        pl  ->" + (TargetInfo $vP) }
}
"total group-A candidate paths: $n"

if ($gB.Count -ge 2) {
  ""
  "=== cross-check: same value across group A and group B, differs from player ==="
  $n2 = 0
  foreach ($path in $mapP.Keys) {
    $vA = $null; $okA = $true
    foreach ($m in $mapsA) { if (-not $m.ContainsKey($path)) { $okA = $false; break }; if ($null -eq $vA) { $vA = $m[$path] } elseif ($m[$path] -ne $vA) { $okA = $false; break } }
    if (-not $okA) { continue }
    $vB = $null; $okB = $true
    foreach ($m in $mapsB) { if (-not $m.ContainsKey($path)) { $okB = $false; break }; if ($null -eq $vB) { $vB = $m[$path] } elseif ($m[$path] -ne $vB) { $okB = $false; break } }
    if (-not $okB) { continue }
    if ($vA -ne $vB) { continue }
    $vP = $mapP[$path]
    if ($vA -eq $vP) { continue }
    $n2++
    if ($n2 -gt 40) { continue }
    "  {0,-16} civs=0x{1:X8} player=0x{2:X8}" -f $path, $vA, $vP
  }
  "total cross-group candidate paths: $n2"
}
""
"done."
[void][SHR]::CloseHandle($h)
