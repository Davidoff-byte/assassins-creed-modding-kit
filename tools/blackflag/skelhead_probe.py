#!/usr/bin/env python3
"""READ-ONLY: churn-check a walker's skeleton HEADER (+0x18..0x60) for ticking counters.

Usage: skelhead_probe.py <pid>
"""
import ctypes
import struct
import sys
import time

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


def u16(a):
    b = rd(a, 2)
    return struct.unpack('<H', b)[0] if b else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


class M(ctypes.Structure):
    _fields_ = [('b', ctypes.c_void_p), ('ab', ctypes.c_void_p), ('ap', ctypes.c_ulong),
                ('rs', ctypes.c_size_t), ('st', ctypes.c_ulong), ('pr', ctypes.c_ulong),
                ('ty', ctypes.c_ulong)]


m = M()
addr = 0x10000
chars = []
vt = struct.pack('<I', 0x01E4CE90)
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(ctypes.c_void_p(h), ctypes.c_void_p(addr), ctypes.byref(m), ctypes.sizeof(m)):
        break
    base = m.b or 0
    size = m.rs
    if m.st == 0x1000 and m.pr in (4, 8, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1 << 20, size - off)
            b = rd(base + off, n)
            if b:
                j = b.find(vt)
                while j >= 0:
                    a = base + off + j
                    blob = rd(a, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 40 and cnt <= 64:
                            chars.append(a)
                    j = b.find(vt, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for a in chars}
time.sleep(0.9)
sc = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 0.9
        sc.append((d, a))
sc.sort(reverse=True)
walkers = [(d, a) for d, a in sc if 0.8 <= d <= 4.0]
print('walkers: %d' % len(walkers))

for d, a in walkers[:4]:
    kb = u32(a + 0x60)
    cnt = u16(a + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if not c14:
        continue
    skel = u32(c14 + 0x134)
    b1 = rd(skel + 0x18, 0x48)
    if not b1:
        continue
    time.sleep(0.15)
    b2 = rd(skel + 0x18, 0x48)
    if not b2:
        continue
    hits = []
    for off in range(0, 0x48, 4):
        ch = sum(1 for i in range(4) if b1[off + i] != b2[off + i])
        if ch:
            v1 = struct.unpack_from('<I', b1, off)[0]
            v2 = struct.unpack_from('<I', b2, off)[0]
            hits.append((ch, skel + 0x18 + off, v1, v2))
    print('npc=0x%08X spd=%.2f skel=0x%08X header churn hits=%d %s' % (
        a, d, skel, len(hits),
        ', '.join('+%X %08X->%08X' % (h[1] - skel, h[2], h[3]) for h in hits[:8])))
    if hits:
        hits.sort(reverse=True)
        print('HOT 0x%08X' % hits[0][1])
        sys.exit(0)
print('NO HOT DWORD')
sys.exit(1)
