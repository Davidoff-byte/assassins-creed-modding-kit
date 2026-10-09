#!/usr/bin/env python3
"""READ-ONLY: rank per-dword write activity in ctl+0x2000..0x3000 across all NPCs.

Prints top (npc, ctl, dword offset) rows and a 'WATCH ctl off' line for the
hottest one (for watch-writer-addr.ps1).

Usage: scan_hot2.py <pid> [sec]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0

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
                        A, B = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= A <= 64 and B <= 64:
                            chars.append((a, A, B))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

npcs = []
for (a, A, B) in chars:
    ctl = u32(a + 0xE8)
    if 0x10000 <= ctl < 0x7FFF0000:
        npcs.append((a, A, B, ctl))

prev = {ctl: rd(ctl + 0x2000, 0x1000) for (a, A, B, ctl) in npcs}
counts = {}
t0 = time.time()
sweeps = 0
while time.time() - t0 < DUR:
    time.sleep(0.25)
    sweeps += 1
    for (a, A, B, ctl) in npcs:
        cur = rd(ctl + 0x2000, 0x1000)
        old = prev.get(ctl)
        prev[ctl] = cur
        if not cur or not old or cur == old:
            continue
        for i in range(0, min(len(cur), len(old)) - 3, 4):
            if cur[i:i + 4] != old[i:i + 4]:
                k = (ctl, 0x2000 + i)
                counts[k] = counts.get(k, 0) + 1

rows = sorted(counts.items(), key=lambda kv: -kv[1])
print('sweeps=%d over %.1fs' % (sweeps, time.time() - t0))
for (ctl, off), c in rows[:25]:
    ent = next((a for (a, A, B, q) in npcs if q == ctl), 0)
    print('ent=0x%08X ctl=0x%08X +0x%04X chg=%d' % (ent, ctl, off, c))
if rows:
    (ctl, off), c = rows[0]
    print('WATCH 0x%08X 0x%04X' % (ctl, off))
else:
    print('NO ACTIVITY')
