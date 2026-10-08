param([int]$ProcId, [string]$Addr, [int]$Len, [string]$Out)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.IO;
public static class MemD {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static int Dump(int pid, long addr, int len, string outPath) {
    IntPtr h = OpenProcess(0x0410, false, pid);
    if (h == IntPtr.Zero) return -1;
    byte[] buf = new byte[len];
    IntPtr got;
    bool ok = ReadProcessMemory(h, (IntPtr)addr, buf, len, out got);
    CloseHandle(h);
    if (!ok) return -2;
    File.WriteAllBytes(outPath, buf);
    return (int)got;
  }
}
"@
$addrI = [Convert]::ToInt64($Addr, 16)
$n = [MemD]::Dump($ProcId, $addrI, $Len, $Out)
Write-Output "dumped $n bytes to $Out"
