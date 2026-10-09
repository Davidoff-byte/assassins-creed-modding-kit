#!/usr/bin/env python3
"""READ-ONLY: compare a walking NPC vs a standing one - floats near the entity.

Prints for one fast mover and one stander:
  pos, computed speed, ent+0x70..0x7C as floats, ent+0xB0..0xBC as floats,
  and hex dumps of ctl+0x8C8..0x8F0.

Usage: speed_probe.py <pid>
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


def f32(a):
    b = rd(a, 4)
    return struct.unpack('<f', b)[0] if b else None


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
mover = scored[0]
standers = [s for s in scored if s[0] < 0.02]
stander = standers[0] if standers else scored[-1]


def show(tag, d, a):
    ctl = u32(a + 0xE8)
    print('== %s: ent=0x%08X moved=%.2fm in 1s ctl=0x%08X ==' % (tag, a, d, ctl))
    print('  pos=(%.2f,%.2f,%.2f) yaw-ish f32@0x70/74/78/7C: %.4f %.4f %.4f %.4f' % (
        *(f3(a + 0x40) or (0, 0, 0)), f32(a + 0x70), f32(a + 0x74), f32(a + 0x78), f32(a + 0x7C)))
    print('  f32@0xB0/B4/B8/BC: %.4f %.4f %.4f %.4f' % (
        f32(a + 0xB0), f32(a + 0xB4), f32(a + 0xB8), f32(a + 0xBC)))
    b = rd(ctl + 0x8C8, 0x28)
    if b:
        print('  ctl+8C8: ' + ' '.join('%08X' % struct.unpack_from('<I', b, k)[0]
                                       for k in range(0, 0x28, 4)))
        print('  ctl+8C8 floats: ' + ' '.join('%.3f' % struct.unpack_from('<f', b, k)[0]
                                              for k in range(0, 0x28, 4)))
    b2 = rd(a + 0x40, 0x40)
    if b2:
        pass


show('MOVER', mover[0], mover[1])
show('STANDER', stander[0], stander[1])
