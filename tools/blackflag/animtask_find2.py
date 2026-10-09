#!/usr/bin/env python3
"""READ-ONLY: hardened scan for anim-task objects linked to a walking NPC.

Signature A (timed blend): obj = hit-0x7C where hit is a dword == c14;
  requires: vtable at obj in module range, anim skel u32(obj+0x1B0) valid
  (mode +0x90 in {0,1}, pose +0xa4 readable), time f32(obj+0x1B4) and
  duration f32(obj+0x14) sane and 0 <= time <= 4*duration.
Signature B (layered blend): vtable ok, weight f32(obj+8) in [0,1.01],
  skels u32(obj+0x10C) and u32(obj+0x110) valid.

Usage: animtask_find2.py <pid>
"""
import ctypes
import math
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


def f32(a):
    b = rd(a, 4)
    return struct.unpack('<f', b)[0] if b else 0.0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b else None


def in_module(v):
    return 0x400000 <= v <= 0xF30000


def valid_skel(v):
    if not (0x10000 < v < 0xFF000000):
        return False
    mode = u32(v + 0x90)
    if mode > 3:
        return False
    pose = u32(v + 0xa4)
    if not (0x10000 < pose < 0xFF000000):
        return False
    if not rd(pose, 16):
        return False
    return True


def sane_float(x, lo, hi):
    return not math.isnan(x) and not math.isinf(x) and lo <= x <= hi


class M(ctypes.Structure):
    _fields_ = [('b', ctypes.c_void_p), ('ab', ctypes.c_void_p), ('ap', ctypes.c_ulong),
                ('rs', ctypes.c_size_t), ('st', ctypes.c_ulong), ('pr', ctypes.c_ulong),
                ('ty', ctypes.c_ulong)]


m = M()
addr = 0x10000
chars = []
vt = struct.pack('<I', 0x01E4CE90)
while addr < 0x7FFF0000:
    if not k32.VirtualQueryEx(ctypes.c_void_p(h), ctypes.c_void_p(addr), ctypes.byref(m), ctypes.sizeof(m)):
        break
    base = m.b or 0
    size = m.rs
    if m.st == 0x1000 and m.pr in (4, 8, 0x40, 0x80):
        off = 0
        while off < size:
            n = min(1 << 20, size - off)
            b = rd(base + off, n)
            if b:
                j = b.find(vt)
                while j >= 0:
                    a = base + off + j
                    blob = rd(a, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 40 and cnt <= 64:
                            chars.append(a)
                    j = b.find(vt, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for a in chars}
time.sleep(0.9)
sc = []
for a in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 0.9
        sc.append((d, a))
sc.sort(reverse=True)
walkers = [(d, a) for d, a in sc if 0.8 <= d <= 4.0]
if not walkers:
    print('NO WALKER')
    sys.exit(1)
d, a = walkers[0]
kb = u32(a + 0x60)
cnt = u16(a + 0x66)
c14 = None
for i in range(min(cnt, 48)):
    k = u32(kb + i * 4)
    if u32(k) == 0x01E41E58:
        c14 = k
        break
ent = a
print('walker npc=0x%08X spd=%.2f c14=0x%08X' % (a, d, c14))

needles = {'c14': c14, 'ent': ent}
for tag, nd in needles.items():
    if not nd:
        continue
    needle = struct.pack('<I', nd)
    hits = []
    mbi = M()
    addr = 0x10000
    while addr < 0x7FFF0000:
        if not k32.VirtualQueryEx(ctypes.c_void_p(h), ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.b or 0
        size = mbi.rs
        if mbi.st == 0x1000 and mbi.pr in (4, 8, 0x40, 0x80):
            off = 0
            while off < size:
                n = min(1 << 20, size - off)
                b = rd(base + off, n)
                if b:
                    j = b.find(needle)
                    while j >= 0:
                        hits.append(base + off + j)
                        j = b.find(needle, j + 4)
                off += n
        addr = base + size
    print('== needle %s 0x%08X refs=%d ==' % (tag, nd, len(hits)))
    shown = 0
    for hh in hits:
        for off in (0x7C, 0x80):
            obj = hh - off
            if obj <= 0:
                continue
            vtable = u32(obj)
            if not in_module(vtable):
                continue
            # signature A
            skel = u32(obj + 0x1B0)
            if valid_skel(skel):
                t = f32(obj + 0x1B4)
                dur = f32(obj + 0x14)
                if sane_float(t, 0.0, 1e7) and sane_float(dur, 0.001, 1e6) and t <= dur * 4 + 1:
                    w = f32(obj + 8)
                    print('  A obj=0x%08X vt=0x%08X w=%.3f t=%.3f dur=%.3f animSkel=0x%08X (+ref off 0x%X)' % (
                        obj, vtable, w, t, dur, skel, off))
                    shown += 1
                    continue
            # signature B
            w = f32(obj + 8)
            if sane_float(w, 0.0, 1.01):
                skA = u32(obj + 0x10C)
                skB = u32(obj + 0x110)
                if valid_skel(skA) and valid_skel(skB):
                    print('  B obj=0x%08X vt=0x%08X w=%.3f skelA=0x%08X skelB=0x%08X (+ref off 0x%X)' % (
                        obj, vtable, w, skA, skB, off))
                    shown += 1
        if shown > 40:
            break
    if shown == 0:
        print('  (no candidates)')
