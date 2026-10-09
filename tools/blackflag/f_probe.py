#!/usr/bin/env python3
"""READ-ONLY: chase scene node from walk-child and find per-frame churn blocks.

Usage: f_probe.py <pid>
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


def churn(tag, a, n=0x1800, dt=0.15):
    b1 = rd(a, n)
    if not b1:
        print('  %s 0x%08X: unreadable' % (tag, a))
        return
    time.sleep(dt)
    b2 = rd(a, n)
    if not b2:
        return
    diff = [i for i in range(0, len(b1)) if b1[i] != b2[i]]
    if not diff:
        print('  %s 0x%08X: no churn in %d bytes' % (tag, a, n))
        return
    rows = {}
    for i in diff:
        rows.setdefault(i // 16, 0)
        rows[i // 16] += 1
    top = sorted(rows.items(), key=lambda kv: -kv[1])[:8]
    print('  %s 0x%08X: %d bytes changed; top rows: %s' % (
        tag, a, len(diff), ', '.join('+%X(%d)' % (r * 16, c) for r, c in top)))


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
time.sleep(1.0)
scored = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
        scored.append((d, a))
scored.sort(reverse=True)
d, a = scored[0]
ctl = u32(a + 0xE8)
kb = u32(a + 0x60)
cnt = u16(a + 0x66)
c14 = None
for i in range(min(cnt, 48)):
    k = u32(kb + i * 4)
    if u32(k) == 0x01E41E58:
        c14 = k
print('walker ent=0x%08X moved=%.2fm c14=0x%08X' % (a, d, c14))
if c14:
    for off in (0x134, 0x138, 0x140, 0x144, 0x128, 0x12C, 0x130):
        print('  c14+0x%X = 0x%08X' % (off, u32(c14 + off)))
    node = u32(c14 + 0x138) or u32(c14 + 0x134)
    print('== node 0x%08X dump ==' % node)
    b = rd(node, 0x100)
    if b:
        for row in range(0, 0x100, 0x10):
            print('   +%03X: %s' % (row, ' '.join('%08X' % struct.unpack_from('<I', b, row + k * 4)[0] for k in range(4))))
    cands = []
    for off in range(0x40, 0x100, 4):
        v = u32(node + off)
        if 0x10000 < v < 0x7FFF0000:
            cands.append((off, v))
    print('== pointer candidates under node: %s ==' % ', '.join('+%X->0x%08X' % c for c in cands))
    churn('node', node)
    for off, v in cands[:8]:
        churn('node+%X' % off, v, 0x800)
