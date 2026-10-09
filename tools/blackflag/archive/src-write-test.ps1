$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class MT {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr w);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$h = [MT]::OpenProcess(0x38, $false, $p.Id)
function RMem([Int64]$a, [int]$n) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][MT]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); return $b }
function RU32([Int64]$a) { return [BitConverter]::ToUInt32((RMem $a 4), 0) }
function WMem([Int64]$a, [byte[]]$b) { $w = [IntPtr]::Zero; [void][MT]::WriteProcessMemory($h, [IntPtr]$a, $b, $b.Length, [ref]$w); return $w.ToInt32() }
function F3($b) { return ("({0:F2}, {1:F2}, {2:F2})" -f [BitConverter]::ToSingle($b,0), [BitConverter]::ToSingle($b,4), [BitConverter]::ToSingle($b,8)) }

$mgr = RU32 0x2ABE588
$holder = RU32 ($mgr + 0x4C)
$camobj = RU32 $holder
$block = RU32 ($camobj + 0x68)
$prov = RU32 ($block + 0x174)
"chain: block=0x{0:X8} prov=0x{1:X8}" -f $block, $prov
"chain eye       = " + (F3 (RMem ($block + 0x50) 12))
"prov+0x110 feet = " + (F3 (RMem ($prov + 0x110) 12))

$srcObj = 0x44B38810
""
"---- source object 0x{0:X8} live dump (dwords | floats) ----" -f $srcObj
$d = RMem $srcObj 0x140
for ($i = 0; $i -lt 0x140; $i += 16) {
  $line = "+0x{0:X3}  " -f $i
  for ($j = 0; $j -lt 16; $j += 4) { $line += "{0:X8} " -f [BitConverter]::ToUInt32($d, $i + $j) }
  $line += " | "
  for ($j = 0; $j -lt 16; $j += 4) { $line += "{0,6:F2} " -f [BitConverter]::ToSingle($d, $i + $j) }
  $line
}
""
"src+0x40  matrix t = " + (F3 (RMem ($srcObj + 0x40) 12))
"src+0x110 node    = " + (F3 (RMem ($srcObj + 0x110) 12))

""
"---- write test: X+5 at src+0x40, 3 cycles ----"
for ($c = 1; $c -le 3; $c++) {
  $b = RMem ($srcObj + 0x40) 12
  $x = [BitConverter]::ToSingle($b, 0)
  $nx = [single]($x + 5.0)
  $n = WMem ($srcObj + 0x40) ([BitConverter]::GetBytes($nx))
  ("cycle {0}: wrote X {1:F2} -> {2:F2} (bytes={3})" -f $c, $x, $nx, $n)
  foreach ($dly in 120, 400, 900) {
    Start-Sleep -Milliseconds $dly
    "   sample: src+0x40=" + (F3 (RMem ($srcObj + 0x40) 12)) + "  src+0x110=" + (F3 (RMem ($srcObj + 0x110) 12)) + "  prov.feet=" + (F3 (RMem ($prov + 0x110) 12)) + "  eye=" + (F3 (RMem ($block + 0x50) 12))
  }
  Start-Sleep -Milliseconds 300
  [void](WMem ($srcObj + 0x40) ([BitConverter]::GetBytes([single]$x)))
  ("...restored X to {0:F2}" -f $x)
  Start-Sleep -Milliseconds 700
}
[void][MT]::CloseHandle($h)
