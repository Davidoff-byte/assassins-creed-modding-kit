#!/usr/bin/env python3
"""READ-ONLY: hunt for live ctl regions across all character NPCs.

For every char entity, reads ctl+0x2000..0x3000 in 0x100 blocks a few times
per second; counts changed bytes per (npc, block) and prints the top ones.
Also tracks each NPC's speed.

Usage: tick_hunt.py <pid> [sec]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0

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
                        A, B = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= A <= 64 and B <= 64:
                            chars.append((a, A, B))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('chars=%d' % len(chars), flush=True)

npcs = []
for (a, A, B) in chars:
    ctl = u32(a + 0xE8)
    if 0x10000 <= ctl < 0x7FFF0000:
        npcs.append([a, A, B, ctl, {}, None])

prev = {}
for n in npcs:
    d = rd(n[3] + 0x2000, 0x1000)
    if d:
        prev[n[3]] = d
    n[5] = f3(n[0] + 0x40)

t0 = time.time()
sweeps = 0
lastpos = {n[3]: n[5] for n in npcs}
while time.time() - t0 < DUR:
    for n in npcs:
        d = rd(n[3] + 0x2000, 0x1000)
        p = f3(n[0] + 0x40)
        if p and lastpos.get(n[3]):
            dx = abs(p[0] - lastpos[n[3]][0]) + abs(p[1] - lastpos[n[3]][1])
        else:
            dx = 0.0
        lastpos[n[3]] = p
        old = prev.get(n[3])
        prev[n[3]] = d
        if d and old and d != old:
            for i in range(len(d)):
                if d[i] != old[i]:
                    blk = ('0x%04X' % (0x2000 + (i & 0xF00)))
                    rec = n[4].get(blk)
                    if rec is None:
                        n[4][blk] = [1, dx]
                    else:
                        rec[0] += 1
                        rec[1] = max(rec[1], dx)
    sweeps += 1
    time.sleep(0.3)

print('sweeps=%d' % sweeps)
rows = []
for n in npcs:
    a, A, B, ctl, blocks, _ = n
    vt = u32(ctl)
    for blk, (cnt, maxdx) in blocks.items():
        rows.append((cnt, a, A, B, ctl, vt, blk, maxdx))
rows.sort(reverse=True)
for (cnt, a, A, B, ctl, vt, blk, maxdx) in rows[:40]:
    print('ent=0x%08X A=%d B=%d ctl=0x%08X vt=0x%08X %s chg=%d maxdx=%.2f' % (
        a, A, B, ctl, vt, blk, cnt, maxdx))
if not rows:
    print('NO CHANGES ANYWHERE')
