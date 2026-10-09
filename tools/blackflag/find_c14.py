#!/usr/bin/env python3
"""READ-ONLY: find a steady walker; print children; report the 01E6CC50 child.

Usage: find_c14.py <pid> [sample_sec]
Prints 'C14 0xADDR' once the child is found (for the write-watchpoint tool),
then samples c14+0x2F40 / c14+0x2F58 for sample_sec and reports changes.
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
SAMP = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0

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

print('chars=%d' % len(chars))
p0 = {a: f3(a + 0x40) for (a, A, B) in chars}
time.sleep(1.5)
scored = []
for (a, A, B) in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 1.5
        scored.append((d, a, A, B))
scored.sort(reverse=True)


def steady(a):
    ps = [f3(a + 0x40)]
    for _ in range(2):
        time.sleep(0.6)
        ps.append(f3(a + 0x40))
    spd = []
    for i in range(1, 3):
        if not ps[i] or not ps[i - 1]:
            return None
        dd = ((ps[i][0] - ps[i - 1][0]) ** 2 + (ps[i][1] - ps[i - 1][1]) ** 2) ** 0.5 / 0.6
        spd.append(dd)
    return spd if all(0.3 < s < 8.0 for s in spd) else None


best = None
for (d, a, A, B) in [x for x in scored if 0.3 < x[0] < 8.0][:8]:
    spd = steady(a)
    if spd:
        best = (a, A, B, spd)
        break
if not best:
    print('NO STEADY WALKER')
    sys.exit(2)

ent, A, B, spd = best
print('target ent=0x%08X A=%d B=%d speeds=%s' % (ent, A, B, ['%.2f' % s for s in spd]))

cbase = u32(ent + 0x60)
ccnt = min(u16(ent + 0x66), 64)
kids = []
for i in range(ccnt):
    c = u32(cbase + i * 4)
    if 0x10000 <= c < 0x7FFF0000:
        kids.append((i, c, u32(c)))
        print('  [%2d] 0x%08X vt=0x%08X' % (i, c, u32(c)))

c14 = None
for i, c, vt in kids:
    if vt == 0x01E6CC50:
        c14 = c
        break
if not c14:
    print('NO 01E6CC50 CHILD')
    sys.exit(3)

print('C14 0x%08X' % c14, flush=True)

lastpos = f3(ent + 0x40)
prev40 = u32(c14 + 0x2F40)
prev58 = u32(c14 + 0x2F58)
ch40 = ch58 = 0
t0 = time.time()
while time.time() - t0 < SAMP:
    time.sleep(0.2)
    t = time.time() - t0
    pos = f3(ent + 0x40) or lastpos
    spd_now = 0.0
    if pos and lastpos:
        spd_now = ((pos[0] - lastpos[0]) ** 2 + (pos[1] - lastpos[1]) ** 2) ** 0.5 / 0.2
    lastpos = pos
    v40 = u32(c14 + 0x2F40)
    v58 = u32(c14 + 0x2F58)
    if v40 != prev40:
        ch40 += 1
        print('t=%5.1f spd=%.2f 2F40 %08X > %08X' % (t, spd_now, prev40, v40))
        prev40 = v40
    if v58 != prev58:
        ch58 += 1
        print('t=%5.1f spd=%.2f 2F58 %08X > %08X' % (t, spd_now, prev58, v58))
        prev58 = v58
print('changes 2F40=%d 2F58=%d over %.0fs' % (ch40, ch58, SAMP))
