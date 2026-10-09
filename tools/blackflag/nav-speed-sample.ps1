# nav-speed-sample.ps1 - sample a CSrvNavigation instance's speed fields to confirm movement.
# PC slot20/21 = GetSpeed/GetDesiredSpeed, returning [ecx+0x3C0]/[ecx+0x3C4] floats.
param([long]$Nav = 0, [int]$Seconds = 30, [int]$IntervalMs = 250)
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  public static IntPtr H;
  public static byte[] Read(long addr, int size) {
    var b = new byte[size]; IntPtr r;
    if (!ReadProcessMemory(H, (IntPtr)addr, b, size, out r)) return null;
    return b;
  }
  public static uint U32(long a) { var b = Read(a, 4); return b == null ? 0 : BitConverter.ToUInt32(b, 0); }
  public static float F32(long a) { var b = Read(a, 4); return b == null ? 0f : BitConverter.ToSingle(b, 0); }
}
'@
[NS]::H = [NS]::OpenProcess(0x0410, $false, $game.Id)

"nav = 0x$('{0:X8}' -f $Nav)  vt=0x$('{0:X8}' -f ([NS]::U32($Nav)))"
"sampling +0x3C0/+0x3C4 (speeds) and flags @+0x8C for $Seconds s..."
$start = Get-Date
while (((Get-Date) - $start).TotalSeconds -lt $Seconds) {
  $s1 = [NS]::F32($Nav + 0x3C0)
  $s2 = [NS]::F32($Nav + 0x3C4)
  $f  = [NS]::U32($Nav + 0x8C)
  $t  = [NS]::F32($Nav + 0x3C8)
  $u  = [NS]::F32($Nav + 0x3CC)
  "{0}  +3C0={1,8:F3}  +3C4={2,8:F3}  +3C8={3,8:F3}  +3CC={4,8:F3}  fl=0x{5:X8}" -f (Get-Date).ToString("HH:mm:ss.fff"), $s1, $s2, $t, $u, $f
  Start-Sleep -Milliseconds $IntervalMs
}
"done"
