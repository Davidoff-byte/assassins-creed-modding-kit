param([int]$ProcId, [string]$Addr, [string]$Hex)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MemW {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr written);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static string WriteRead(int pid, long addr, byte[] data) {
    IntPtr h = OpenProcess(0x0038, false, pid); // VM_OPERATION|VM_WRITE|VM_READ
    if (h == IntPtr.Zero) return "OpenProcess failed";
    IntPtr w;
    bool ok = WriteProcessMemory(h, (IntPtr)addr, data, data.Length, out w);
    byte[] rb = new byte[data.Length]; IntPtr r;
    ReadProcessMemory(h, (IntPtr)addr, rb, data.Length, out r);
    CloseHandle(h);
    return (ok ? "write OK" : "write FAILED") + "; now=" + BitConverter.ToString(rb).Replace("-", " ");
  }
}
"@
$bytes = [byte[]]($Hex -split '\s+' | ForEach-Object { [Convert]::ToByte($_,16) })
$addr = [Convert]::ToInt64($Addr, 16)
Write-Output ([MemW]::WriteRead($ProcId, $addr, $bytes))
