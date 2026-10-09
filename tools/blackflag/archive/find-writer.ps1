# find-writer.ps1 - find the code that writes the player transform block each frame.
#
# Attaches as a debugger to a running AC4BFSP.exe, sets a HARDWARE WRITE BREAKPOINT on the
# player-body position (resolved live from the camera-manager chain), waits for one hit, prints the
# writing instruction pointer (EIP) and registers, then clears the breakpoint and detaches.
# Run while IN-GAME (the block is only written during gameplay).
#
#   powershell -ExecutionPolicy Bypass -File find-writer.ps1 -ProcId <pid> [ -TimeoutMs 60000 ]
#
param([Parameter(Mandatory=$true)][int]$ProcId, [int]$TimeoutMs = 60000)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WF {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool DebugActiveProcess(int pid);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool DebugActiveProcessStop(int pid);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool WaitForDebugEvent(IntPtr ev, int ms);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool ContinueDebugEvent(int pid, int tid, int code);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenThread(int access, bool inherit, int tid);
  [DllImport("kernel32.dll")] public static extern int SuspendThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern int ResumeThread(IntPtr h);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool Wow64GetThreadContext(IntPtr h, IntPtr c);
  [DllImport("kernel32.dll", SetLastError=true)] public static extern bool Wow64SetThreadContext(IntPtr h, IntPtr c);
  [DllImport("kernel32.dll")] public static extern IntPtr CreateToolhelp32Snapshot(int flags, int pid);
  [DllImport("kernel32.dll")] public static extern bool Thread32First(IntPtr s, IntPtr te);
  [DllImport("kernel32.dll")] public static extern bool Thread32Next(IntPtr s, IntPtr te);

  // x86 CONTEXT/WOW64_CONTEXT offsets (716 bytes total).
  const int O_FLAGS=0, O_DR0=4, O_DR1=8, O_DR2=12, O_DR3=16, O_DR6=24, O_DR7=28,
            O_ECX=172, O_EAX=176, O_EBX=164, O_EDX=168,
            O_EBP=180, O_EIP=184, O_ESP=196, O_CTXSIZE=716;
  const int CTXFLAGS = 0x00010013;      // i386 | CONTROL | INTEGER | DEBUG_REGISTERS
  const int THREAD_ALL = 0x1F03FF, SNAPTHREAD = 0x4, DBG_CONTINUE = 0x00010002;
  const int EVSIZE = 256;

  public static string Run(int pid, uint target, int timeoutMs) {
    IntPtr hp = OpenProcess(0x0410, false, pid);
    if (hp == IntPtr.Zero) return "OpenProcess failed";
    if (!DebugActiveProcess(pid)) return "DebugActiveProcess failed: " + Marshal.GetLastWin32Error();

    IntPtr ctx = Marshal.AllocHGlobal(O_CTXSIZE);
    IntPtr te  = Marshal.AllocHGlobal(64);
    IntPtr ev  = Marshal.AllocHGlobal(EVSIZE);
    int armed = 0;
    try {
      // --- arm DR0 (write, 1 byte) on every thread ---
      IntPtr snap = CreateToolhelp32Snapshot(SNAPTHREAD, 0);
      Marshal.WriteInt32(te, 0, 28);
      if (Thread32First(snap, te)) {
        do {
          int tid = Marshal.ReadInt32(te, 8), owner = Marshal.ReadInt32(te, 12);
          if (owner == pid) {
            IntPtr ht = OpenThread(THREAD_ALL, false, tid);
            if (ht != IntPtr.Zero) {
              SuspendThread(ht);
              Marshal.WriteInt32(ctx, O_FLAGS, CTXFLAGS);
              if (Wow64GetThreadContext(ht, ctx)) {
                // Arm DR0..DR3 on four 4-byte fields of the block (the engine may rewrite a
                // neighbouring field rather than +0x50).
                Marshal.WriteInt32(ctx, O_DR0, (int)target);
                Marshal.WriteInt32(ctx, O_DR1, (int)(target - 0x40));
                Marshal.WriteInt32(ctx, O_DR2, (int)(target - 0x20));
                Marshal.WriteInt32(ctx, O_DR3, (int)(target + 0x18));
                Marshal.WriteInt32(ctx, O_DR7, 0x1111000F);   // L0-L3=1, RW0-3=01 (write), LEN=11 (4 bytes)
                if (Wow64SetThreadContext(ht, ctx)) armed++;
              }
              ResumeThread(ht); CloseHandle(ht);
            }
          }
        } while (Thread32Next(snap, te));
      }
      CloseHandle(snap);
      if (armed == 0) { DebugActiveProcessStop(pid); return "no threads armed"; }

      // --- wait for the write hit ---
      string result = null;
      int waited = 0;
      while (waited < timeoutMs) {
        if (!WaitForDebugEvent(ev, 500)) { waited += 500; continue; }
        int code = Marshal.ReadInt32(ev, 0), epid = Marshal.ReadInt32(ev, 4), tid = Marshal.ReadInt32(ev, 8);
        int cont = DBG_CONTINUE;
        if (code == 1) { // EXCEPTION_DEBUG_EVENT
          int exc = Marshal.ReadInt32(ev, 12);
          if (exc == unchecked((int)0x80000004)) { // STATUS_SINGLE_STEP
            IntPtr ht = OpenThread(THREAD_ALL, false, tid);
            if (ht != IntPtr.Zero) {
              Marshal.WriteInt32(ctx, O_FLAGS, CTXFLAGS);
              if (Wow64GetThreadContext(ht, ctx)) {
                result = string.Format(
                  "WRITER tid={0}  EIP=0x{1:X8}  DR6=0x{2:X8}  EAX=0x{3:X8} ECX=0x{4:X8} EDX=0x{5:X8} EBX=0x{6:X8} ESP=0x{7:X8}",
                  tid, Marshal.ReadInt32(ctx,O_EIP), Marshal.ReadInt32(ctx,O_DR6),
                  Marshal.ReadInt32(ctx,O_EAX), Marshal.ReadInt32(ctx,O_ECX),
                  Marshal.ReadInt32(ctx,O_EDX), Marshal.ReadInt32(ctx,O_EBX), Marshal.ReadInt32(ctx,O_ESP));
              }
              CloseHandle(ht);
            }
            ContinueDebugEvent(epid, tid, cont);
            break;
          }
        }
        ContinueDebugEvent(epid, tid, cont);
      }

      // --- clear DR0 everywhere, detach ---
      snap = CreateToolhelp32Snapshot(SNAPTHREAD, 0);
      Marshal.WriteInt32(te, 0, 28);
      if (Thread32First(snap, te)) {
        do {
          int tid = Marshal.ReadInt32(te, 8), owner = Marshal.ReadInt32(te, 12);
          if (owner == pid) {
            IntPtr ht = OpenThread(THREAD_ALL, false, tid);
            if (ht != IntPtr.Zero) {
              SuspendThread(ht);
              Marshal.WriteInt32(ctx, O_FLAGS, CTXFLAGS);
              if (Wow64GetThreadContext(ht, ctx)) {
                Marshal.WriteInt32(ctx, O_DR0, 0); Marshal.WriteInt32(ctx, O_DR1, 0);
                Marshal.WriteInt32(ctx, O_DR2, 0); Marshal.WriteInt32(ctx, O_DR3, 0);
                Marshal.WriteInt32(ctx, O_DR7, 0);
                Wow64SetThreadContext(ht, ctx);
              }
              ResumeThread(ht); CloseHandle(ht);
            }
          }
        } while (Thread32Next(snap, te));
      }
      CloseHandle(snap);
      DebugActiveProcessStop(pid);
      return result ?? "no write detected within timeout (is the game in-world and moving?)";
    } finally {
      Marshal.FreeHGlobal(ctx); Marshal.FreeHGlobal(te); Marshal.FreeHGlobal(ev);
      CloseHandle(hp);
    }
  }
}
"@

