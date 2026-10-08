$p = Get-Process AC4BFSP -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { "game not running"; exit }
$pidG = $p.Id
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SS {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool b, int pid);
  [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll")] public static extern IntPtr VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, IntPtr len);
  [StructLayout(LayoutKind.Sequential)]
  public struct MBI { public IntPtr BaseAddress; public IntPtr AllocationBase; public uint AllocationProtect; public IntPtr RegionSize; public uint State; public uint Protect; public uint Type; }

  static bool Match(byte[] buf, int i, byte[] pat) {
    if (i + pat.Length > buf.Length) return false;
    for (int k = 0; k < pat.Length; k++) if (buf[i + k] != pat[k]) return false;
    return true;
  }
  public static List<long> FindPattern(int pid, byte[] pat) {
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
        for (long off = 0; off < sz; off += buf.Length - 256) {
          int want = (int)Math.Min((long)buf.Length, sz - off); IntPtr got;
          if (ReadProcessMemory(h, (IntPtr)(ba + off), buf, want, out got) && got.ToInt32() > 0) {
            int n = got.ToInt32();
            for (int i = 0; i + pat.Length <= n; i++) if (Match(buf, i, pat)) hits.Add(ba + off + i);
          }
        }
      }
      addr = ba + sz;
    }
    CloseHandle(h);
    return hits;
  }
  public static byte[] ReadBytes(int pid, long addr, int n) {
    IntPtr h = OpenProcess(0x0410, false, pid);
    byte[] b = new byte[n];
    if (h == IntPtr.Zero) return b;
    IntPtr r;
    ReadProcessMemory(h, (IntPtr)addr, b, n, out r);
    CloseHandle(h);
    return b;
  }
}
"@
function AsciiAt([int64]$a,[int]$n){
  $b = [SS]::ReadBytes($pidG, $a, $n)
  $s = ""
  for ($i=0; $i -lt $b.Length; $i++) {
    if ($b[$i] -eq 0) { break }
    if ($b[$i] -lt 32 -or $b[$i] -gt 126) { return "" }
    $s += [char]$b[$i]
  }
  return $s
}

"== ASCII 'Edward' =="
$pat1 = [System.Text.Encoding]::ASCII.GetBytes("Edward")
$h1 = [SS]::FindPattern($pidG, $pat1)
"hits: $($h1.Count)"
$h1 | Select-Object -First 10 | ForEach-Object { "  @0x{0:X8}  '{1}'" -f $_, (AsciiAt ($_-8) 48) }

"== UTF-16 'Edward' =="
$pat2 = [System.Text.Encoding]::Unicode.GetBytes("Edward")
$h2 = [SS]::FindPattern($pidG, $pat2)
"hits: $($h2.Count)"
$h2 | Select-Object -First 10 | ForEach-Object {
  $b = [SS]::ReadBytes($pidG, ($_-16), 80)
  $s = ""
  for ($i=0; $i -lt $b.Length-1; $i+=2) {
    $c = [BitConverter]::ToUInt16($b,$i)
    if ($c -eq 0) { break }
    if ($c -lt 32 -or $c -gt 126) { $s = ""; break }
    $s += [char]$c
  }
  "  @0x{0:X8}  '{1}'" -f $_, $s
}

"== ASCII 'PuppetText' =="
$pat3 = [System.Text.Encoding]::ASCII.GetBytes("PuppetText")
$h3 = [SS]::FindPattern($pidG, $pat3)
"hits: $($h3.Count)"
$h3 | Select-Object -First 6 | ForEach-Object { "  @0x{0:X8}  '{1}'" -f $_, (AsciiAt ($_-16) 64) }

"== UTF-16 'PuppetTextState' =="
$pat4 = [System.Text.Encoding]::Unicode.GetBytes("PuppetTextState")
$h4 = [SS]::FindPattern($pidG, $pat4)
"hits: $($h4.Count)"
$h4 | Select-Object -First 6 | ForEach-Object { "  @0x{0:X8}" -f $_ }