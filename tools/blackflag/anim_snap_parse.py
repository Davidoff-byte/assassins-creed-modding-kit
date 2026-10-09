#!/usr/bin/env python3
"""anim_snap_parse.py - analyze anim_snap.csv (read-only).

Reports which ent/ctl/state-object byte offsets change while the NPC is moving
(speed>0.5) vs standing (speed<0.2), plus a focused dword history for the
known walk-diff cells.

Usage: python anim_snap_parse.py [csv]
"""
import csv
import sys

path = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\anim_snap.csv")
rows = list(csv.DictReader(open(path, encoding='utf-8')))

# column -> (base label, region base offset)
cols = {
    'e70': ('ent', 0x70), 'eB0': ('ent', 0xB0),
    'c8B0': ('ctl', 0x8B0), 'soHdr': ('so', 0x0),
    'c26C8': ('ctl', 0x26C8), 'c28E0': ('ctl', 0x28E0),
    'cEB8': ('ctl', 0xEB8), 'cE20': ('ctl', 0xE20), 'c2F40': ('ctl', 0x2F40),
}


def hx(s):
    return bytes.fromhex(s) if s and s != '-' else b''


# per byte offset history: list of (t, value, speed_at_sample)
coll = {k: {} for k in cols}
sp = []
for r in rows:
    t = float(r['t'])
    speed = float(r['speed'])
    sp.append(speed)
    for k in cols:
        b = hx(r[k])
        cur = coll[k]
        for j, v in enumerate(b):
            o = cols[k][1] + j
            hist = cur.setdefault(o, [])
            if not hist or hist[-1][1] != v:
                hist.append((t, v, speed))

n = len(rows)
print('samples=%d dur=%.1fs speed avg=%.2f max=%.2f' %
      (n, float(rows[-1]['t']), sum(sp) / n, max(sp)))
print('speed>0.5: %d samples | speed<0.2: %d samples | in-between: %d' %
      (sum(1 for s in sp if s > 0.5), sum(1 for s in sp if s < 0.2),
       sum(1 for s in sp if 0.2 <= s <= 0.5)))

print()
print('== per-offset change counts (moving vs standing) ==')
for k, (base, off) in cols.items():
    cur = coll[k]
    interesting = []
    for o, hist in sorted(cur.items()):
        c = len(hist) - 1
        if c <= 0:
            continue
        cm = sum(1 for h in hist[1:] if h[2] > 0.5)
        cs = sum(1 for h in hist[1:] if h[2] < 0.2)
        interesting.append((c, cm, cs, o, hist[0][1], hist[-1][1]))
    interesting.sort(reverse=True)
    print('%s (%s+0x%X): %d changed offsets; top:' % (k, base, off, len(interesting)))
    for c, cm, cs, o, v0, v1 in interesting[:18]:
        d = o - off
        print('   +0x%03X chg=%3d mv=%3d st=%3d  0x%02X..0x%02X' % (d, c, cm, cs, v0, v1))

# focused dword histories
FOCUS = [
    ('ctl', 0x8D4), ('ctl', 0x8D8), ('ctl', 0x8DC), ('ctl', 0x8E0),
    ('ctl', 0xEC4), ('ctl', 0xE34), ('ctl', 0x26D8), ('ctl', 0x26E0),
    ('ctl', 0x26E4), ('ctl', 0x26E8), ('ctl', 0x28F0), ('ctl', 0x28F4),
    ('ctl', 0x28F8), ('ctl', 0x2F50), ('ctl', 0x2F54), ('ctl', 0x2F58),
    ('ctl', 0x2F5C), ('ctl', 0x2F60), ('ctl', 0x2F64),
]


def region_for(base, off):
    for k, (b, o) in cols.items():
        if b == base and o <= off and off + 4 <= o + len(hx(rows[0][k] or '')):
            return k, off - o
    return None, None


print()
print('== focused dword histories (change points only) ==')
for base, off in FOCUS:
    k, i = region_for(base, off)
    if k is None:
        print('%s+0x%X: not captured' % (base, off))
        continue
    vals = []
    for r in rows:
        b = hx(r[k])
        if len(b) < i + 4:
            continue
        v = int.from_bytes(b[i:i + 4], 'little')
        t = float(r['t'])
        s = float(r['speed'])
        if not vals or vals[-1][1] != v:
            vals.append((t, v, s))
    nch = len(vals) - 1
    show = vals if nch <= 24 else vals[:12] + [('...', 0, 0)] + vals[-6:]
    txt = ' '.join(
        ('%.1f:%08X(s%.1f)' % (t, v, s)) if t != '...' else '...'
        for (t, v, s) in show)
    print('%s+0x%X chg=%d: %s' % (base, off, nch, txt))
