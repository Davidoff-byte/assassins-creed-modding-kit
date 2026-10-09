#!/usr/bin/env python3
"""READ-ONLY: inspect the walk-child (vt 0x01E41E58) motion-source chain.

For the best walker (or any of the given ch): prints
  ent/ctl/c14, ent+0xB0, c14+0x124/0x134/0x138/0x140/0x144 pointers and
  hex dumps of the pointed-to objects.

Usage: c124_probe.py <pid> [ch]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
WANT = int(sys.argv[2]) if len(sys.argv) > 2 else -1

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


def dump(tag, a, n=0x60):
    b = rd(a, n)
    if not b:
        print('   %s 0x%08X: <unreadable>' % (tag, a))
        return
    for row in range(0, n, 0x10):
        if row + 0x10 > len(b):
            break
        print('   %s+%03X: %s' % (tag, row, ' '.join('%08X' % struct.unpack_from('<I', b, row + k * 4)[0] for k in range(4))))


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
chars = []
while addr < 0x7FFF0000:
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
                        if 16 <= ch <= 40 and cnt <= 64:
                            chars.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for a in chars}
time.sleep(1.2)
scored = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 1.2
        scored.append((d, a))
scored.sort(reverse=True)


def probe(a, d):
    ch = u16(a + 0x64)
    cnt = u16(a + 0x66)
    ctl = u32(a + 0xE8)
    kids = []
    kb = u32(a + 0x60)
    for i in range(min(cnt, 48)):
        kids.append(u32(kb + i * 4))
    c14 = None
    for k in kids:
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    print('== ent=0x%08X ch=%d cnt=%d speed=%.2f ctl=0x%08X c14=%s ==' % (
        a, ch, cnt, d, ctl, ('0x%08X' % c14) if c14 else 'NONE'))
    if not c14:
        return
    print('   ent+0xB0=0x%08X  ent+0x40=(%.1f,%.1f,%.1f)' % (u32(a + 0xB0), *(f3(a + 0x40) or (0, 0, 0))))
    for off in (0x124, 0x134, 0x138, 0x13C, 0x140, 0x144, 0x134 + 4):
        pass
    p124 = u32(c14 + 0x124)
    p134 = u32(c14 + 0x134)
    print('   c14+0x124=0x%08X  c14+0x134=0x%08X  c14+0x138=0x%08X  c14+0x140=0x%08X  c14+0x144=0x%08X' % (
        p124, p134, u32(c14 + 0x138), u32(c14 + 0x140), u32(c14 + 0x144)))
    if p124:
        dump('src124', p124)
    if p134:
        dump('obj134', p134)


if WANT >= 0:
    for d, a in scored:
        if u16(a + 0x64) == WANT:
            probe(a, d)
            break
    else:
        print('no ch=%d found; best walker:' % WANT)
        if scored:
            probe(scored[0][1], scored[0][0])
else:
    for d, a in scored[:3]:
        probe(a, d)
