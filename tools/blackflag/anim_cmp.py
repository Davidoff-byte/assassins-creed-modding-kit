#!/usr/bin/env python3
"""READ-ONLY: compare anim field region ctl+0x8C0..0x8F8 for player vs walking crowd NPC.

Usage: anim_cmp.py <pid>
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


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


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
                            chars.append((a, cnt, ch))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for (a, c, ch) in chars}
time.sleep(1.2)
scored = []
for (a, c, ch) in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 1.2
        scored.append((d, a, c, ch))
scored.sort(reverse=True)


def show(tag, a, c, ch, d):
    ctl = u32(a + 0xE8)
    print('== %s ent=0x%08X ch=%d cnt=%d speed=%.2f ctl=0x%08X ctlvt=0x%08X ==' % (
        tag, a, ch, c, d, ctl, u32(ctl)))
    b = rd(ctl + 0x8C0, 0x40)
    if b:
        for row in range(0, 0x40, 0x10):
            vals = ' '.join('%08X' % struct.unpack_from('<I', b, row + k * 4)[0] for k in range(4))
            fls = ' '.join('%9.4f' % struct.unpack_from('<f', b, row + k * 4)[0] for k in range(4))
            print('   +%03X: %s   | %s' % (0x8C0 + row, vals, fls))


# player = ch32
pl = [s for s in scored if s[3] == 32]
if pl:
    show('PLAYER', pl[0][1], pl[0][2], pl[0][3], pl[0][0])
    b = rd(u32(pl[0][1] + 0xE8) + 0x8C0, 0x40)
    time.sleep(0.8)
    b2 = rd(u32(pl[0][1] + 0xE8) + 0x8C0, 0x40)
    if b and b2:
        ch = [i for i in range(0x40) if b[i] != b2[i]]
        print('   player ctl changes (0.8s): ' + ','.join('%02X' % i for i in ch))
# best walker (non player)
for d, a, c, ch in scored[:5]:
    if ch != 32:
        show('WALKER%.2f' % d, a, c, ch, d)
        ctl = u32(a + 0xE8)
        b = rd(ctl + 0x8C0, 0x40)
        time.sleep(0.8)
        b2 = rd(ctl + 0x8C0, 0x40)
        if b and b2:
            chg = [i for i in range(0x40) if b[i] != b2[i]]
            print('   walker ctl changes (0.8s): ' + ','.join('%02X' % i for i in chg))
        break
