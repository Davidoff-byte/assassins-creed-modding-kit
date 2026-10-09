#!/usr/bin/env python3
"""Two-pass motion detector: scans full characters (ch>=16, f7c=-0.5) twice,
reports entities present in both passes whose position moved, sorted by
displacement. Finds walking characters/groups (e.g. the keyed dock gang)."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0

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


def scan():
    mbi = MBI()
    addr = 0x10000
    hits = []
    while addr < 0x7FFF0000:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)):
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
    chars = {}
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
        chars[a] = (pos, ch, cnt, f50, key)
    return chars


print('pass1 ...', end=' ')
sys.stdout.flush()
c0 = scan()
print('%d chars; waiting %.0fs ...' % (len(c0), interval))
sys.stdout.flush()
time.sleep(interval)
c1 = scan()
print('pass2: %d chars' % len(c1))
moved = []
for a, (pos0, ch, cnt, f50, k) in c0.items():
    if a in c1:
        pos1 = c1[a][0]
        d = math.hypot(pos1[0] - pos0[0], pos1[1] - pos0[1])
        if d > 0.5:
            moved.append((d, a, ch, cnt, k, pos0, pos1))
moved.sort(reverse=True)
print('moved entities: %d' % len(moved))
for d, a, ch, cnt, k, p0, p1 in moved[:50]:
    print('disp=%5.1f 0x%08X ch=%-3d cnt=%-3d key=%08X  (%.1f,%.1f) -> (%.1f,%.1f)' % (
        d, a, ch, cnt, k, p0[0], p0[1], p1[0], p1[1]))
