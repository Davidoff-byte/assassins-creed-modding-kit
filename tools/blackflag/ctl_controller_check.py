#!/usr/bin/env python3
"""READ-ONLY pre-check: crowd ctl embedded controller layout.

For each crowd character (ch 16..29): ctl = u32(ent+0xE8). Dump ctl+0x8A0..0x910
as 4-byte words; for the u32 at ctl+0x8DC check readability, deref its vtable
(u32 at ptr) and classify (module range 0x400000-0x528000 / heap / other).

No writes. Usage: ctl_controller_check.py <pid>
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


def classify(v):
    if 0x400000 <= v <= 0x528000:
        return 'MODULE'
    if 0x10000000 <= v <= 0x7FFF0000:
        return 'heap?'
    return '-'


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
chars = []
player = 0
while addr < 0x7FFF0000 and len(chars) < 500:
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
                        if ch == 32 and cnt == 34:
                            player = a
                        elif 16 <= ch <= 29 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('player=0x%08X  crowd chars=%d' % (player, len(chars)))

# player ctl comparison
if player:
    pctl = u32(player + 0xE8)
    b = rd(pctl + 0x8C0, 0x30) if pctl else None
    print('PLAYER ctl=0x%08X +8C0: %s' % (pctl, b.hex().upper() if b else '-'))

# dump +0x8A0..0x910 for first 6 crowd chars
for a, ch, cnt in chars[:6]:
    ctl = u32(a + 0xE8)
    if not ctl:
        print('ent=0x%08X ch=%d no ctl' % (a, ch))
        continue
    b = rd(ctl + 0x8A0, 0x70)
    pos = f3(a + 0x40)
    if b:
        words = struct.unpack('<28I', b)
        print('ent=0x%08X ch=%d cnt=%d pos=(%.1f,%.1f,%.1f) ctl=0x%08X' % (
            a, ch, cnt, pos[0], pos[1], pos[2], ctl))
        for i in range(0, 28, 4):
            off = 0x8A0 + i * 4
            row = words[i:i + 4]
            extra = ''
            if off == 0x8A0:
                extra = ' vt(+0x8B0)=' + str(classify(u32(ctl + 0x8B0)))
            print('   +%03X: %s' % (off, ' '.join('%08X' % w for w in row) + extra))
        # state object at +0x8DC
        so = u32(ctl + 0x8DC)
        if so:
            vt = u32(so)
            print('   stateobj(+0x8DC)=0x%08X vt=0x%08X [%s]' % (so, vt, classify(vt)))
            head = rd(so, 0x40)
            if head:
                print('   stateobj head: %s' % head.hex().upper())
        else:
            print('   stateobj(+0x8DC)=0')
    else:
        print('ent=0x%08X ctl=0x%08X unreadable' % (a, ctl))
