#!/usr/bin/env python3
"""Compact live scanner: lists all full characters (ch>=16, f7c=-0.5) with key,
ch, cnt, f50 and position, sorted by distance from a center. Also prints a
(ch,cnt) histogram so outliers (e.g. the swapped Edward body) pop out."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
px = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
py = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
maxd = float(sys.argv[4]) if len(sys.argv) > 4 else 500.0

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('cannot open pid %d' % pid)


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


def read(addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(addr), buf, size,
                               ctypes.byref(got))
    return buf.raw[:got.value] if ok else None


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
hits = []
t0 = time.time()
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1024 * 1024, size - off)
            b = read(base + off, n)
            if b:
                j = b.find(VT)
                while j >= 0:
                    hits.append(base + off + j)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

chars = []
for a in hits:
    blob = read(a, 0x100)
    if not blob or len(blob) < 0xF0:
        continue
    pos = struct.unpack_from('<fff', blob, 0x40)
    if not all(-9000 < v < 9000 for v in pos) or all(v == 0 for v in pos):
        continue
    f7c = struct.unpack_from('<f', blob, 0x7C)[0]
    ch = struct.unpack_from('<H', blob, 0x66)[0]
    cnt = struct.unpack_from('<H', blob, 0x64)[0]
    if ch < 16 or abs(f7c + 0.5) > 0.05:
        continue
    d = math.hypot(pos[0] - px, pos[1] - py)
    if d > maxd:
        continue
    f50 = struct.unpack_from('<I', blob, 0x50)[0]
    reg = struct.unpack_from('<I', blob, 0xC8)[0]
    key = 0
    if reg >= 0x10000:
        rb = read(reg, 0x20)
        if rb:
            try:
                key = struct.unpack_from('<I', rb, 12)[0]
            except Exception:
                pass
    chars.append((d, a, pos, ch, cnt, f50, key))

chars.sort(key=lambda c: c[0])
print('scanned %d vt hits in %.1fs; full chars within %.0f m: %d' % (
    len(hits), time.time() - t0, maxd, len(chars)))
hist = {}
for c in chars:
    hist[(c[3], c[4])] = hist.get((c[3], c[4]), 0) + 1
print('(ch,cnt) histogram:', ' '.join('%s:%d' % (k, v) for k, v in sorted(hist.items())))
print('%6s %-10s %-4s %-4s %-10s %s' % ('dist', 'addr', 'ch', 'cnt', 'key', 'pos'))
for d, a, pos, ch, cnt, f50, key in chars:
    flag = ' <<<' if (ch, cnt) not in ((17, 20), (18, 20), (19, 20), (20, 20), (20, 23), (19, 23)) else ''
    print('%6.1f %08X   %-4d %-4d %08X   (%.1f,%.1f,%.1f)%s' % (
        d, a, ch, cnt, key, pos[0], pos[1], pos[2], flag))
