#!/usr/bin/env python3
"""Multi-teleport: hold several character entities at target positions for a
duration by burst-writing their feet (+0x40) - so the delivery is visible
before their AI resumes. Usage:
  python tp_multi.py <pid> <duration_s> addr:x:y:z [addr:x:y:z ...]"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
duration = float(sys.argv[2])
specs = []
for s in sys.argv[3:]:
    a, x, y, z = s.split(':')
    specs.append((int(a, 16), float(x), float(y), float(z)))

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x1F0FFF, False, pid)
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
    return bool(ok)

for addr, x, y, z in specs:
    blob = read(addr, 0x100)
    if not blob:
        raise SystemExit('cannot read 0x%08X' % addr)
    vt = struct.unpack_from('<I', blob, 0)[0]
    ch = struct.unpack_from('<H', blob, 0x66)[0]
    cnt = struct.unpack_from('<H', blob, 0x64)[0]
    before = struct.unpack_from('<fff', blob, 0x40)
    ok = vt == 0x01E4CE90 and ch == 29 and cnt == 32
    print('0x%08X vt=0x%08X ch=%d cnt=%d feet=(%.1f,%.1f,%.1f) -> (%.1f,%.1f,%.1f) %s' % (
        addr, vt, ch, cnt, *before, x, y, z, 'OK' if ok else '!!! SIG MISMATCH - ABORT'))
    if not ok:
        raise SystemExit('aborting: signature mismatch')

t0 = time.time()
writes = 0
while time.time() - t0 < duration:
    for addr, x, y, z in specs:
        write(addr + 0x40, struct.pack('<fff', x, y, z))
        writes += 1
    time.sleep(0.1)
print('held %d writes over %.0fs' % (writes, time.time() - t0))
for addr, x, y, z in specs:
    now = struct.unpack('<fff', read(addr + 0x40, 12))
    print('0x%08X now at (%.1f, %.1f, %.1f)' % (addr, *now))
