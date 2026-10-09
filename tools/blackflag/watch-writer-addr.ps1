# watch-writer-addr.ps1 (v3) - hardware WRITE watchpoint on an arbitrary address+offset
# (default +0x40, a character's position). Catches the engine's own writers.
#
# !! WARNING - this tool manipulates the hardware debug registers of a LIVE process.
# v1/v2 crashed the game at detach (leftover armed threads / trap flags raised an
# unhandled STATUS_SINGLE_STEP). v3 hardens the whole lifecycle:
#   - every DR/TF context write happens with the thread SUSPENDED and VERIFIED
#     (suspend -> get -> set -> get-verify -> resume)
#   - a grace DRAIN of queued debug events after the hit budget is reached
#   - a verified DISARM loop (until sweeps show zero armed threads)
#   - a POST-DETACH verification sweep
# Still: validate on a synthetic 32-bit target before using it on the game
# (see tools/TestWatch sandbox in bf-coop). Prefer in-process hooks when possible.
param(
  [Parameter(Mandatory=$true)][string]$TargetAddr,
  [string]$Offset = "0x40",
  [int]$WaitSec = 30,
  [int]$CaptureSec = 120,
  [int]$MaxHits = 20,
  [string]$ProcessName = "AC4BFSP"
)

$ErrorActionPreference = 'Continue'
$game = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $game) { "$ProcessName not running"; exit 1 }
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

  [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
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
  [DllImport("kernel32.dll", SetLastError = true)] public static extern int SuspendThread(IntPtr th);
  [DllImport("kernel32.dll", SetLastError = true)] public static extern int ResumeThread(IntPtr th);

  // suspend -> get -> set(DR0,DR7,TF) -> get-verify -> resume
  static bool SetCtxSuspended(IntPtr th, uint dr0, uint dr7, bool setTf) {
    SuspendThread(th);
    bool ok = false;
    WOW64_CONTEXT c = new WOW64_CONTEXT();
    c.ContextFlags = 0x10013;
    if (Wow64GetThreadContext(th, ref c)) {
      c.Dr0 = dr0; c.Dr1 = 0; c.Dr2 = 0; c.Dr3 = 0; c.Dr6 = 0; c.Dr7 = dr7;
      if (setTf) { c.EFlags |= 0x100u; } else { c.EFlags &= ~0x100u; }
      if (Wow64SetThreadContext(th, ref c)) {
        WOW64_CONTEXT v = new WOW64_CONTEXT();
        v.ContextFlags = 0x10013;
        if (Wow64GetThreadContext(th, ref v)) {
          bool drOk = (v.Dr0 == dr0) && (v.Dr7 == dr7);
          bool tfOk = ((v.EFlags & 0x100u) != 0) == setTf;
          ok = drOk && tfOk;
        }
      }
    }
    ResumeThread(th);
    return ok;
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
          if (SetCtxSuspended(th, target, 0x000D0001u, false)) armed++;
          CloseHandle(th);
        } while (Thread32Next(snap, ref te));
      }
      CloseHandle(snap);
    }
    sb.AppendLine("armed " + armed + " threads on 0x" + target.ToString("X8"));
    return sb.ToString();
  }

  // suspend -> clear DR0-3/DR6/DR7/TF -> verify; returns count still armed after attempt
  public static int DisarmSweep(int pid, out int swept) {
    int remaining = 0;
    swept = 0;
    IntPtr snap = CreateToolhelp32Snapshot(4, pid);
    if (snap != (IntPtr)(-1)) {
      THREADENTRY32W te = new THREADENTRY32W();
      te.dwSize = (uint)Marshal.SizeOf(typeof(THREADENTRY32W));
      if (Thread32First(snap, ref te)) {
        do {
          if (te.th32OwnerProcessID != pid) continue;
          IntPtr th = OpenThread(0x001A, false, (int)te.th32ThreadID);
          if (th == IntPtr.Zero) continue;
          swept++;
          SuspendThread(th);
          WOW64_CONTEXT c = new WOW64_CONTEXT();
          c.ContextFlags = 0x10013;
          if (Wow64GetThreadContext(th, ref c)) {
            bool was = (c.Dr7 != 0) || (c.Dr0 != 0) || ((c.EFlags & 0x100u) != 0);
            if (was) {
              c.Dr0 = 0; c.Dr1 = 0; c.Dr2 = 0; c.Dr3 = 0; c.Dr6 = 0; c.Dr7 = 0;
              c.EFlags &= ~0x100u;
              Wow64SetThreadContext(th, ref c);
              WOW64_CONTEXT v = new WOW64_CONTEXT();
              v.ContextFlags = 0x10013;
              if (Wow64GetThreadContext(th, ref v)) {
                if ((v.Dr7 != 0) || (v.Dr0 != 0) || ((v.EFlags & 0x100u) != 0)) remaining++;
              } else { remaining++; }
            }
          } else { remaining++; }
          ResumeThread(th);
          CloseHandle(th);
        } while (Thread32Next(snap, ref te));
      }
      CloseHandle(snap);
    }
    return remaining;
  }

  // read-only: count threads with DR0/DR7/TF still set
  public static int VerifySweep(int pid, out int checkedCount) {
    int armed = 0;
    checkedCount = 0;
    IntPtr snap = CreateToolhelp32Snapshot(4, pid);
    if (snap != (IntPtr)(-1)) {
      THREADENTRY32W te = new THREADENTRY32W();
      te.dwSize = (uint)Marshal.SizeOf(typeof(THREADENTRY32W));
      if (Thread32First(snap, ref te)) {
        do {
          if (te.th32OwnerProcessID != pid) continue;
          IntPtr th = OpenThread(0x001A, false, (int)te.th32ThreadID);
          if (th == IntPtr.Zero) continue;
          SuspendThread(th);
          WOW64_CONTEXT c = new WOW64_CONTEXT();
          c.ContextFlags = 0x10013;
          if (Wow64GetThreadContext(th, ref c)) {
            checkedCount++;
            if ((c.Dr7 != 0) || (c.Dr0 != 0) || ((c.EFlags & 0x100u) != 0)) armed++;
          }
          ResumeThread(th);
          CloseHandle(th);
        } while (Thread32Next(snap, ref te));
      }
      CloseHandle(snap);
    }
    return armed;
  }

  public static string Run(int pid, long target, int capMs, int maxHits) {
    StringBuilder sb = new StringBuilder();
    IntPtr h = OpenProcess(0x1F0FFF, false, pid);
    if (h == IntPtr.Zero) return "OpenProcess failed: " + Marshal.GetLastWin32Error();

    sb.AppendLine("watch target = 0x" + target.ToString("X8"));
    if (!DebugActiveProcess(pid)) {
      sb.AppendLine("DebugActiveProcess failed: " + Marshal.GetLastWin32Error());
      CloseHandle(h);
      return sb.ToString();
    }
    DebugSetProcessKillOnExit(false);

    int hits = 0;
    int armed = 0;
    bool firstArmDone = false;
    bool finished = false;
    bool draining = false;
    HashSet<int> pendingStep = new HashSet<int>();
    long deadline = DateTime.UtcNow.Ticks + (long)(capMs + 30000) * 10000L;
    long armUntil = DateTime.UtcNow.Ticks + 3000L * 10000L;
    long drainUntil = 0;
    try {
      while (!finished && DateTime.UtcNow.Ticks < deadline) {
        DEBUG_EVENT ev;
        if (!WaitForDebugEvent(out ev, 100)) {
          if (Marshal.GetLastWin32Error() == 121) continue; else break;
        }
        uint cont = 0x00010002u;
        if (ev.dwDebugEventCode == 1) {
          uint exc = ev.ExceptionCode;
          if (exc == 0x80000004u || exc == 0x4000001Eu) {
            int tid = (int)ev.dwThreadId;
            IntPtr th = OpenThread(0x001A, false, tid);
            if (th != IntPtr.Zero) {
              WOW64_CONTEXT c = new WOW64_CONTEXT();
              c.ContextFlags = 0x10013;
              if (Wow64GetThreadContext(th, ref c)) {
                if (pendingStep.Contains(tid)) {
                  // our single-step completed: clear TF + Dr6; re-arm (or disarm while draining)
                  c.EFlags &= ~0x100u;
                  c.Dr6 = 0;
                  if (draining || finished) { c.Dr7 = 0; }
                  else { c.Dr0 = (uint)target; c.Dr7 = 0x000D0001u; }
                  Wow64SetThreadContext(th, ref c);
                  pendingStep.Remove(tid);
                } else if ((c.Dr6 & 1) != 0) {
                  // fresh write hit on DR0
                  hits++;
                  uint ret = 0;
                  byte[] stk = new byte[4];
                  IntPtr got;
                  if (ReadProcessMemory(h, (IntPtr)c.Esp, stk, 4, out got) && got.ToInt32() == 4) {
                    ret = BitConverter.ToUInt32(stk, 0);
                  }
                  // scan the stack for plausible code addresses (exe image 0x400000-0x528000)
                  StringBuilder stkSb = new StringBuilder();
                  byte[] stkBuf = new byte[0x100];
                  if (ReadProcessMemory(h, (IntPtr)c.Esp, stkBuf, 0x100, out got) && got.ToInt32() > 0) {
                    int take = Math.Min(16, got.ToInt32() / 4);
                    stkSb.Append(" stk:");
                    for (int si = 0; si < take; si++) {
                      uint sv = BitConverter.ToUInt32(stkBuf, si * 4);
                      if (sv >= 0x00400000u && sv <= 0x00528000u) {
                        stkSb.AppendFormat("0x{0:X8},", sv);
                      }
                    }
                  }
                  sb.AppendFormat("HIT#{0} tid={1} eip=0x{2:X8} ret=0x{3:X8} eax=0x{4:X8} ecx=0x{5:X8} esi=0x{6:X8} ebx=0x{7:X8} edx=0x{8:X8} edi=0x{9:X8} ebp=0x{10:X8} esp=0x{11:X8}\r\n",
                    hits, tid, c.Eip, ret, c.Eax, c.Ecx, c.Esi, c.Ebx, c.Edx, c.Edi, c.Ebp, c.Esp);
                  sb.AppendLine(stkSb.ToString().TrimEnd(','));
                  if (draining || finished) {
                    c.Dr7 = 0; c.Dr6 = 0;
                    Wow64SetThreadContext(th, ref c);
                  } else {
                    // disable DR7, clear Dr6, step over the faulting instruction
                    c.Dr7 = 0; c.Dr6 = 0; c.EFlags |= 0x100u;
                    Wow64SetThreadContext(th, ref c);
                    pendingStep.Add(tid);
                  }
                  if (hits >= maxHits) finished = true;
                } else {
                  // orphan single-step (not ours): clear TF, clear Dr6, re-arm/disarm
                  c.EFlags &= ~0x100u;
                  c.Dr6 = 0;
                  if (draining || finished) { c.Dr7 = 0; }
                  else { c.Dr0 = (uint)target; c.Dr7 = 0x000D0001u; }
                  Wow64SetThreadContext(th, ref c);
                }
              }
              CloseHandle(th);
            }
          } else {
            cont = 0x80010001u;
          }
        } else if (ev.dwDebugEventCode == 2 || ev.dwDebugEventCode == 3) {
          if (!finished && (firstArmDone || ev.dwDebugEventCode == 3)) {
            IntPtr th = OpenThread(0x001A, false, (int)ev.dwThreadId);
            if (th != IntPtr.Zero) {
              if (SetCtxSuspended(th, (uint)target, 0x000D0001u, false)) armed++;
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
          sb.AppendLine(">>> ARMED <<<");
        }
        if (finished && !draining) {
          draining = true;
          drainUntil = DateTime.UtcNow.Ticks + 3000L * 10000L;
          sb.AppendLine("draining " + pendingStep.Count + " pending single-step thread(s)");
        }
      }

      // grace drain: consume late events for up to 3s, disarm anything that fires
      long quietSince = 0;
      while (draining && DateTime.UtcNow.Ticks < drainUntil) {
        DEBUG_EVENT ev;
        if (!WaitForDebugEvent(out ev, 100)) {
          if (Marshal.GetLastWin32Error() == 121) {
            if (quietSince == 0) quietSince = DateTime.UtcNow.Ticks;
            if (DateTime.UtcNow.Ticks - quietSince > 1200L * 10000L) break;
            continue;
          } else break;
        }
        quietSince = 0;
        uint cont2 = 0x00010002u;
        if (ev.dwDebugEventCode == 1) {
          uint exc = ev.ExceptionCode;
          if (exc == 0x80000004u || exc == 0x4000001Eu) {
            int tid = (int)ev.dwThreadId;
            IntPtr th = OpenThread(0x001A, false, tid);
            if (th != IntPtr.Zero) {
              WOW64_CONTEXT c = new WOW64_CONTEXT();
              c.ContextFlags = 0x10013;
              if (Wow64GetThreadContext(th, ref c)) {
                c.EFlags &= ~0x100u;
                c.Dr6 = 0;
                c.Dr7 = 0;
                Wow64SetThreadContext(th, ref c);
                pendingStep.Remove(tid);
              }
              CloseHandle(th);
            }
          } else {
            cont2 = 0x80010001u;
          }
        } else if (ev.dwDebugEventCode == 5) {
          sb.AppendLine("game exited during drain");
          break;
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont2);
      }
      if (pendingStep.Count > 0) sb.AppendLine("note: " + pendingStep.Count + " pending-step thread(s) at drain end");
    } finally {
      // verified disarm loop
      int leftover = -1;
      for (int pass = 1; pass <= 8; pass++) {
        int swept = 0;
        leftover = DisarmSweep(pid, out swept);
        sb.AppendLine("disarm pass " + pass + ": swept " + swept + ", still-armed-after-pass = " + leftover);
        if (leftover == 0) {
          int v2 = 0;
          int checked2 = 0;
          v2 = VerifySweep(pid, out checked2);
          sb.AppendLine("verify sweep: checked " + checked2 + ", still armed = " + v2);
          if (v2 == 0) break;
          leftover = v2;
        }
      }
      sb.AppendLine("disarm leftover = " + leftover);
      DebugActiveProcessStop(pid);
      int checked3 = 0;
      int post = VerifySweep(pid, out checked3);
      sb.AppendLine("post-detach verify: checked " + checked3 + ", still armed = " + post);
      if (post != 0) {
        int s2 = 0;
        int post2 = DisarmSweep(pid, out s2);
        sb.AppendLine("post-detach disarm: swept " + s2 + ", leftover = " + post2);
      }
    }
    sb.AppendLine("finished: " + hits + " hit(s), " + armed + " threads armed");
    CloseHandle(h);
    return sb.ToString();
  }

  [DllImport("kernel32.dll", SetLastError = true)] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
}
'@

$watchAddr = [uint32]([Convert]::ToUInt32(($TargetAddr -replace '^0x',''),16) + [Convert]::ToUInt32(($Offset -replace '^0x',''),16))
$res = [WW]::Run($pidG, $watchAddr, $CaptureSec * 1000, $MaxHits)
$res
$logDir = "C:\Users\Administrator\Documents\Default Project\bf-coop\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("watch-writer-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
Set-Content -Path $log -Value $res -Encoding UTF8
"log: $log"
if (-not (Get-Process -Id $pidG -ErrorAction SilentlyContinue)) { "NOTE: game process $pidG is no longer running" }
