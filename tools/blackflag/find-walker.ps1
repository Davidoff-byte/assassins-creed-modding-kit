# find-walker.ps1 - finds a crowd body that is ACTIVELY MOVING (for the movement-code watchpoint).
# Scans the body allocation region for class bodies (vtable 0x1E4CE90 + marker + children),
# samples each twice, and prints the movers with their delta.
param(
  [string]$Lo = "0x30000000",
  [string]$Hi = "0x50000000",
  [single]$NearX = 100.0,
  [single]$NearY = -73.0,
  [single]$MaxDist = 150.0,
  [int]$MaxCandidates = 400
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FW {
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, IntPtr len);
}
"@

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }
$pidG = $game.Id
"game pid = $pidG"

$h = [FW]::OpenProcess(0x0410, $false, $pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit 1 }

$lo = [Convert]::ToUInt32(($Lo -replace '^0x',''),16)
$hi = [Convert]::ToUInt32(($Hi -replace '^0x',''),16)
$buf = New-Object byte[] (1 -shl 20)
$cands = New-Object System.Collections.Generic.List[uint32]
$msz = [System.Runtime.InteropServices.Marshal]::SizeOf([type][FW+MBI])

$addr = [int64]$lo
while ($addr -lt $hi -and $cands.Count -lt $MaxCandidates) {
  $m = New-Object FW+MBI
  if ([FW]::VirtualQueryEx($h, [IntPtr]$addr, [ref]$m, [IntPtr]$msz) -eq [IntPtr]::Zero) { break }
  $ba = [int64]$m.BaseAddress; $sz = [int64]$m.RegionSize
  $ok = ($m.State -eq 0x1000) -and (($m.Protect -band 0x01) -eq 0) -and (($m.Protect -band 0x100) -eq 0) -and (($m.Protect -band 0xEE) -ne 0)
  if ($ok) {
    for ($off = 0; $off -lt $sz; $off += $buf.Length) {
      $want = [Math]::Min($buf.Length, $sz - $off)
      $got = [IntPtr]::Zero
      if ([FW]::ReadProcessMemory($h, [IntPtr]($ba + $off), $buf, [int]$want, [ref]$got) -and $got.ToInt32() -gt 0) {
        $n = $got.ToInt32()
        for ($i = 0; $i + 4 -le $n; $i += 4) {
          if ([BitConverter]::ToUInt32($buf, $i) -eq 0x01E4CE90) {
            $p = $ba + $off + $i
            $d = New-Object byte[] 0x90
            $r2 = [IntPtr]::Zero
            if ([FW]::ReadProcessMemory($h, [IntPtr]$p, $d, 0x90, [ref]$r2)) {
              if ([BitConverter]::ToUInt32($d,0x68) -ne 0x04DD5F8C) { continue }
              if ([BitConverter]::ToUInt16($d,0x66) -lt 16) { continue }
              $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44)
              $dist = [Math]::Sqrt(($x-$NearX)*($x-$NearX) + ($y-$NearY)*($y-$NearY))
              if ($dist -le $MaxDist) { $cands.Add([uint32]$p) }
            }
            if ($cands.Count -ge $MaxCandidates) { break }
          }
          if ($cands.Count -ge $MaxCandidates) { break }
        }
      }
      if ($cands.Count -ge $MaxCandidates) { break }
    }
  }
  $addr = $ba + $sz
}
"candidates near players: " + $cands.Count

function ReadPos([int64]$p) {
  $b = New-Object byte[] 12; $r = [IntPtr]::Zero
  [void][FW]::ReadProcessMemory($h, [IntPtr]($p + 0x40), $b, 12, [ref]$r)
  return @([BitConverter]::ToSingle($b,0), [BitConverter]::ToSingle($b,4), [BitConverter]::ToSingle($b,8))
}
$first = @{}
$i = 0
foreach ($c in $cands) { $first[$c] = ReadPos $c; if (++$i -ge 300) { break } }
Start-Sleep -Milliseconds 1600
"=== movers (delta over ~1.6s) ==="
$movers = @()
foreach ($c in $cands) {
  $p2 = ReadPos $c
  $p1 = $first[$c]
  if (-not $p1) { continue }
  $dx = $p2[0]-$p1[0]; $dy = $p2[1]-$p1[1]; $dz = $p2[2]-$p1[2]
  $dd = [Math]::Sqrt($dx*$dx + $dy*$dy + $dz*$dz)
  if ($dd -gt 0.4) {
    $movers += [pscustomobject]@{ addr = $c; delta = $dd; pos = ('({0:F1},{1:F1},{2:F1})' -f $p2[0],$p2[1],$p2[2]) }
  }
}
$movers | Sort-Object delta -Descending | Select-Object -First 10 | ForEach-Object { "0x{0:X8}  moved {1:F2} m  pos={2}" -f $_.addr, $_.delta, $_.pos }
"movers: " + $movers.Count