# --- resolve base + the player-body position live ---
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class RDW {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a,bool b,int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
}
"@
$h = [RDW]::OpenProcess(0x0410, $false, $ProcId)
if ($h -eq [IntPtr]::Zero) { "OpenProcess(pid=$ProcId) failed"; exit 1 }
function ReadBytes([Int64]$a, [int]$n) { $b = New-Object byte[] $n; $r = [IntPtr]::Zero; [void][RDW]::ReadProcessMemory($h, [IntPtr]$a, $b, $n, [ref]$r); return $b }
$base = 0x400000
$mgr = [BitConverter]::ToUInt32((ReadBytes ($base + 0x26BE588) 4), 0)
if ($mgr -eq 0) { "camera manager not initialised - load a save first"; [void][RDW]::CloseHandle($h); exit 1 }
$holder = [BitConverter]::ToUInt32((ReadBytes ($mgr + 0x4c) 4), 0)
$camobj = [BitConverter]::ToUInt32((ReadBytes ($holder) 4), 0)
$block  = [BitConverter]::ToUInt32((ReadBytes ($camobj + 0x68) 4), 0)
$target = $block + 0x50
"mgr=0x{0:X} holder=0x{1:X} camobj=0x{2:X} block=0x{3:X}  -> hardware-write breakpoint on 0x{4:X}" -f $mgr,$holder,$camobj,$block,$target
[void][RDW]::CloseHandle($h)

[WF]::Run($ProcId, [uint32]$target, $TimeoutMs)
