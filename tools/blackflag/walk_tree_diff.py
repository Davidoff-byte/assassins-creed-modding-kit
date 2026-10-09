#!/usr/bin/env python3
"""READ-ONLY walking-NPC full-tree differ (v2).

Picks the best-moving crowd NPC (ch 16..29, prefers ch==29 Edwards), then
byte-diffs: entity (0x400), behavior ctl (0x3800), and up to 40 entity
children (0x1000 each) across a WALK window and a STAND window.

Pure reads. Usage: walk_tree_diff.py <pid> [walk_sec] [stand_sec] [out]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR_WALK = float(sys.argv[2]) if len(sys.argv) > 2 else 16.0
DUR_STAND = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
OUT = sys.argv[4] if len(sys.argv) > 4 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\walk_tree_diff.txt")

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('OpenProcess failed')


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    if not ok or g.value != n:
        return None
    return b.raw


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
while addr < 0x7FFF0000 and len(chars) < 400:
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
                        if 16 <= ch <= 29 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('candidates:', len(chars), flush=True)

# measure movement over 2.5s
p0 = {}
for a, ch, cnt in chars:
    p0[a] = f3(a + 0x40)
time.sleep(2.5)
scored = []
for a, ch, cnt in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = abs(p[0] - q[0]) + abs(p[1] - q[1])
        scored.append((d, a, ch, cnt))
scored.sort(reverse=True)
best = scored[:8]
print('top movers:', flush=True)
for d, a, ch, cnt in best:
    print('  0x%08X ch=%d cnt=%d moved=%.2f' % (a, ch, cnt, d), flush=True)

target = None
for d, a, ch, cnt in scored:
    if d > 0.5:
        target = (a, ch, cnt)
        break
if not target and scored and scored[0][0] > 0.15:
    d, a, ch, cnt = scored[0]
    target = (a, ch, cnt)

if not target:
    print('NO MOVING CROWD NPC - world frozen?', flush=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('NO MOVING CROWD NPC\n')
    raise SystemExit(2)

ent, ch, cnt = target
ctl = u32(ent + 0xE8)
print('TARGET ent=0x%08X ch=%d cnt=%d ctl=0x%08X' % (ent, ch, cnt, ctl), flush=True)


def build_regions():
    regs = [('ent', ent, 0x400)]
    if ctl and 0x10000 <= ctl < 0x7FFF0000:
        regs.append(('ctl', ctl, 0x3800))
    cnt2 = u16(ent + 0x66)
    if 1 <= cnt2 <= 72:
        lp = rd(ent + 0x60, cnt2 * 4)
        if lp:
            got = 0
            for i in range(min(cnt2, 40)):
                c = struct.unpack_from('<I', lp, i * 4)[0]
                if not (0x10000 <= c < 0x7FFF0000):
                    continue
                vt = u32(c)
                ok = (0x00400000 <= vt <= 0x00700000) or (0x46000000 <= vt <= 0x7FFF0000)
                if not ok:
                    continue
                regs.append(('c%02d' % i, c, 0x1000))
                got += 1
            print('children used:', got, 'of', cnt2, flush=True)
    return regs


regions = build_regions()
for name, base, ln in regions:
    vt = u32(base)
    print('region %s base=0x%08X len=0x%X vt=0x%08X' % (name, base, ln, vt), flush=True)


def diff_window(tag, dur):
    base_data = {}
    for name, b, ln in regions:
        data = rd_buf(b, ln)
        if data:
            base_data[name] = data
    prev = dict(base_data)
    changes = {}   # (name, off) -> [count, [values...] (cap 40)]
    t0 = time.time()
    move_pairs = 0
    lastpos = None
    while time.time() - t0 < dur:
        p = f3(ent + 0x40)
        if p and lastpos and abs(p[0] - lastpos[0]) + abs(p[1] - lastpos[1]) > 0.03:
            move_pairs += 1
        lastpos = p
        for name, b, ln in regions:
            cur = rd_buf(b, ln)
            if cur is None:
                continue
            old = prev.get(name)
            if old is None:
                prev[name] = cur
                continue
            if cur != old:
                for i in range(len(cur)):
                    if cur[i] != old[i]:
                        k = (name, i)
                        rec = changes.get(k)
                        if rec is None:
                            changes[k] = [1, [cur[i]]]
                        else:
                            rec[0] += 1
                            if len(rec[1]) < 40:
                                rec[1].append(cur[i])
                prev[name] = cur
        time.sleep(0.1)
    return changes, move_pairs


walk_ch, walk_moves = diff_window('WALK', DUR_WALK)
print('walk window done: move-pairs=%d, changed offsets=%d' % (walk_moves, len(walk_ch)), flush=True)

# wait for a quiet stretch (max 24s)
quiet = False
t0 = time.time()
while time.time() - t0 < 24:
    a = f3(ent + 0x40)
    time.sleep(1.0)
    b = f3(ent + 0x40)
    if a and b and abs(b[0] - a[0]) + abs(b[1] - a[1]) < 0.08:
        quiet = True
        break

stand_ch, stand_moves = diff_window('STAND', DUR_STAND) if quiet else ({}, 0)
print('stand window: quiet=%s move-pairs=%d changed offsets=%d' % (quiet, stand_moves, len(stand_ch)), flush=True)

lines = []
lines.append('# regions:')
for name, b, ln in regions:
    lines.append('#  %s base=0x%08X len=0x%X' % (name, b, ln))
lines.append('# walk: move-pairs=%d changed=%d | stand: move-pairs=%d changed=%d' % (
    walk_moves, len(walk_ch), stand_moves, len(stand_ch)))

lines.append('')
lines.append('== walk-only changers (changed in walk, not in stand), top by count ==')
walk_only = [(k, v) for k, v in walk_ch.items() if stand_ch.get(k, [0])[0] <= 2]
walk_only.sort(key=lambda kv: -kv[1][0])
for (name, off), (cnt, vals) in walk_only[:80]:
    seq = ' '.join('%02X' % v for v in vals[:24])
    lines.append('%s +0x%03X  x%-4d  seq: %s' % (name, off, cnt, seq))

lines.append('')
lines.append('== top changers overall (walk | stand) ==')
allk = sorted(set(walk_ch) | set(stand_ch),
              key=lambda k: -(walk_ch.get(k, [0])[0] + stand_ch.get(k, [0])[0]))
for k in allk[:80]:
    name, off = k
    wc = walk_ch.get(k, [0, []])[0]
    sc = stand_ch.get(k, [0, []])[0]
    vals = (walk_ch.get(k) or stand_ch.get(k))[1]
    seq = ' '.join('%02X' % v for v in vals[:24])
    lines.append('%s +0x%03X  w%-4d s%-4d  seq: %s' % (name, off, wc, sc, seq))

txt = '\n'.join(lines) + '\n'
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(txt)
print(txt, flush=True)
