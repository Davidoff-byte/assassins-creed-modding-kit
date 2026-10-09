#!/usr/bin/env python3
"""READ-ONLY: catch idle<->walk transitions of nearby NPCs and value-diff their
ctl + walk-child regions (the fields that are constant-but-different between states).

Usage: transition_snap.py <pid> [seconds]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
duration = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
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


class M(ctypes.Structure):
    _fields_ = [('b', ctypes.c_void_p), ('ab', ctypes.c_void_p), ('ap', ctypes.c_ulong),
                ('rs', ctypes.c_size_t), ('st', ctypes.c_ulong), ('pr', ctypes.c_ulong),
                ('ty', ctypes.c_ulong)]


def scan_chars():
    m = M()
    addr = 0x10000
    out = []
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
                                out.append(a)
                        j = b.find(vt, j + 4)
                off += n
        addr = base + size
    return out


chars = scan_chars()
subj = []
for a in chars:
    p = f3(a + 0x40)
    if not p:
        continue
    kb = u32(a + 0x60)
    cnt = u16(a + 0x66)
    c14 = None
    for i in range(min(cnt, 48)):
        k = u32(kb + i * 4)
        if u32(k) == 0x01E41E58:
            c14 = k
            break
    if c14:
        subj.append([a, c14, u32(a + 0xE8), p, [], None, 0.0])
print('subjects (have c14): %d' % len(subj))

R_CTL = (0x880, 0x100)
R_C14 = (0x0C0, 0xE0)


def snap(ctl, c14):
    return (rd(ctl + R_CTL[0], R_CTL[1]), rd(c14 + R_C14[0], R_C14[1]))


t0 = time.time()
tick = 0
while time.time() - t0 < duration:
    tick += 1
    for s in subj:
        a, c14, ctl, p0, hist, last, cd = s
        if time.time() < cd:
            continue
        p = f3(a + 0x40)
        if not p:
            continue
        sp = ((p[0] - p0[0]) ** 2 + (p[1] - p0[1]) ** 2) ** 0.5
        s[3] = p
        hist.append(sp)
        if len(hist) > 6:
            hist.pop(0)
        if len(hist) >= 6:
            old = sum(hist[:3]) / 3.0
            new = sum(hist[3:]) / 3.0
            if old < 0.02 and new > 0.03 or old > 0.03 and new < 0.02:
                if time.time() >= cd:
                    cur = snap(ctl, c14)
                    if last is not None:
                        ch = []
                        for tag, base, prev, now in (
                                ('ctl+%03X', R_CTL[0], last[0], cur[0]),
                                ('c14+%03X', R_C14[0], last[1], cur[1])):
                            if prev and now:
                                for off in range(0, min(len(prev), len(now)) - 3, 4):
                                    v1 = struct.unpack_from('<I', prev, off)[0]
                                    v2 = struct.unpack_from('<I', now, off)[0]
                                    if v1 != v2:
                                        ch.append('%s v %08X->%08X' % (tag % (base + off), v1, v2))
                        if ch:
                            print('TRANSITION ent=0x%08X spd %.3f->%.3f: %s' % (
                                a, old, new, '; '.join(ch[:14])))
                            sys.stdout.flush()
                    s[5] = cur
                    s[6] = time.time() + 2.0
                    s[4] = []
                    continue
        if s[5] is None and tick % 5 == 0:
            s[5] = snap(ctl, c14)
    time.sleep(0.18)
print('done')
