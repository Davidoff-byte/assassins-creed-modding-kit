$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
"pid = $pidG  (start $(Get-Date -Format HH:mm:ss))"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class SAB {
  [StructLayout(LayoutKind.Explicit, Size = 256)]
  public struct DEBUG_EVENT {
    [FieldOffset(0)] public uint dwDebugEventCode;
    [FieldOffset(4)] public uint dwProcessId;
    [FieldOffset(8)] public uint dwThreadId;
    [FieldOffset(16)] public uint ExceptionCode;
    [FieldOffset(20)] public uint ExceptionFlags;
    [FieldOffset(32)] public ulong ExceptionAddress;
    [FieldOffset(168)] public uint dwFirstChance;
  }

  [StructLayout(LayoutKind.Explicit, Size = 716)]
  public struct WOW64_CONTEXT {
    [FieldOffset(0x00)] public uint ContextFlags;
    [FieldOffset(0x9C)] public uint Edi;
    [FieldOffset(0xA0)] public uint Esi;
    [FieldOffset(0xA4)] public uint Ebx;
    [FieldOffset(0xA8)] public uint Edx;
    [FieldOffset(0xAC)] public uint Ecx;
    [FieldOffset(0xB0)] public uint Eax;
    [FieldOffset(0xB4)] public uint Ebp;
    [FieldOffset(0xB8)] public uint Eip;
    [FieldOffset(0xC0)] public uint EFlags;
    [FieldOffset(0xC4)] public uint Esp;
  }

  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct MODULEENTRY32W {
    public uint dwSize;
    public uint th32ModuleID;
    public uint th32ProcessID;
    public uint GlblcntUsage;
    public uint ProccntUsage;
    public IntPtr modBaseAddr;
    public uint modBaseSize;
    public IntPtr hModule;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szModule;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExePath;
  }

  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenProcess(int access, bool inherit, int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr written);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugActiveProcess(int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugActiveProcessStop(int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugSetProcessKillOnExit(bool killOnExit);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool WaitForDebugEvent(out DEBUG_EVENT e, uint ms);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool ContinueDebugEvent(uint pid, uint tid, uint status);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenThread(int access, bool inherit, int tid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool Wow64GetThreadContext(IntPtr hThread, ref WOW64_CONTEXT ctx);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool Wow64SetThreadContext(IntPtr hThread, ref WOW64_CONTEXT ctx);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr CreateToolhelp32Snapshot(uint flags, int pid);
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool Module32FirstW(IntPtr snap, ref MODULEENTRY32W me);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
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

  public static bool Write(IntPtr h, long addr, byte[] b) {
    IntPtr w;
    return WriteProcessMemory(h, (IntPtr)addr, b, b.Length, out w);
  }

  public static long GetModuleBase(int pid, out string name) {
    name = "";
    long b = 0x400000;
    IntPtr snap = CreateToolhelp32Snapshot(0x18, pid);
    if (snap == (IntPtr)(-1)) return b;
    MODULEENTRY32W me = new MODULEENTRY32W();
    me.dwSize = (uint)Marshal.SizeOf(typeof(MODULEENTRY32W));
    me.szModule = "";
    me.szExePath = "";
    if (Module32FirstW(snap, ref me)) { b = me.modBaseAddr.ToInt64(); name = me.szModule; }
    CloseHandle(snap);
    return b;
  }

  public static string CaptureEax(int pid, long rva, int waitMs) {
    string modName;
    long baseAddr = GetModuleBase(pid, out modName);
    long target = baseAddr + rva;
    IntPtr h = OpenProcess(0x1F0FFF, false, pid);
    if (h == IntPtr.Zero) return "FAIL:open " + Marshal.GetLastWin32Error();
    byte[] orig = new byte[1];
    IntPtr rr;
    if (!ReadProcessMemory(h, (IntPtr)target, orig, 1, out rr)) { CloseHandle(h); return "FAIL:readbyte"; }
    if (orig[0] == 0xCC) { CloseHandle(h); return "FAIL:alreadycc"; }
    if (!DebugActiveProcess(pid)) { CloseHandle(h); return "FAIL:attach " + Marshal.GetLastWin32Error(); }
    DebugSetProcessKillOnExit(false);
    IntPtr w;
    WriteProcessMemory(h, (IntPtr)target, new byte[] { 0xCC }, 1, out w);
    string result = "FAIL:timeout";
    bool captured = false;
    long deadline = DateTime.UtcNow.Ticks + (long)waitMs * 10000L;
    try {
      while (DateTime.UtcNow.Ticks < deadline && !captured) {
        DEBUG_EVENT ev;
        if (!WaitForDebugEvent(out ev, 100)) {
          int err = Marshal.GetLastWin32Error();
          if (err == 121) continue;
          result = "FAIL:wait " + err;
          break;
        }
        uint cont = 0x00010002u;
        if (ev.dwDebugEventCode == 1) {
          uint exc = ev.ExceptionCode;
          if (exc == 0x80000003u || exc == 0x4000001Fu) {
            IntPtr th = OpenThread(0x001A, false, (int)ev.dwThreadId);
            WOW64_CONTEXT ctx = new WOW64_CONTEXT();
            ctx.ContextFlags = 0x10003;
            bool ok = Wow64GetThreadContext(th, ref ctx);
            bool ours = false;
            if (ok && (ctx.Eip == (uint)(target + 1) || ctx.Eip == (uint)target)) ours = true;
            if (ev.ExceptionAddress == (ulong)target) ours = true;
            if (ours && ok) {
              captured = true;
              result = "OK:0x" + ctx.Eax.ToString("X8");
              WriteProcessMemory(h, (IntPtr)target, orig, 1, out w);
              ctx.Eip = (uint)target;
              Wow64SetThreadContext(th, ref ctx);
            }
            if (th != IntPtr.Zero) CloseHandle(th);
          } else {
            cont = 0x80010001u;
          }
        } else if (ev.dwDebugEventCode == 5) {
          result = "FAIL:exit";
          break;
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont);
      }
    } finally {
      WriteProcessMemory(h, (IntPtr)target, orig, 1, out w);
      DebugActiveProcessStop(pid);
      CloseHandle(h);
    }
    return result;
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

$h = [SAB]::Open($pidG)
if ($h -eq [IntPtr]::Zero) { "OpenProcess failed"; exit }

function GetEye {
  $mgr = [SAB]::ReadPtr($h, 0x2ABE588); if ($mgr -eq 0) { return $null }
  $holder = [SAB]::ReadPtr($h, $mgr + 0x4C); if ($holder -eq 0) { return $null }
  $camobj = [SAB]::ReadPtr($h, $holder); if ($camobj -eq 0) { return $null }
  $block = [SAB]::ReadPtr($h, $camobj + 0x68); if ($block -eq 0) { return $null }
  $b = [SAB]::Read($h, $block + 0x50, 12)
  return [pscustomobject]@{ x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8); block = $block }
}

"waiting for in-world..."
$deadline = (Get-Date).AddMinutes(10)
$sane = 0
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $e = GetEye
  if ($e -and ([Math]::Abs($e.x) + [Math]::Abs($e.y) -gt 100)) { $sane++ } else { $sane = 0 }
  if ($sane -ge 2) { break }
}
if ($sane -lt 2) { "game never got in-world; aborting"; exit }
$eye = GetEye
"in-world $(Get-Date -Format HH:mm:ss); player eye = ({0:F2}, {1:F2}, {2:F2})" -f $eye.x, $eye.y, $eye.z

# ---------- Phase A: capture Edward's root and shove him ----------
"phase A: capturing player root (INT3)..."
$cap = [SAB]::CaptureEax($pidG, 0xD2218E, 60000)
"capture: $cap"
$srcObj = 0
if ($cap.StartsWith("OK:")) { $srcObj = [Convert]::ToInt64($cap.Substring(3), 16) }
if ($srcObj -ne 0) {
  $d = [SAB]::Read($h, $srcObj, 0x90)
  $vt = [BitConverter]::ToUInt32($d, 0)
  $mk = [BitConverter]::ToUInt32($d, 0x68)
  $ox2 = [BitConverter]::ToSingle($d,0x40); $oy2 = [BitConverter]::ToSingle($d,0x44); $oz2 = [BitConverter]::ToSingle($d,0x48)
  $dx = $ox2 - $eye.x; $dy = $oy2 - $eye.y; $dz = $oz2 - ($eye.z - 1.2)
  $dmatch = [Math]::Sqrt($dx*$dx + $dy*$dy + $dz*$dz)
  "root candidate 0x{0:X8} vtable=0x{1:X8} marker=0x{2:X8} pos=({3:F2},{4:F2},{5:F2}) matchDist={6:F2}" -f $srcObj, $vt, $mk, $ox2, $oy2, $oz2, $dmatch
  if ($vt -eq 0x01E4CE90 -and $dmatch -lt 3.0) {
    "shoving Edward x2 (X+15)..."
    for ($k = 1; $k -le 2; $k++) {
      $b = [SAB]::Read($h, $srcObj + 0x40, 12)
      $x0 = [BitConverter]::ToSingle($b,0); $y0 = [BitConverter]::ToSingle($b,4); $z0 = [BitConverter]::ToSingle($b,8)
      $nx = [single]($x0 + 15.0)
      $bytes = [BitConverter]::GetBytes([single]$nx) + [BitConverter]::GetBytes([single]$y0) + [BitConverter]::GetBytes([single]$z0)
      [void][SAB]::Write($h, $srcObj + 0x40, $bytes)
      Start-Sleep -Milliseconds 1300
      $chk = [SAB]::Read($h, $srcObj + 0x40, 12)
      "   shove $k : wrote X={0:F2}, now ({1:F2}, {2:F2}, {3:F2})" -f $nx, ([BitConverter]::ToSingle($chk,0)), ([BitConverter]::ToSingle($chk,4)), ([BitConverter]::ToSingle($chk,8))
      $bytes = [BitConverter]::GetBytes([single]$x0) + [BitConverter]::GetBytes([single]$y0) + [BitConverter]::GetBytes([single]$z0)
      [void][SAB]::Write($h, $srcObj + 0x40, $bytes)
      Start-Sleep -Milliseconds 900
    }
    "Edward restored."
  } else {
    "captured object does not match player position; skipping shove."
  }
}

# ---------- Phase B: burst-pop everything nearby ----------
""
"phase B: burst pop..."
$hitList = [SAB]::Find($pidG, 0x01E4CE90)
$cands = New-Object System.Collections.ArrayList
foreach ($hit in $hitList) {
  $d = [SAB]::Read($h, $hit, 0x90)
  if ($d.Length -lt 0x90) { continue }
  if ([BitConverter]::ToUInt32($d, 0x68) -ne 0x04DD5F8C) { continue }
  $x = [BitConverter]::ToSingle($d,0x40); $y = [BitConverter]::ToSingle($d,0x44); $z = [BitConverter]::ToSingle($d,0x48)
  if ([Math]::Abs($x) -gt 9000 -or [Math]::Abs($y) -gt 9000 -or $z -lt -200 -or $z -gt 300) { continue }
  $dist = [Math]::Sqrt([Math]::Pow($x-$eye.x,2) + [Math]::Pow($y-$eye.y,2))
  if ($dist -lt 2.5 -or $dist -gt 14) { continue }
  if ($hit -eq $srcObj) { continue }
  [void]$cands.Add([pscustomobject]@{ base=[Int64]$hit; id=[BitConverter]::ToUInt32($d,4); x=$x; y=$y; z=$z; dist=$dist })
}
"burst candidates: $($cands.Count)"
$targets = $cands | Sort-Object dist | Select-Object -First 80
$entries = New-Object System.Collections.ArrayList
foreach ($t in $targets) {
  $b = [SAB]::Read($h, $t.base + 0x40, 12)
  [void]$entries.Add([pscustomobject]@{
    base = $t.base
    id = $t.id
    dist = $t.dist
    x = [BitConverter]::ToSingle($b,0); y = [BitConverter]::ToSingle($b,4); z = [BitConverter]::ToSingle($b,8)
  })
}
if ($entries.Count -gt 0) {
  for ($r = 1; $r -le 6; $r++) {
    foreach ($en in $entries) {
      $nx = [single]($en.x + 5.0); $ny = [single]$en.y; $nz = [single]($en.z + 2.5)
      $bytes = [BitConverter]::GetBytes($nx) + [BitConverter]::GetBytes($ny) + [BitConverter]::GetBytes($nz)
      [void][SAB]::Write($h, $en.base + 0x40, $bytes)
    }
    Start-Sleep -Milliseconds 500
  }
  $stuck = 0
  foreach ($en in $entries) {
    $b = [SAB]::Read($h, $en.base + 0x40, 12)
    $cx = [BitConverter]::ToSingle($b,0)
    if ([Math]::Abs($cx - ($en.x + 5.0)) -lt 0.7) { $stuck++ }
  }
  "held $($entries.Count) objects up+sideways for 3s; still displaced at check: $stuck"
  foreach ($en in $entries) {
    $bytes = [BitConverter]::GetBytes([single]$en.x) + [BitConverter]::GetBytes([single]$en.y) + [BitConverter]::GetBytes([single]$en.z)
    [void][SAB]::Write($h, $en.base + 0x40, $bytes)
  }
  "restored."
  "moved objects (nearest 25):"
  $entries | Select-Object -First 25 | ForEach-Object { "   base=0x{0:X8} id=0x{1:X8} dist={2:F1}" -f $_.base, $_.id, $_.dist }
}
[void][SAB]::CloseHandle($h)
"done $(Get-Date -Format HH:mm:ss)"
