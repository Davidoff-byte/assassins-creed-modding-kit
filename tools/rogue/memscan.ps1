param([int]$ProcId, [string]$Hex, [int]$Max = 20, [int]$Before = 0, [int]$After = 0)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
public static class Mem {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll")] public static extern int VirtualQueryEx(IntPtr h, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, int len);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct MEMORY_BASIC_INFORMATION {
    public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect;
    public IntPtr RegionSize; public uint State; public uint Protect; public uint Type;
  }
  public static byte[] Context(int pid, long addr, int len) {
    IntPtr h = OpenProcess(0x0410, false, pid);
    byte[] buf = new byte[len]; IntPtr got;
    ReadProcessMemory(h, (IntPtr)addr, buf, len, out got);
    CloseHandle(h);
    return buf;
  }
  public static List<long> Scan(int pid, byte[] pat, int max, int before, int after, List<byte[]> contexts) {
    var hits = new List<long>();
    IntPtr h = OpenProcess(0x0410, false, pid);
    long addr = 0x10000, maxAddr = 0x7FFFFFFFFFFF;
    var mbi = new MEMORY_BASIC_INFORMATION();
    int sz = Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION));
    int chunk = 32*1024*1024;
    byte[] buf = new byte[chunk + pat.Length];
    while (addr < maxAddr) {
      if (VirtualQueryEx(h, (IntPtr)addr, out mbi, sz) == 0) break;
      long regsize = (long)mbi.RegionSize;
      if (mbi.State == 0x1000 && (mbi.Protect & 0x100) == 0 && (mbi.Protect & 0x01) == 0) {
        long off = 0;
        while (off < regsize) {
          int toread = (int)Math.Min((long)chunk, regsize - off);
          IntPtr got;
          if (ReadProcessMemory(h, (IntPtr)(addr+off), buf, toread, out got) && (long)got >= pat.Length) {
            int n = (int)got;
            for (int i=0;i<=n-pat.Length;i++){ bool ok=true; for(int j=0;j<pat.Length;j++){ if(buf[i+j]!=pat[j]){ok=false;break;} } if(ok){ long a=addr+off+i; hits.Add(a);
              if (before+after>0) { byte[] c=new byte[before+after]; IntPtr g2; ReadProcessMemory(h,(IntPtr)(a-before),c,before+after,out g2); contexts.Add(c); }
              if(hits.Count>=max){ CloseHandle(h); return hits; } } }
          }
          off += toread;
        }
      }
      addr += regsize; if (regsize==0) break;
    }
    CloseHandle(h); return hits;
  }
}
"@
$pat = [byte[]]($Hex -split '\s+' | ForEach-Object { [Convert]::ToByte($_,16) })
$ctx = New-Object 'System.Collections.Generic.List[byte[]]'
$hits = [Mem]::Scan($ProcId, $pat, $Max, $Before, $After, $ctx)
Write-Output "hits=$($hits.Count)"
for ($i=0; $i -lt $hits.Count; $i++) {
  $line = "0x{0:X}" -f $hits[$i]
  if ($Before + $After -gt 0 -and $i -lt $ctx.Count) { $line += "  ctx=" + (($ctx[$i] | ForEach-Object { $_.ToString('X2') }) -join ' ') }
  Write-Output $line
}
