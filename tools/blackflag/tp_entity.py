#!/usr/bin/env python3
"""Teleport a live character entity: repeatedly write its feet (matrix row 3 at
+0x40) to a target position for a short burst, so the engine/nav cannot snap
it back mid-update. Usage:
  python tp_entity.py <pid> <entity-hexaddr> <x> <y> <z> [bursts] [interval_ms]"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
addr = int(sys.argv[2], 16)
x = float(sys.argv[3])
y = float(sys.argv[4])
z = float(sys.argv[5])
bursts = int(sys.argv[6]) if len(sys.argv) > 6 else 40
interval = (int(sys.argv[7]) if len(sys.argv) > 7 else 50) / 1000.0

k32 = ctypes.windll.kernel32
PROCESS_ALL = 0x1F0FFF
h = k32.OpenProcess(PROCESS_ALL, False, pid)
if not h:
    raise SystemExit('OpenProcess failed for pid %d' % pid)


def read(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), buf, n,
                               ctypes.byref(got))
    return buf.raw[:got.value] if ok else None


def write(a, data):
    n = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), data,
                                len(data), ctypes.byref(n))
    return bool(ok), n.value


vt = struct.unpack('<I', read(addr, 4))[0]
print('entity 0x%08X vt=0x%08X (expect 0x01E4CE90) ch/cnt @+0x64/66 = %s' % (
    addr, vt, read(addr + 0x64, 4).hex()))
before = struct.unpack('<fff', read(addr + 0x40, 12))
print('feet before: (%.1f, %.1f, %.1f)' % before)

ok0 = None
for i in range(bursts):
    ok, _ = write(addr + 0x40, struct.pack('<fff', x, y, z))
    if ok0 is None:
        ok0 = ok
    time.sleep(interval)

after = struct.unpack('<fff', read(addr + 0x40, 12))
print('write ok(first)=%s  feet after: (%.1f, %.1f, %.1f)' % (ok0, *after))
