# watch-current-body.ps1 - autopsy sampler for the current ghost body.
# Reads the body address from the newest plugin log ("CullWatch: watching body 0x..."), then samples
# its lifecycle fields every 50 ms. On change or when the memory goes unreadable / the fields break,
# it dumps everything so the release mechanism is visible (destroy-in-place vs registry-removal).
param([int]$Minutes = 30)

$dir = "D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins"
Add-Type @"
using System;using System.Runtime.InteropServices;
public static class AB {
 [StructLayout(LayoutKind.Sequential)]
 public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }
 [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
 [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
 [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, IntPtr len);
}
"@

function Get-BodyAddr {
  $f = Get-ChildItem $dir -Filter "AC.BlackFlag.PatchFix*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $f) { return 0 }
  $m = Select-String -Path $f.FullName -Pattern "CullWatch: watching body 0x" | Select-Object -Last 1
  if (-not $m) { return 0 }
  return [Convert]::ToUInt32(($m.Line -replace '.*watching body 0x',''),16)
}

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }
$h = [AB]::OpenProcess(0x0410, $false, $game.Id)
$msz = [System.Runtime.InteropServices.Marshal]::SizeOf([type][AB+MBI])
"autopsy watcher on pid $($game.Id); waiting for a ghost body..."

$body = 0
$prev = @{}
$deadCount = 0
$start = Get-Date
while (((Get-Date) - $start).TotalMinutes -lt $Minutes) {
  $newBody = Get-BodyAddr
  if ($newBody -ne $body) {
    if ($body -ne 0) { "==== SWITCH: 0x{0:X} -> 0x{1:X} at {2} ====" -f $body, $newBody, (Get-Date -Format HH:mm:ss.fff) }
    $body = $newBody
    $prev = @{}
    $deadCount = 0
  }
  if ($body -eq 0) { Start-Sleep -Milliseconds 200; continue }

  # readable?
  $mbi = New-Object AB+MBI
  $q = [AB]::VirtualQueryEx($h, [IntPtr][int64]$body, [ref]$mbi, [IntPtr]$msz)
  $readable = ($q -ne [IntPtr]::Zero) -and ($mbi.State -eq 0x1000) -and (($mbi.Protect -band 0xEE) -ne 0) -and (($mbi.Protect -band 0x100) -eq 0)

  $snap = @{}
  if ($readable) {
    $b = New-Object byte[] 0xF0
    $r = [IntPtr]::Zero
    if ([AB]::ReadProcessMemory($h, [IntPtr][int64]$body, $b, 0xF0, [ref]$r) -and $r.ToInt32() -ge 0xF0) {
      $snap = @{
        vt  = [BitConverter]::ToUInt32($b, 0)
        ch  = [BitConverter]::ToUInt16($b, 0x66)
        f68 = [BitConverter]::ToUInt32($b, 0x68)
        f7c = [BitConverter]::ToSingle($b, 0x7C)
        fC8 = [BitConverter]::ToUInt32($b, 0xC8)
        fE8 = [BitConverter]::ToUInt32($b, 0xE8)
        x   = [BitConverter]::ToSingle($b, 0x40)
        y   = [BitConverter]::ToSingle($b, 0x44)
        z   = [BitConverter]::ToSingle($b, 0x48)
      }
    } else { $readable = $false }
  }

  if (-not $readable) {
    $deadCount++
    if ($deadCount -eq 3) {
      "!!!! {0} BODY 0x{1:X} UNREADABLE (freed) after {2:F1}s; last: {3} !!!!" -f (Get-Date -Format HH:mm:ss.fff), $body, ((Get-Date) - $start).TotalSeconds, ($prev | Out-String).Trim()
    }
    Start-Sleep -Milliseconds 50
    continue
  }

  foreach ($k in $snap.Keys) {
    if ($prev.ContainsKey($k) -and $prev[$k] -ne $snap[$k]) {
      "CHANGE {0} 0x{1:X} {2}: {3} -> {4}" -f (Get-Date -Format HH:mm:ss.fff), $body, $k, $prev[$k], $snap[$k]
    }
  }
  $prev = $snap
  Start-Sleep -Milliseconds 50
}
"watcher done"
