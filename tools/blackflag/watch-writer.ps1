# watch-writer.ps1 - hardware WRITE watchpoint on the player controller's +0xE0 (action phase byte).
# Catches the exact instruction that writes the action state when the player vaults/climbs.
# Attaches as a WOW64 debugger, arms DR0/DR7 on ALL game threads, logs each hit (EIP + regs + return
# address) then detaches. Watch the game and DO actions during the capture window.
param([int]$WaitSec = 240, [int]$CaptureSec = 120)

$ErrorActionPreference = 'Continue'
$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running"; exit 1 }
$pidG = $game.Id
"game pid = $pidG"

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public static class WW {
  [StructLayout(LayoutKind.Explicit, Size = 256)]
  public struct DEBUG_EVENT {
    [FieldOffset(0)] public uint dwDebugEventCode;
    [FieldOffset(4)] public uint dwProcessId;
    [FieldOffset(8)] public uint dwThreadId;
    [FieldOffset(16)] public uint ExceptionCode;
    [FieldOffset(20)] public uint ExceptionFlags;
    [FieldOffset(32)] public ulong ExceptionAddress;
  }

  [StructLayout(LayoutKind.Explicit, Size = 716)]
  public struct WOW64_CONTEXT {
    [FieldOffset(0x00)] public uint ContextFlags;
    [FieldOffset(0x04)] public uint Dr0;
    [FieldOffset(0x08)] public uint Dr1;
    [FieldOffset(0x0C)] public uint Dr2;
    [FieldOffset(0x10)] public uint Dr3;
    [FieldOffset(0x14)] public uint Dr6;
    [FieldOffset(0x18)] public uint Dr7;
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

  [StructLayout(LayoutKind.Sequential)]
  public struct THREADENTRY32W {
    public uint dwSize;
    public uint cntUsage;
    public uint th32ThreadID;
    public uint th32OwnerProcessID;
    public uint tpBasePri;
    public uint tpDeltaPri;
    public uint dwFlags;
  }

  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }

  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugActiveProcess(int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugActiveProcessStop(int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool DebugSetProcessKillOnExit(bool k);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool WaitForDebugEvent(out DEBUG_EVENT e, uint ms);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool ContinueDebugEvent(uint pid, uint tid, uint status);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenThread(int a, bool b, int tid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool Wow64GetThreadContext(IntPtr th, ref WOW64_CONTEXT c);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool Wow64SetThreadContext(IntPtr th, ref WOW64_CONTEXT c);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr CreateToolhelp32Snapshot(uint f, int pid);
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool Thread32First(IntPtr snap, ref THREADENTRY32W te);
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool Thread32Next(IntPtr snap, ref THREADENTRY32W te);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, IntPtr len);

  public static byte[] Read(IntPtr h, long a, int s) { byte[] b = new byte[s]; IntPtr r; ReadProcessMemory(h, (IntPtr)a, b, s, out r); return b; }
  public static long ReadPtr(IntPtr h, long a) { return BitConverter.ToUInt32(Read(h, a, 4), 0); }

  static bool GetPos(IntPtr h, out float x, out float y) {
    x = 0; y = 0;
    long mgr = ReadPtr(h, 0x2ABE588);
    if (mgr == 0) return false;
    long holder = ReadPtr(h, mgr + 0x4C);
    if (holder == 0) return false;
    long camobj = ReadPtr(h, holder);
    if (camobj == 0) return false;
    long block = ReadPtr(h, camobj + 0x68);
    if (block == 0) return false;
    long prov = ReadPtr(h, block + 0x174);
    if (prov == 0) return false;
    byte[] f = Read(h, prov + 0x110, 12);
    x = BitConverter.ToSingle(f, 0); y = BitConverter.ToSingle(f, 4);
    return true;
  }

  static List<long> ScanNodes(int pid) {
    var nodes = new List<long>();
    IntPtr qh = OpenProcess(0x0410, false, pid);
    if (qh == IntPtr.Zero) return nodes;
    long addr = 0x10000, max = 0x7FFF0000;
    byte[] buf = new byte[1 << 20];
    int msz = Marshal.SizeOf(typeof(MBI));
    while (addr < max) {
      MBI m;
      if (VirtualQueryEx(qh, (IntPtr)addr, out m, (IntPtr)msz) == IntPtr.Zero) break;
      long ba = (long)m.BaseAddress; long sz = (long)m.RegionSize;
      bool ok = (m.State == 0x1000) && ((m.Protect & 0x01) == 0) && ((m.Protect & 0x100) == 0) && ((m.Protect & 0xEE) != 0);
      if (ok) {
        for (long off = 0; off < sz; off += buf.Length) {
          int want = (int)Math.Min((long)buf.Length, sz - off); IntPtr got;
          if (ReadProcessMemory(qh, (IntPtr)(ba + off), buf, want, out got) && got.ToInt32() > 0) {
            int n = got.ToInt32();
            for (int i = 0; i + 4 <= n; i += 4)
              if (BitConverter.ToUInt32(buf, i) == 0x01E4CE90) nodes.Add(ba + off + i);
          }
        }
      }
      addr = ba + sz;
    }
    CloseHandle(qh);
    return nodes;
  }

  public static string Arm(int pid, uint target, out int armed) {
    StringBuilder sb = new StringBuilder();
    armed = 0;
    IntPtr snap = CreateToolhelp32Snapshot(4, pid);
    if (snap != (IntPtr)(-1)) {
      THREADENTRY32W te = new THREADENTRY32W();
      te.dwSize = (uint)Marshal.SizeOf(typeof(THREADENTRY32W));
      if (Thread32First(snap, ref te)) {
        do {
          if (te.th32OwnerProcessID != pid) continue;
          IntPtr th = OpenThread(0x001A, false, (int)te.th32ThreadID);
          if (th == IntPtr.Zero) continue;
          WOW64_CONTEXT c = new WOW64_CONTEXT();
          c.ContextFlags = 0x10013;
          if (Wow64GetThreadContext(th, ref c)) {
            c.Dr0 = target;
            c.Dr7 = 0x000D0001;
            if (Wow64SetThreadContext(th, ref c)) armed++;
          }
          CloseHandle(th);
        } while (Thread32Next(snap, ref te));
      }
      CloseHandle(snap);
    }
    sb.AppendLine("armed " + armed + " threads with watchpoint on 0x" + target.ToString("X8"));
    return sb.ToString();
  }

  public static string Run(int pid, long target, int waitMs, int capMs) {
    StringBuilder sb = new StringBuilder();
    IntPtr h = OpenProcess(0x1F0FFF, false, pid);
    if (h == IntPtr.Zero) return "OpenProcess failed: " + Marshal.GetLastWin32Error();

    // 1) wait for in-world, then find the player node + controller with fresh positions + retries
    long deadlineW = DateTime.UtcNow.Ticks + (long)waitMs * 10000L;
    long ctl = 0;
    bool done = false;
    while (!done && DateTime.UtcNow.Ticks < deadlineW) {
      float x, y;
      if (!GetPos(h, out x, out y)) { System.Threading.Thread.Sleep(1500); continue; }
      if (Math.Abs(x) + Math.Abs(y) <= 10) { sb.AppendLine("waiting for in-world (paused?)..."); System.Threading.Thread.Sleep(1500); continue; }
      var nodes = ScanNodes(pid);
      // fresh position AFTER the scan, then pick the closest player node (children >= 24)
      float fx, fy;
      if (!GetPos(h, out fx, out fy)) { System.Threading.Thread.Sleep(1500); continue; }
      long best = 0; double bestD = 12.0;
      foreach (long nd in nodes) {
        byte[] d = Read(h, nd, 0x90);
        if (d.Length < 0x90) continue;
        if (BitConverter.ToUInt32(d, 0x68) != 0x04DD5F8C) continue;
        ushort cnt = BitConverter.ToUInt16(d, 0x66);
        if (cnt < 24) continue;
        float nx = BitConverter.ToSingle(d, 0x40), ny = BitConverter.ToSingle(d, 0x44);
        double dist = Math.Sqrt((nx - fx) * (nx - fx) + (ny - fy) * (ny - fy));
        if (dist < bestD) { bestD = dist; best = nd; }
      }
      if (best != 0) {
        ctl = ReadPtr(h, best + 0xE8);
        if (ctl >= 0x10000) {
          target = ctl + 0x8E0;
          sb.AppendLine("player node=0x" + best.ToString("X8") + " ctl=0x" + ctl.ToString("X8") + " dist=" + bestD.ToString("F1"));
          done = true;
        } else {
          sb.AppendLine("ctl pointer bad (0x" + ctl.ToString("X8") + "), retrying...");
        }
      } else {
        sb.AppendLine("no player node near (" + fx.ToString("F0") + "," + fy.ToString("F0") + "), retrying...");
      }
      if (!done) System.Threading.Thread.Sleep(2000);
    }
    if (!done) { CloseHandle(h); sb.AppendLine("gave up: never found the player node"); return sb.ToString(); }
    sb.AppendLine("in-world. target=0x" + target.ToString("X8"));

    // 2) attach + arm
    if (!DebugActiveProcess(pid)) {
      sb.AppendLine("DebugActiveProcess failed: " + Marshal.GetLastWin32Error());
      CloseHandle(h);
      return sb.ToString();
    }
    DebugSetProcessKillOnExit(false);

    int hits = 0, armed = 0, stepTid = 0;
    bool stepping = false, finished = false;
    long deadline = DateTime.UtcNow.Ticks + (long)(capMs + 30000) * 10000L;
    long armUntil = DateTime.UtcNow.Ticks + 3000L * 10000L;
    bool firstArmDone = false;
    try {
      while (!finished && DateTime.UtcNow.Ticks < deadline) {
        DEBUG_EVENT ev;
        if (!WaitForDebugEvent(out ev, 100)) { if (Marshal.GetLastWin32Error() == 121) continue; else break; }
        uint cont = 0x00010002u;
        if (ev.dwDebugEventCode == 1) {
          uint exc = ev.ExceptionCode;
          if (exc == 0x80000004u || exc == 0x4000001Eu) {
            IntPtr th = OpenThread(0x001A, false, (int)ev.dwThreadId);
            WOW64_CONTEXT c = new WOW64_CONTEXT();
            c.ContextFlags = 0x10013;
            if (Wow64GetThreadContext(th, ref c)) {
              if (stepping && ev.dwThreadId == stepTid) {
                c.EFlags &= ~0x100u;
                c.Dr7 = 0x000D0001;
                Wow64SetThreadContext(th, ref c);
                stepping = false;
              } else if ((c.Dr6 & 1) != 0) {
                hits++;
                uint ret = 0;
                byte[] stk = Read(h, c.Esp, 4);
                if (stk.Length >= 4) ret = BitConverter.ToUInt32(stk, 0);
                sb.AppendFormat("HIT#{0} tid={1} eip=0x{2:X8} ret=0x{3:X8} eax=0x{4:X8} ecx=0x{5:X8} esi=0x{6:X8} ebx=0x{7:X8} edx=0x{8:X8} edi=0x{9:X8} ebp=0x{10:X8} esp=0x{11:X8}\r\n",
                  hits, ev.dwThreadId, c.Eip, ret, c.Eax, c.Ecx, c.Esi, c.Ebx, c.Edx, c.Edi, c.Ebp, c.Esp);
                c.Dr7 = 0;
                c.EFlags |= 0x100u;
                Wow64SetThreadContext(th, ref c);
                stepping = true;
                stepTid = (int)ev.dwThreadId;
                if (hits >= 8) finished = true;
              }
            }
            if (th != IntPtr.Zero) CloseHandle(th);
          } else {
            cont = 0x80010001u;
          }
        } else if (ev.dwDebugEventCode == 2 || ev.dwDebugEventCode == 3) {
          if (firstArmDone || ev.dwDebugEventCode == 3) {
            IntPtr th = OpenThread(0x001A, false, (int)ev.dwThreadId);
            if (th != IntPtr.Zero) {
              WOW64_CONTEXT c = new WOW64_CONTEXT();
              c.ContextFlags = 0x10013;
              if (Wow64GetThreadContext(th, ref c)) {
                c.Dr0 = (uint)target;
                c.Dr7 = 0x000D0001;
                if (Wow64SetThreadContext(th, ref c)) armed++;
              }
              CloseHandle(th);
            }
          }
        } else if (ev.dwDebugEventCode == 5) {
          sb.AppendLine("game exited during watch");
          break;
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont);
        if (!firstArmDone && DateTime.UtcNow.Ticks > armUntil) {
          int a;
          sb.AppendLine(Arm(pid, (uint)target, out a));
          armed += a;
          firstArmDone = true;
          sb.AppendLine(">>> ARMED - vault/climb now <<<");
        }
      }
    } finally {
      DebugActiveProcessStop(pid);
    }
    sb.AppendLine("finished: " + hits + " hit(s), " + armed + " threads armed");
    CloseHandle(h);
    return sb.ToString();
  }
}
'@

$res = [WW]::Run($pidG, 0, $WaitSec * 1000, $CaptureSec * 1000)
$res
$logDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("watch-writer-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
Set-Content -Path $log -Value $res -Encoding UTF8
"log: $log"
if (-not (Get-Process -Id $pidG -ErrorAction SilentlyContinue)) { "NOTE: game process $pidG is no longer running" }
