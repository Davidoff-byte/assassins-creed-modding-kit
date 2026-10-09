#!/usr/bin/env python3
"""READ-ONLY: find the best walking NPC and print its children (for the watchpoint).

Prints for each child: index, address, vtable. Highlights vt=0x01E41E58
(the walk-state child) and prints 'WATCH 0x<addr> 0x2C4' when found.

Usage: find_walker_children.py <pid> [min_speed] [max_speed]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
MINS = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
MAXS = float(sys.argv[3]) if len(sys.argv) > 3 else 2.6

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('OpenProcess failed')


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
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size
print('candidates: %d' % len(chars), flush=True)

p0 = {a: f3(a + 0x40) for a, ch, cnt in chars}
time.sleep(2.0)
scored = []
for a, ch, cnt in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 2.0
        scored.append((d, a, ch, cnt))
scored.sort(reverse=True)
for d, a, ch, cnt in scored[:6]:
    print('  0x%08X ch=%d cnt=%d speed=%.2f' % (a, ch, cnt, d), flush=True)

target = None
for d, a, ch, cnt in scored:
    if MINS < d < MAXS:
        target = (d, a, ch, cnt)
        break
if not target and scored and scored[0][0] > 0.4:
    target = scored[0]
if not target:
    print('NO MOVING NPC')
    sys.exit(2)

d, ent, ch, cnt = target
ctl = u32(ent + 0xE8)
print('TARGET ent=0x%08X ch=%d cnt=%d speed=%.2f ctl=0x%08X' % (ent, ch, cnt, d, ctl), flush=True)

cbase = u32(ent + 0x60)
ccnt = min(u16(ent + 0x66), 48)
walk_child = None
for i in range(ccnt):
    c = u32(cbase + i * 4)
    if not (0x10000 <= c < 0x7FFF0000):
        continue
    vt = u32(c)
    tag = ''
    if vt == 0x01E41E58:
        walk_child = c
        tag = '  <== walk-state child (vt 01E41E58)'
    print('  [%2d] 0x%08X vt=0x%08X%s' % (i, c, vt, tag), flush=True)

if walk_child:
    print('WATCH 0x%08X 0x2C4' % walk_child)
else:
    print('NOTE: no vt=0x01E41E58 child on this npc')
