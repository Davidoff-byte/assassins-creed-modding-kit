#!/usr/bin/env python3
"""READ-ONLY: probe all ch=29 Edwards (or given ch) - speed + ctl walk-region dumps.

Dumps for each: ent, ctl, pos/speed, ent+0x70..0x7C floats, ent+0xB0..0xBC,
ctl+0x26D0..0x2700 and ctl+0x28E0..0x2910 twice (1.2s apart) showing ticks.

Usage: edw_walk_probe.py <pid> [ch]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
CH = int(sys.argv[2]) if len(sys.argv) > 2 else 29

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
                        if ch == CH:
                            chars.append((a, cnt, ch))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('ch=%d chars: %d' % (CH, len(chars)))
for (a, cnt, ch) in chars:
    ctl = u32(a + 0xE8)
    p0 = f3(a + 0x40)
    time.sleep(1.2)
    p1 = f3(a + 0x40)
    spd = 0.0
    if p0 and p1:
        spd = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5 / 1.2
    print('== ent=0x%08X cnt=%d ctl=0x%08X ctlvt=0x%08X speed=%.2f ==' % (
        a, cnt, ctl, u32(ctl), spd))
    print('   pos=(%.1f,%.1f,%.1f) f32@0x70..0x7C: %.3f %.3f %.3f %.3f' % (
        *(p1 or (0, 0, 0)), f32(a + 0x70), f32(a + 0x74), f32(a + 0x78), f32(a + 0x7C)))
    print('   f32@0xB0..0xBC: %.3f %.3f %.3f %.3f' % (
        f32(a + 0xB0), f32(a + 0xB4), f32(a + 0xB8), f32(a + 0xBC)))
    b = rd(ctl + 0x26D0, 0x30)
    if b:
        print('   ctl+0x26D0: ' + ' '.join('%08X' % struct.unpack_from('<I', b, k)[0]
                                           for k in range(0, 0x30, 4)))
    b = rd(ctl + 0x28E0, 0x30)
    if b:
        print('   ctl+0x28E0: ' + ' '.join('%08X' % struct.unpack_from('<I', b, k)[0]
                                           for k in range(0, 0x30, 4)))
    time.sleep(0.6)
    b2 = rd(ctl + 0x26D0, 0x30)
    if b2:
        print('   ctl+0x26D0: ' + ' '.join('%08X' % struct.unpack_from('<I', b2, k)[0]
                                           for k in range(0, 0x30, 4)))
    b2 = rd(ctl + 0x28E0, 0x30)
    if b2:
        print('   ctl+0x28E0: ' + ' '.join('%08X' % struct.unpack_from('<I', b2, k)[0]
                                           for k in range(0, 0x30, 4)))
