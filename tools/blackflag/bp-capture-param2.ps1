param([int]$WaitSec = 480, [int]$TimeoutSec = 150, [int]$Hits = 8)

$ErrorActionPreference = 'Continue'

$game = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "AC4BFSP not running - launch the game first"; exit 1 }
$pidG = $game.Id
"game pid = $pidG"

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class BPCap3 {
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

  public static long GetModuleBase(IntPtr hUnused, int pid, out string name) {
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

  public static string Vec3(byte[] b, int off) {
    return string.Format("({0:F2}, {1:F2}, {2:F2})", BitConverter.ToSingle(b, off), BitConverter.ToSingle(b, off + 4), BitConverter.ToSingle(b, off + 8));
  }

  public static string HexDump(byte[] b, int perLine) {
    StringBuilder sb = new StringBuilder();
    for (int i = 0; i + 4 <= b.Length; i += perLine) {
      sb.Append("        +0x").Append(i.ToString("X3")).Append("  ");
      for (int j = 0; j < perLine && i + j + 4 <= b.Length; j += 4) {
        sb.Append(BitConverter.ToUInt32(b, i + j).ToString("X8")).Append(' ');
      }
      sb.Append(" | ");
      for (int j = 0; j < perLine && i + j + 4 <= b.Length; j += 4) {
        sb.Append(BitConverter.ToSingle(b, i + j).ToString("F2")).Append(' ');
      }
      sb.AppendLine();
    }
    return sb.ToString();
  }

  public static long ResolvePos(IntPtr h, long baseAddr, out long srcOut, out long blockOut) {
    srcOut = 0; blockOut = 0;
    long mgr = ReadPtr(h, baseAddr + 0x26BE588);
    if (mgr == 0) return 0;
    long holder = ReadPtr(h, mgr + 0x4C);
    if (holder == 0) return 0;
    long camobj = ReadPtr(h, holder);
    if (camobj == 0) return 0;
    long block = ReadPtr(h, camobj + 0x68);
    if (block == 0) return 0;
    blockOut = block;
    srcOut = ReadPtr(h, block + 0x174);
    return block + 0x50;
  }

  public static string Run(int pid, long rva, int waitMs, int timeoutMs, int maxHits) {
    StringBuilder sb = new StringBuilder();
    IntPtr h = OpenProcess(0x1F0FFF, false, pid);
    if (h == IntPtr.Zero) return "OpenProcess failed: " + Marshal.GetLastWin32Error();
    string modName;
    long baseAddr = GetModuleBase(h, pid, out modName);
    long target = baseAddr + rva;
    sb.AppendLine("module " + modName + " base=0x" + baseAddr.ToString("X8") + " target=0x" + target.ToString("X8"));

    long deadlineW = DateTime.UtcNow.Ticks + (long)waitMs * 10000L;
    bool inWorld = false;
    int goodPolls = 0;
    while (DateTime.UtcNow.Ticks < deadlineW) {
      if (ReadPtr(h, baseAddr + 0x26BE588) == 0 && !inWorld) { /* game may still be booting */ }
      long src, blk;
      long pa = ResolvePos(h, baseAddr, out src, out blk);
      if (pa == 0) {
        sb.AppendLine("waiting for world... (camera chain not up)");
        goodPolls = 0;
      } else {
        byte[] pb = Read(h, pa, 12);
        float x = BitConverter.ToSingle(pb, 0), y = BitConverter.ToSingle(pb, 4), z = BitConverter.ToSingle(pb, 8);
        float mag = Math.Abs(x) + Math.Abs(y) + Math.Abs(z);
        if (src != 0 && mag > 50.0f) goodPolls++; else goodPolls = 0;
        sb.AppendLine(string.Format("waiting for world... pos=({0:F2}, {1:F2}, {2:F2}) mag={3:F1} src=0x{4:X8}", x, y, z, mag, src));
        if (goodPolls >= 2) { inWorld = true; break; }
      }
      System.Threading.Thread.Sleep(1500);
    }
    if (!inWorld) { CloseHandle(h); sb.AppendLine("gave up waiting for in-world (never saw a real player position)"); return sb.ToString(); }
    sb.AppendLine("in-world confirmed.");

    byte[] orig = new byte[1];
    IntPtr rr;
    bool rok = ReadProcessMemory(h, (IntPtr)target, orig, 1, out rr);
    sb.AppendLine("orig byte at target = " + (rok ? "0x" + orig[0].ToString("X2") : "READ FAILED " + Marshal.GetLastWin32Error()));
    if (!rok || orig[0] == 0xCC) { CloseHandle(h); return sb.ToString(); }

    if (!DebugActiveProcess(pid)) {
      sb.AppendLine("DebugActiveProcess failed: " + Marshal.GetLastWin32Error());
      CloseHandle(h);
      return sb.ToString();
    }
    DebugSetProcessKillOnExit(false);

    IntPtr w;
    byte[] cc = new byte[] { 0xCC };
    bool armed = WriteProcessMemory(h, (IntPtr)target, cc, 1, out w);

    int hits = 0;
    bool stepping = false;
    int stepTid = 0;
    bool finished = false;
    string stale = "";
    int evCount = 0;
    long deadline = DateTime.UtcNow.Ticks + (long)timeoutMs * 10000L;
    try {
      while (!finished && DateTime.UtcNow.Ticks < deadline) {
        DEBUG_EVENT ev;
        if (!WaitForDebugEvent(out ev, 100)) {
          int err = Marshal.GetLastWin32Error();
          if (err == 121) continue;
          sb.AppendLine("WaitForDebugEvent failed: " + err);
          break;
        }
        evCount++;
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
            if ((ev.ExceptionAddress == (ulong)target || ev.ExceptionAddress == (ulong)(target + 1))) ours = true;
            if (ours) {
              hits++;
              StringBuilder L = new StringBuilder();
              if (ok) {
                L.AppendFormat("HIT#{0} src=0x{1:X8} prov=0x{2:X8} eip=0x{3:X8} esp=0x{4:X8}\r\n", hits, ctx.Eax, ctx.Ecx, ctx.Eip, ctx.Esp);
                L.AppendFormat("   ebx=0x{0:X8} ecx=0x{1:X8} edx=0x{2:X8} esi=0x{3:X8} edi=0x{4:X8} ebp=0x{5:X8}\r\n", ctx.Ebx, ctx.Ecx, ctx.Edx, ctx.Esi, ctx.Edi, ctx.Ebp);
                if (ctx.Ecx >= 0x10000L) {
                  byte[] vt = Read(h, ctx.Ecx, 4);
                  byte[] pp = Read(h, ctx.Ecx + 0x20, 12);
                  byte[] pf = Read(h, ctx.Ecx + 0xF8, 0x28);
                  L.AppendFormat("   prov vtable=0x{0:X8}  prov+0x20={1}\r\n", BitConverter.ToUInt32(vt, 0), Vec3(pp, 0));
                  L.AppendFormat("   prov+0xF8..0x11F: {0} {1} {2} {3} {4} {5} {6} {7} {8} {9}\r\n",
                    BitConverter.ToUInt32(pf, 0).ToString("X8"), BitConverter.ToUInt32(pf, 4).ToString("X8"),
                    BitConverter.ToUInt32(pf, 8).ToString("X8"), BitConverter.ToUInt32(pf, 12).ToString("X8"),
                    BitConverter.ToUInt32(pf, 16).ToString("X8"), BitConverter.ToUInt32(pf, 20).ToString("X8"),
                    BitConverter.ToUInt32(pf, 24).ToString("X8"), BitConverter.ToUInt32(pf, 28).ToString("X8"),
                    BitConverter.ToUInt32(pf, 32).ToString("X8"), BitConverter.ToUInt32(pf, 36).ToString("X8"));
                  L.AppendFormat("   prov+0x108 feet-ish = {0}\r\n", Vec3(pf, 16));
                }
              } else {
                L.AppendFormat("HIT#{0} (context read failed)\r\n", hits);
              }
              long src2, blk2;
              long pa2 = ResolvePos(h, baseAddr, out src2, out blk2);
              if (pa2 != 0) {
                byte[] pb2 = Read(h, pa2, 12);
                L.AppendFormat("   chain: src=0x{0:X8} block=0x{1:X8} eye={2}\r\n", src2, blk2, Vec3(pb2, 0));
              }
              if (ok && ctx.Eax >= 0x10000L) {
                byte[] obj = Read(h, ctx.Eax, 0x80);
                L.Append("   src obj @0x").Append(ctx.Eax.ToString("X8")).Append(":\r\n").Append(HexDump(obj, 0x10));
                long p8 = ReadPtr(h, ctx.Eax + 8);
                L.AppendFormat("   [src+8]=0x{0:X8}{1}\r\n", p8, (p8 == 0 ? "  (pos expected at src+0x40)" : "  (node pointer)"));
              }
              stale += L.ToString();
              if (stale.Length > 20000) stale = stale.Substring(stale.Length - 18000);

              WriteProcessMemory(h, (IntPtr)target, orig, 1, out w);
              armed = false;
              if (ok) {
                ctx.Eip = (uint)target;
                ctx.EFlags = ctx.EFlags | 0x100u;
                Wow64SetThreadContext(th, ref ctx);
                stepping = true;
                stepTid = (int)ev.dwThreadId;
              }
            }
            if (th != IntPtr.Zero) CloseHandle(th);
          }
          else if (exc == 0x80000004u || exc == 0x4000001Eu) {
            if (stepping && ev.dwThreadId == stepTid) {
              IntPtr th2 = OpenThread(0x001A, false, (int)ev.dwThreadId);
              WOW64_CONTEXT ctx2 = new WOW64_CONTEXT();
              ctx2.ContextFlags = 0x10003;
              if (Wow64GetThreadContext(th2, ref ctx2)) {
                ctx2.EFlags = ctx2.EFlags & ~0x100u;
                Wow64SetThreadContext(th2, ref ctx2);
              }
              if (th2 != IntPtr.Zero) CloseHandle(th2);
              stepping = false;
              if (hits < maxHits) {
                armed = WriteProcessMemory(h, (IntPtr)target, cc, 1, out w);
              } else {
                finished = true;
              }
            }
          }
          else {
            cont = 0x80010001u;
          }
        }
        else if (ev.dwDebugEventCode == 5) {
          sb.AppendLine("process exited during capture");
          break;
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont);
      }
    } finally {
      if (armed) { WriteProcessMemory(h, (IntPtr)target, orig, 1, out w); }
      byte[] chk = Read(h, target, 1);
      if (chk[0] != orig[0]) { stale += "\r\nWARNING: byte at target is 0x" + chk[0].ToString("X2") + " (expected 0x" + orig[0].ToString("X2") + ")\r\n"; }
      DebugActiveProcessStop(pid);
    }
    sb.AppendLine("captured " + hits + " hit(s), " + evCount + " debug events processed");
    sb.AppendLine(stale);
    CloseHandle(h);
    return sb.ToString();
  }
}
'@

$res = [BPCap3]::Run($pidG, 0xD2218E, $WaitSec * 1000, $TimeoutSec * 1000, $Hits)
$res
if (-not (Get-Process -Id $pidG -ErrorAction SilentlyContinue)) { "NOTE: game process $pidG is no longer running" }

$logDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("bp-capture-param2-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
Set-Content -Path $log -Value $res -Encoding UTF8
"log: $log"
