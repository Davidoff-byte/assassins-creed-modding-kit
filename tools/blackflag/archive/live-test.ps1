param([int]$MoveMeters = 20, [int]$WatchSec = 5)

$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class LT {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr w);
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

  public static bool Write(IntPtr h, long addr, byte[] b) {
    IntPtr w;
    return WriteProcessMemory(h, (IntPtr)addr, b, b.Length, out w);
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

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CAP {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$fg = [CAP]::GetForegroundWindow()
$fgPid = 0
[void][CAP]::GetWindowThreadProcessId($fg, [ref]$fgPid)
"foreground is game: $($fgPid -eq $pidG)"

$h = [LT]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

# chain (player reference)
function F3($b) { return ("({0:F2}, {1:F2}, {2:F2})" -f [BitConverter]::ToSingle($b,0), [BitConverter]::ToSingle($b,4), [BitConverter]::ToSingle($b,8)) }
$mgr = [LT]::ReadPtr($h, 0x2ABE588)
$holder = [LT]::ReadPtr($h, $mgr + 0x4C)
$camobj = [LT]::ReadPtr($h, $holder)
$block = [LT]::ReadPtr($h, $camobj + 0x68)
$chainEye = F3 ([LT]::Read($h, $block + 0x50, 12))
"chain eye before = $chainEye"

# source object sanity
$srcObj = 0x44B38810
$sig = [LT]::Read($h, $srcObj, 0x70)
$vt = [BitConverter]::ToUInt32($sig, 0)
$mk = [BitConverter]::ToUInt32($sig, 0x68)
"source 0x44B38810: vtable=0x{0:X8} marker=0x{1:X8} (valid: {2})" -f $vt, $mk, (($vt -eq 0x01E4CE90) -and ($mk -eq 0x04DD5F8C))

# --- screenshots ---
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$shots = "C:\Users\Administrator\Documents\Default Project\bf-coop\shots"
New-Item -ItemType Directory -Force -Path $shots | Out-Null
$hwnd = $p.MainWindowHandle
$r = New-Object CAP+RECT
[void][CAP]::GetWindowRect($hwnd, [ref]$r)
$w = $r.Right - $r.Left; $ht = $r.Bottom - $r.Top
"window rect: L=$($r.Left) T=$($r.Top) W=$w H=$ht"
function Snap([string]$name) {
  $path = Join-Path $shots ($name + ".png")
  try {
    if ($w -gt 100 -and $ht -gt 100) {
      $bmp = New-Object System.Drawing.Bitmap $w, $ht
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $hdc = $g.GetHdc()
      $ok = [CAP]::PrintWindow($hwnd, $hdc, 2)
      $g.ReleaseHdc($hdc); $g.Dispose()
      $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
      $bmp.Dispose()
      return $path
    } else {
      $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
      $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $g.CopyFromScreen($b.X, $b.Y, 0, 0, $bmp.Size)
      $g.Dispose()
      $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
      $bmp.Dispose()
      return $path
    }
  } catch { return "snap failed: $_" }
}

$a = Snap "live-A-before"
"shot A: $a"

# --- teleport test ---
$pos = [LT]::Read($h, $srcObj + 0x40, 12)
$x = [BitConverter]::ToSingle($pos, 0)
$y = [BitConverter]::ToSingle($pos, 4)
$z = [BitConverter]::ToSingle($pos, 8)
"player source pos = ({0:F2}, {1:F2}, {2:F2})" -f $x, $y, $z
$nx = [single]($x + $MoveMeters)
[void][LT]::Write($h, $srcObj + 0x40, [BitConverter]::GetBytes($nx))
"wrote X -> {0:F2}" -f $nx
Start-Sleep -Milliseconds 800
$pos2 = [LT]::Read($h, $srcObj + 0x40, 12)
"pos after 0.8s = " + (F3 $pos2) + "   chain eye now = " + (F3 ([LT]::Read($h, $block + 0x50, 12)))
$b = Snap "live-B-after"
"shot B: $b"
Start-Sleep -Milliseconds 400
$pos3 = [LT]::Read($h, $srcObj + 0x40, 12)
"pos after 1.2s = " + (F3 $pos3)
# restore
[void][LT]::Write($h, $srcObj + 0x40, [BitConverter]::GetBytes([single]$x))
"restored X -> {0:F2}" -f $x

# --- movement scan: find living characters ---
""
"---- scanning class instances ----"
$hits = [LT]::Find($pidG, 0x01E4CE90)
"vtable occurrences: $($hits.Count)"
$objs = New-Object System.Collections.ArrayList
foreach ($hit in $hits) {
  $d = [LT]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $o = [pscustomobject]@{
    base = [Int64]$hit
    id = [BitConverter]::ToUInt32($d, 4)
    x = [BitConverter]::ToSingle($d, 0x40)
    y = [BitConverter]::ToSingle($d, 0x44)
    z = [BitConverter]::ToSingle($d, 0x48)
    f64 = [BitConverter]::ToUInt32($d, 0x64)
  }
  [void]$objs.Add($o)
}
"instances: $($objs.Count)"
$px = $x; $py = $y
$near = $objs | Where-Object { [Math]::Abs($_.x - $px) -lt 600 -and [Math]::Abs($_.y - $py) -lt 600 }
"near player (<600m): $($near.Count)"

"---- watching for movement ($WatchSec s) ----"
Start-Sleep -Seconds $WatchSec
$moved = New-Object System.Collections.ArrayList
foreach ($o in $near) {
  $d = [LT]::Read($h, $o.base + 0x40, 12)
  if ($d.Length -lt 12) { continue }
  $n2x = [BitConverter]::ToSingle($d, 0); $n2y = [BitConverter]::ToSingle($d, 4); $n2z = [BitConverter]::ToSingle($d, 8)
  $dd = [Math]::Sqrt([Math]::Pow($n2x - $o.x, 2) + [Math]::Pow($n2y - $o.y, 2) + [Math]::Pow($n2z - $o.z, 2))
  if ($dd -gt 0.08) {
    [void]$moved.Add([pscustomobject]@{ base = $o.base; id = $o.id; from = ("({0:F2},{1:F2},{2:F2})" -f $o.x, $o.y, $o.z); to = ("({0:F2},{1:F2},{2:F2})" -f $n2x, $n2y, $n2z); delta = [Math]::Round($dd, 2); f64 = ("0x{0:X8}" -f $o.f64); isPlayer = ($o.base -eq $srcObj) })
  }
}
"movers: $($moved.Count)"
$moved | Sort-Object delta -Descending | Select-Object -First 45 | ForEach-Object {
  "  base=0x{0:X8} id=0x{1:X8} {2} -> {3} d={4} f64={5}{6}" -f $_.base, $_.id, $_.from, $_.to, $_.delta, $_.f64, $(if ($_.isPlayer) { "  <== PLAYER" } else { "" })
}
[void][LT]::CloseHandle($h)
