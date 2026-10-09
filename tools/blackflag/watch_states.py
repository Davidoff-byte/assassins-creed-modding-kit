#!/usr/bin/env python3
"""READ-ONLY: watch crowd NPC anim-state candidates over time.

Samples at ~6 Hz for DURATION seconds: position + several ctl regions
(0x8C0..0x8F0, 0x26D0..0x2710, 0x28D0..0x2930) + recurses into the entity's
real child list (base = u32(ent+0x60), count = u16(ent+0x66)).

Prints compact timelines: MOVED events, +0x8DC state-pointer transitions,
counter changes. Pure reads.
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
OUT = sys.argv[3] if len(sys.argv) > 3 else None

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


def rd_buf(a, n):
    out = bytearray(n)
    ok_any = False
    off = 0
    while off < n:
        m = min(0x1000, n - off)
        b = rd(a + off, m)
        if b:
            out[off:off + m] = b
            ok_any = True
        off += m
    return bytes(out) if ok_any else None


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
player = 0
edwards = []
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
                        if ch == 32 and cnt == 34:
                            player = a
                        elif ch == 29 and cnt == 32 and len(edwards) < 6:
                            edwards.append(a)
                        elif 16 <= ch <= 25 and cnt >= 16 and len(chars) < 600:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

# movers
p0 = {a: f3(a + 0x40) for a, ch, cnt in chars}
time.sleep(1.2)
scored = []
for a, ch, cnt in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = abs(p[0] - q[0]) + abs(p[1] - q[1])
        scored.append((d, a, ch, cnt))
scored.sort(reverse=True)

targets = []
for e in edwards:
    targets.append(('edw', e))
targets.append(('player', player))
for d, a, ch, cnt in scored[:5]:
    targets.append(('mover_%.1f' % d, a))

print('player=0x%08X edwards=%s' % (player, ['0x%08X' % e for e in edwards]), flush=True)
print('targets:', targets, flush=True)

# --- structure of each target
for tag, ent in targets:
    ctl = u32(ent + 0xE8)
    cbase = u32(ent + 0x60)
    ccnt = u16(ent + 0x66)
    print('== %s ent=0x%08X ctl=0x%08X childbase=0x%08X nchild=%d' % (tag, ent, ctl, cbase, ccnt), flush=True)
    if 1 <= ccnt <= 100 and cbase:
        kids = rd(cbase, min(ccnt, 60) * 4)
        if kids:
            row = []
            for i in range(min(ccnt, 60)):
                c = struct.unpack_from('<I', kids, i * 4)[0]
                if not c:
                    row.append('#%d=0' % i)
                    continue
                vt = u32(c)
                mark = '=CTL' if c == ctl else ''
                row.append('#%d=0x%08X:vt=0x%08X%s' % (i, c, vt, mark))
            print('   children: ' + ' '.join(row), flush=True)

# --- sampling
REGIONS = [
    ('ent', 0x00, 0x80),
    ('ctA', 0x8C0, 0x40),
    ('ctB', 0x26C0, 0x60),
    ('ctC', 0x28C0, 0x70),
]
state = {}
t0 = time.time()
lines = []
n = 0
while time.time() - t0 < DUR:
    n += 1
    t = time.time() - t0
    for tag, ent in targets:
        ctl = u32(ent + 0xE8)
        if not ctl:
            continue
        pos = f3(ent + 0x40) or (0, 0, 0)
        cur = {}
        for rname, roff, rlen in REGIONS:
            base = ent if rname == 'ent' else ctl
            cur[rname] = rd_buf(base + roff, rlen)
        prev, ppos = state.get(tag, (None, None))
        msgs = []
        if ppos is not None:
            d = abs(pos[0] - ppos[0]) + abs(pos[1] - ppos[1])
            if d > 0.15:
                msgs.append('MOVED %.2f' % d)
        if prev is not None:
            for rname, roff, rlen in REGIONS:
                a = prev.get(rname)
                b = cur.get(rname)
                if a and b and a != b:
                    i = 0
                    while i < len(a):
                        if a[i] != b[i]:
                            j = i
                            while j < len(a) and a[j] != b[j]:
                                j += 1
                            if j - i <= 6:
                                msgs.append('%s+0x%03X[%d] %s>%s' % (
                                    rname, roff + i, j - i,
                                    a[i:j].hex().upper(), b[i:j].hex().upper()))
                            else:
                                msgs.append('%s+0x%03X[%d] %s>%s' % (
                                    rname, roff + i, j - i,
                                    a[i:j].hex().upper()[:16] + '..',
                                    b[i:j].hex().upper()[:16] + '..'))
                            i = j
                        else:
                            i += 1
        state[tag] = (cur, pos)
        if msgs:
            lines.append('t=%6.2f %-12s %s' % (t, tag, ' | '.join(msgs)))
    time.sleep(0.16)

txt = '\n'.join(lines)
print('--- events (%d lines) ---' % len(lines), flush=True)
print(txt[:12000], flush=True)
if OUT:
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(txt + '\n')
    print('written %s' % OUT, flush=True)

# state-ptr summary for ctA region
print('--- ctA+0x8DC values seen ---', flush=True)
for tag, ent in targets:
    ctl = u32(ent + 0xE8)
    v = u32(ctl + 0x8DC) if ctl else 0
    print('%s ctl=0x%08X +0x8DC=0x%08X +0x8D0=0x%08X +0x8D4=0x%08X +0x8D8=0x%08X' % (
        tag, ctl, v, u32(ctl + 0x8D0) if ctl else 0, u32(ctl + 0x8D4) if ctl else 0,
        u32(ctl + 0x8D8) if ctl else 0), flush=True)
