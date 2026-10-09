#!/usr/bin/env python3
"""READ-ONLY: pick the hottest pose among a walker's NON-final skeleton refs.

For the top real walker (0.5-4 m/s): churn-check all four refs (c14+0x134/0x138/0x140/0x144);
prefer the biggest churn among 0x138/0x140/0x144; fall back to 0x134.
Prints HOT <addr> <refoffset> <churn>.

Usage: srcwatch5.py <pid>
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


def churn(a, n=0x200, dt=0.12):
    b1 = rd(a, n)
    if not b1:
        return None
    time.sleep(dt)
    b2 = rd(a, n)
    if not b2:
        return None
    best = []
    for off in range(0, n, 4):
        ch = sum(1 for i in range(4) if b1[off + i] != b2[off + i])
        if ch:
            best.append((ch, a + off))
    best.sort(reverse=True)
    return best


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
time.sleep(0.9)
scored = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 0.9
        scored.append((d, a))
scored.sort(reverse=True)
walkers = [(d, a) for d, a in scored if 0.5 <= d <= 4.0]
print('walkers 0.5-4 m/s: %d' % len(walkers))

for d, a in walkers[:5]:
    kb = u32(a + 0x60)
    cnt = u16(a + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if not c14:
        continue
    hits = []
    for off in (0x138, 0x140, 0x144, 0x134):
        skel = u32(c14 + off)
        if not skel:
            continue
        pose = u32(skel + 0xa4)
        if not pose:
            continue
        res = churn(pose)
        ch = res[0][0] if res else 0
        hot = res[0][1] if res else 0
        print('npc=0x%08X speed=%.2f c14+0x%X skel=0x%08X mode=%d -> churn=%d hot=0x%08X' % (
            a, d, off, skel, u32(skel + 0x90), ch, hot))
        if ch >= 3:
            hits.append((off, ch, hot, skel, pose))
    if hits:
        # prefer non-0x134 refs
        pref = [x for x in hits if x[0] != 0x134]
        pick = max(pref or hits, key=lambda x: x[1])
        print('HOT 0x%08X ref=0x%X churn=%d skel=0x%08X pose=0x%08X' % (pick[2], pick[0], pick[1], pick[3], pick[4]))
        sys.exit(0)
print('NO HOT DWORD')
sys.exit(1)
