#!/usr/bin/env python3
"""READ-ONLY: which child component of a walking NPC carries walk state?

Scans character entities (inventory print), picks a steady walker, then
watches each child's candidate regions at ~5 Hz for DUR s, counting changed
bytes while moving (speed > 0.4) vs standing (< 0.2).

Usage: child_watch.py <pid> [dur_sec] [outfile]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
OUT = sys.argv[3] if len(sys.argv) > 3 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\child_watch.txt")

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

print('== inventory (%d chars) ==' % len(chars))
for (a, A, B) in chars:
    p = f3(a + 0x40)
    print('ent=0x%08X +64=%3d +66=%3d vt=0x%08X pos=%s' % (
        a, A, B, u32(a), ('(%.1f,%.1f,%.1f)' % p) if p else '?'), flush=True)

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
print('top movers: ' + ' '.join('0x%08X:%.2f' % (a, d) for (d, a, A, B) in scored[:6]),
      flush=True)


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
for (d, a, A, B) in [(d, a, A, B) for (d, a, A, B) in scored if 0.3 < d < 8.0][:8]:
    spd = steady(a)
    if spd:
        best = (a, A, B, spd)
        break
if not best:
    if not scored:
        print('NO CHARS FOUND')
        sys.exit(2)
    best = (scored[0][1], scored[0][2], scored[0][3], None)
    print('no verified steady walker - watching top mover anyway', flush=True)

ent, A, B, vspd = best
print('watching ent=0x%08X (+64=%d +66=%d) verified=%s' % (ent, A, B, vspd), flush=True)

cbase = u32(ent + 0x60)
ccnt = min(u16(ent + 0x66), 64)
kids = []
for i in range(ccnt):
    c = u32(cbase + i * 4)
    if 0x10000 <= c < 0x7FFF0000:
        kids.append((i, c, u32(c)))
print('children: %d valid of %d' % (len(kids), ccnt))
for (i, c, vt) in kids:
    print('  [%2d] 0x%08X vt=0x%08X' % (i, c, vt), flush=True)

REG = [('anim', 0x8C0, 0x50), ('slots', 0x2F00, 0x90),
       ('a26', 0x26D0, 0x28), ('a28', 0x28E0, 0x28)]
EREG = [('eH', 0x60, 0x80), ('eB', 0xB0, 0x10)]

targets = []
for (i, c, vt) in kids:
    for (k, o, L) in REG:
        targets.append(('c%02d/%s' % (i, k), c + o, L))
for (k, o, L) in EREG:
    targets.append(('ent/%s' % k, ent + o, L))

prev = {}
for (lab, a, L) in targets:
    d = rd(a, L)
    if d is not None:
        prev[lab] = d

events = {}
mv_samples = st_samples = others = 0
t0 = time.time()
lastpos = f3(ent + 0x40)
samples = 0
while time.time() - t0 < DUR:
    t = time.time() - t0
    pos = f3(ent + 0x40) or lastpos
    spd = 0.0
    if pos and lastpos:
        spd = ((pos[0] - lastpos[0]) ** 2 + (pos[1] - lastpos[1]) ** 2) ** 0.5 / 0.15
    lastpos = pos
    if spd > 0.4:
        mv_samples += 1
    elif spd < 0.2:
        st_samples += 1
    else:
        others += 1
    for (lab, a, L) in targets:
        cur = rd(a, L)
        if cur is None:
            continue
        old = prev.get(lab)
        prev[lab] = cur
        if old is None or cur == old:
            continue
        for bi in range(min(len(cur), len(old))):
            if cur[bi] != old[bi]:
                e = events.get((lab, bi))
                if e is None:
                    e = [0, 0, old[bi], cur[bi], t]
                    events[(lab, bi)] = e
                if spd > 0.4:
                    e[0] += 1
                elif spd < 0.2:
                    e[1] += 1
                e[3] = cur[bi]
    samples += 1
    time.sleep(0.15)

lines = []
lines.append('# watched ent=0x%08X children=%d samples=%d mv=%d st=%d other=%d' % (
    ent, len(kids), samples, mv_samples, st_samples, others))
ranked = sorted(events.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
for (lab, bi), (mv, st, v0, v1, tf) in ranked:
    lines.append('%-12s +0x%03X mv=%4d st=%4d  0x%02X..0x%02X (first t=%.1f)' % (
        lab, bi, mv, st, v0, v1, tf))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('samples=%d mv=%d st=%d other=%d  -> %s' % (
    samples, mv_samples, st_samples, others, OUT), flush=True)
for ln in lines[1:41]:
    print(ln, flush=True)
