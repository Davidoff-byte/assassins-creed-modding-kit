# watch-ghost-behavior.ps1 - wide diff watcher on the ghost body's behavior object (node+0xE8).
# Reads the ghost body address from the newest plugin log, resolves the +0xE8 behavior object
# (BhvGenericNPC for crowd bodies), then samples 0x1000 bytes of it every IntervalMs and prints
# changed dwords with timestamps, plus periodic body-position lines for correlation.
# Read-only (ReadProcessMemory), never writes.
param([int]$Seconds = 150, [int]$IntervalMs = 250)

$dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
Add-Type @"
using System;using System.Runtime.InteropServices;
public static class GB {
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
}
"@

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }
$h = [GB]::OpenProcess(0x0410, $false, $game.Id)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit 1 }
"watcher on pid $($game.Id) for $Seconds s, interval $IntervalMs ms"

function Read-Bytes([uint32]$addr, [int]$size) {
  $buf = New-Object byte[] $size
  $r = [IntPtr]::Zero
  if ([GB]::ReadProcessMemory($h, [IntPtr]$addr, $buf, $size, [ref]$r) -and $r.ToInt32() -eq $size) { return $buf }
  return $null
}
function Read-U32([uint32]$addr) {
  $b = Read-Bytes $addr 4
  if ($null -eq $b) { return $null }
  return [BitConverter]::ToUInt32($b, 0)
}
function Read-F32([uint32]$addr) {
  $b = Read-Bytes $addr 4
  if ($null -eq $b) { return $null }
  return [BitConverter]::ToSingle($b, 0)
}
function Get-GhostBody {
  $f = Get-ChildItem $dir -Filter "AC.BlackFlag.PatchFix*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $f) { return 0 }
  $lines = Get-Content $f.FullName -Tail 400
  $hit = $null
  foreach ($l in $lines) { if ($l -match "GhostBody: body (0x[0-9A-Fa-f]+)") { $hit = $Matches[1] } }
  if ($null -eq $hit) { return 0 }
  return [Convert]::ToUInt32($hit, 16)
}

$start = Get-Date
$body = 0; $obj = 0
$prev = $null; $prevOk = $null
$lastPosPrint = [DateTime]::MinValue
$totalChanges = 0

while (((Get-Date) - $start).TotalSeconds -lt $Seconds) {
  $ts = (Get-Date).ToString("HH:mm:ss.fff")
  $nb = Get-GhostBody
  if ($nb -ne 0 -and $nb -ne $body) {
    $body = $nb; $obj = 0; $prev = $null; $prevOk = $null
    "[$ts] BODY 0x{0:X}" -f $body
  }
  if ($body -ne 0) {
    $no = Read-U32 ($body + 0xE8)
    if ($null -ne $no -and $no -ne $obj) {
      $obj = $no; $prev = $null; $prevOk = $null
      $vt = Read-U32 $obj
      "[$ts] OBJ 0x{0:X} vt=0x{1:X}" -f $obj, $vt
    }
    if ($obj -ne 0) {
      $snap = New-Object uint32[] 0x400
      $ok   = New-Object bool[] 0x400
      for ($c = 0; $c -lt 0x1000; $c += 0x100) {
        $b = Read-Bytes ([uint32]($obj + $c)) 0x100
        if ($null -ne $b) {
          $base = $c / 4
          for ($i = 0; $i -lt 0x40; $i++) {
            $snap[$base + $i] = [BitConverter]::ToUInt32($b, $i * 4)
            $ok[$base + $i] = $true
          }
        }
      }
      if ($null -ne $prev) {
        $changes = 0
        for ($i = 0; $i -lt 0x400; $i++) {
          if ($ok[$i] -and $prevOk[$i] -and $snap[$i] -ne $prev[$i]) {
            $changes++
            $totalChanges++
            if ($changes -le 50) {
              "[$ts] +{0:X3}: {1:X8} -> {2:X8}" -f ($i * 4), $prev[$i], $snap[$i]
            }
          }
        }
        if ($changes -gt 50) { "[$ts] ... ({0} changes this tick, truncated)" -f $changes }
      }
      $prev = $snap; $prevOk = $ok
      if (((Get-Date) - $lastPosPrint).TotalSeconds -ge 2) {
        $lastPosPrint = Get-Date
        $x = Read-F32 ([uint32]($body + 0x40)); $y = Read-F32 ([uint32]($body + 0x44)); $z = Read-F32 ([uint32]($body + 0x48))
        $fx = 0.0; $fy = 0.0; $fz = 0.0
        if ($null -ne $x) { $fx = $x }; if ($null -ne $y) { $fy = $y }; if ($null -ne $z) { $fz = $z }
        "[$ts] POS ({0:F1},{1:F1},{2:F1})" -f $fx, $fy, $fz
      }
    }
  }
  Start-Sleep -Milliseconds $IntervalMs
}
"done - $totalChanges total field changes captured"
