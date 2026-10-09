#!/usr/bin/env python3
"""READ-ONLY scan: who carries a live "state object" smart-pointer at ctl+0x8DC.

For every character entity (ch 16..33): ctl=u32(ent+0xE8); cvt=u32(ctl);
so=u32(ctl+0x8DC); if so looks like a heap pointer and so[0] readable,
record (cvt, so, so[0], so[4], so[8]).

Prints: entity table, then histogram of ctl-vtable -> state object first dword.
No writes. Usage: crowd_state_scan.py <pid>
"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


def looks_like_ptr(v):
    return 0x10000 <= v <= 0x7FFF0000


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
chars = []
while addr < 0x7FFF0000 and len(chars) < 600:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or 0
    size = mbi.RegionSize
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x08, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1024 * 1024, size - off)
            b = rd(base + off, n)
            if b:
                j = b.find(VT)
                while j >= 0:
                    a = base + off + j
                    blob = rd(a, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 33 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

hist = {}
rows = []
for a, ch, cnt in chars:
    ctl = u32(a + 0xE8)
    if not ctl:
        continue
    cvt = u32(ctl)
    so = u32(ctl + 0x8DC)
    pos = f3(a + 0x40)
    vivo = looks_like_ptr(so)
    so0 = so4 = so8 = 0
    if vivo:
        so0 = u32(so)
        so4 = u32(so + 4)
        so8 = u32(so + 8)
        hist.setdefault((cvt, so0), 0)
        hist[(cvt, so0)] += 1
    rows.append((a, ch, cnt, ctl, cvt, so, vivo, so0, so4, so8, pos))

print('chars=%d  with live state ptr=%d' % (len(rows), sum(1 for r in rows if r[6])))
print()
print('%10s %3s %4s %10s %10s %10s %5s %10s %10s %10s' % (
    'ent', 'ch', 'cnt', 'ctl', 'ctl_vt', 'so(+8DC)', 'live', 'so0', 'so4', 'so8'))
for (a, ch, cnt, ctl, cvt, so, vivo, so0, so4, so8, pos) in rows:
    print('0x%08X %3d %4d 0x%08X 0x%08X 0x%08X %5s 0x%08X 0x%08X 0x%08X' % (
        a, ch, cnt, ctl, cvt, so, 'YES' if vivo else '', so0, so4, so8))

print()
print('=== histogram: (ctl_vt, so0) -> count ===')
for (cvt, so0), n in sorted(hist.items(), key=lambda kv: -kv[1]):
    print('ctl_vt=0x%08X so0=0x%08X  x%d' % (cvt, so0, n))
