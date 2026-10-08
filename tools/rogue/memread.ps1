param([int]$ProcId, [string]$Addr, [int]$Len = 64)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MemR {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  public static byte[] Read(int pid, long addr, int len) {
    IntPtr h = OpenProcess(0x0410, false, pid);
    byte[] buf = new byte[len]; IntPtr got;
    ReadProcessMemory(h, (IntPtr)addr, buf, len, out got);
    CloseHandle(h); return buf;
  }
}
"@
$addr = [Convert]::ToInt64($Addr, 16)
$b = [MemR]::Read($ProcId, $addr, $Len)
Write-Output ("hex: " + (($b | ForEach-Object { $_.ToString('X2') }) -join ' '))
$floats = for ($i=0; $i + 4 -le $Len; $i += 4) { [BitConverter]::ToSingle($b, $i) }
Write-Output ("floats: " + (($floats | ForEach-Object { "{0:g6}" -f $_ }) -join ', '))
