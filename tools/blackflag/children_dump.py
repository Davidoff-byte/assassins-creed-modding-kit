#!/usr/bin/env python3
"""Enumerate an entity's components (children list) and probe each for the
anim live fields (+0x8D0) and request slots (+0x2F50)."""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
ENT = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x432D7810

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0


def u16(a):
    b = rd(a, 2)
    return struct.unpack('<H', b)[0] if b and len(b) == 2 else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b and len(b) == 12 else None


base = u32(ENT + 0x60)
cnt = u16(ENT + 0x66)
p0 = f3(ENT + 0x40)
time.sleep(0.5)
p1 = f3(ENT + 0x40)
spd = 0.0
if p0 and p1:
    spd = (((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5) / 0.5
e8 = u32(ENT + 0xE8)
print('entity 0x%08X vt=0x%08X ch=%d cnt=%d speed=%.2f pos=%s' % (
    ENT, u32(ENT), u16(ENT + 0x64), cnt, spd,
    ('(%.1f,%.1f,%.1f)' % p1) if p1 else '?'))
print('ent+0xE8 = 0x%08X vt(0x%08X)' % (e8, u32(e8)))
print('children base=0x%08X count=%d' % (base, cnt))
for i in range(min(cnt, 64)):
    c = u32(base + i * 4)
    if not (0x10000 <= c < 0x7FFF0000):
        print('  [%2d] -' % i)
        continue
    vt = u32(c)
    anim = rd(c + 0x8C8, 0x28)
    slots = rd(c + 0x2F48, 0x40)
    atxt = ''
    if anim:
        vals = [struct.unpack_from('<I', anim, k)[0] for k in range(0, 0x28, 4)]
        atxt = ' anim:' + ' '.join('%08X' % v for v in vals)
    stxt = ''
    if slots:
        vals = [struct.unpack_from('<I', slots, k)[0] for k in range(0, 0x40, 4)]
        stxt = ' slots:' + ' '.join('%08X' % v for v in vals)
    m2 = rd(c + 0x26E0, 0x08)
    m3 = rd(c + 0x28F0, 0x08)
    t2 = (' m26E0:' + m2.hex().upper()) if m2 else ''
    t3 = (' m28F0:' + m3.hex().upper()) if m3 else ''
    print('  [%2d] 0x%08X vt=0x%08X%s%s%s%s' % (i, c, vt, atxt, stxt, t2, t3))
