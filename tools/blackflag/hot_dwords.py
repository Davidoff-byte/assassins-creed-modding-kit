#!/usr/bin/env python3
"""READ-ONLY: find the busiest dwords in a memory range over a few seconds.

Usage: hot_dwords.py <pid> <addr> <len> [sweeps] [interval_s]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
base = int(sys.argv[2], 16)
n = int(sys.argv[3], 16) if not sys.argv[3].startswith('0x') else int(sys.argv[3], 16)
sweeps = int(sys.argv[4]) if len(sys.argv) > 4 else 12
iv = float(sys.argv[5]) if len(sys.argv) > 5 else 0.15

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, ln):
    b = ctypes.create_string_buffer(ln)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, ln,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == ln else None


counts = {}
prev = rd(base, n)
if prev is None:
    print('unreadable')
    raise SystemExit(1)
for _ in range(sweeps):
    time.sleep(iv)
    cur = rd(base, n)
    if cur is None:
        continue
    for i in range(0, min(len(cur), len(prev)) - 3, 4):
        if cur[i:i + 4] != prev[i:i + 4]:
            counts[i] = counts.get(i, 0) + 1
    prev = cur

rows = sorted(counts.items(), key=lambda kv: -kv[1])
print('base=0x%08X len=0x%X sweeps=%d' % (base, n, sweeps))
for off, c in rows[:20]:
    v = struct.unpack_from('<I', prev, off)[0] if prev and len(prev) >= off + 4 else 0
    print('+0x%04X chg=%3d last=0x%08X (%.3f)' % (off, c, v, struct.unpack('<f', struct.pack('<I', v))[0]))
if not rows:
    print('no changes')
