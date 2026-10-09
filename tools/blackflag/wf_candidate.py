#!/usr/bin/env python3
"""READ-ONLY: rank NPCs by live writes at ctl+0x2F00..0x2F0F and print WATCH line.

Usage: wf_candidate.py <pid> [sec]
Prints 'WATCH 0xCTL' for the hottest candidate (for watch-writer-addr.ps1).
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

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
        npcs.append([a, A, B, ctl, 0, 0.0, None])

prev = {}
lastpos = {}
for n in npcs:
    d = rd(n[3] + 0x2F00, 0x10)
    if d:
        prev[n[3]] = d
    lastpos[n[3]] = f3(n[0] + 0x40)

t0 = time.time()
while time.time() - t0 < DUR:
    time.sleep(0.2)
    for n in npcs:
        d = rd(n[3] + 0x2F00, 0x10)
        p = f3(n[0] + 0x40)
        old = prev.get(n[3])
        prev[n[3]] = d
        if d and old and d != old:
            n[4] += sum(1 for j in range(len(d)) if d[j] != old[j])
        q = lastpos.get(n[3])
        if p and q:
            dd = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
            if dd > n[5]:
                n[5] = dd
        lastpos[n[3]] = p

rows = sorted(npcs, key=lambda n: -n[4])
print('== hottest ctl+0x2F00 (%.1fs) ==' % (time.time() - t0))
for n in rows[:12]:
    a, A, B, ctl, ch, mx, _ = n
    print('ent=0x%08X A=%d B=%d ctl=0x%08X chg=%d moved=%.2f' % (a, A, B, ctl, ch, mx))
if rows and rows[0][4] > 0:
    print('WATCH 0x%08X' % rows[0][3])
else:
    print('NO WATCH CANDIDATE')
