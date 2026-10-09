#!/usr/bin/env python3
# =====================================================================
# !!! DO NOT RUN - CRASHED THE GAME (2026-10-09). Direct writes to
# beh+0x8D0 corrupt pointer fields on live objects. See MODLOG entry
# "CRASH POST-MORTEM" + bf-coop/crash_dump_analysis.txt.            !!!
# =====================================================================
"""Actuation test, visible edition.

1. Scan: player, keeper Edwards, crowd NPCs.
2. Baseline: classify crowd into movers/idlers (2.5s).
3. Teleport the nearest keeper Edward 4m in front of the player (visible).
4. Live-stream the reference WALKING NPC's anim-state row (beh+0x8D0, 24B)
   into the Edward + up to 2 nearby idle crowd NPCs at 20 Hz for 10s.
5. Report readback rows and position deltas.

Prints 'WRITING' right before the write loop (run with python -u so the
PowerShell harness can sync screenshots).
"""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x1F0FFF, False, pid)
if not h:
    raise SystemExit('OpenProcess failed')


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                                 ctypes.byref(g)):
        return None
    return b.raw[:g.value]


def wr(a, d):
    n = ctypes.c_size_t(0)
    return k32.WriteProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), d,
                                  len(d), ctypes.byref(n))


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0


def f3(a):
    b = rd(a, 12)
    return struct.unpack('<fff', b) if b and len(b) == 12 else None


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', ctypes.c_ulong), ('RegionSize', ctypes.c_size_t),
                ('State', ctypes.c_ulong), ('Protect', ctypes.c_ulong),
                ('Type', ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
edwards = []
players = []
crowd = []
while addr < 0x7FFF0000 and len(crowd) < 400:
    if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                              ctypes.sizeof(mbi)):
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
                    aa = base + off + j
                    blob = rd(aa, 0x100)
                    if blob and len(blob) >= 0xF0:
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if ch == 29 and cnt == 32:
                            edwards.append(aa)
                        elif ch == 32 and cnt == 34:
                            players.append(aa)
                        elif 16 <= ch <= 25 and cnt >= 16:
                            crowd.append(aa)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('scan: edwards=%d players=%d crowd=%d' % (len(edwards), len(players), len(crowd)),
      flush=True)
if not players:
    raise SystemExit('no player entity found')

ppos = f3(players[0] + 0x40)
qb = rd(players[0] + 0x50, 16)
if qb and len(qb) == 16:
    qx, qy, qz, qw = struct.unpack('<4f', qb)
else:
    qz, qw = 0.0, 1.0
th = 2.0 * math.atan2(qz, qw)
fwd = (math.sin(th), math.cos(th))
right = (fwd[1], -fwd[0])
print('player pos=(%.1f,%.1f,%.1f) quat_z=%.3f quat_w=%.3f fwd=(%.2f,%.2f)'
      % (ppos[0], ppos[1], ppos[2], qz, qw, fwd[0], fwd[1]), flush=True)


def keyf(e):
    p = f3(e + 0x40)
    return d2(p, ppos) if p else 1e9


# baseline
pos0 = {}
for e in crowd:
    p = f3(e + 0x40)
    if p:
        pos0[e] = p
time.sleep(2.5)
movers = []
idlers = []
for e, p0 in pos0.items():
    p1 = f3(e + 0x40)
    if not p1:
        continue
    if d2(p0, p1) > 0.35:
        movers.append(e)
    else:
        idlers.append(e)
print('baseline: movers=%d idlers=%d (of %d)' % (len(movers), len(idlers), len(pos0)),
      flush=True)

ref = min(movers, key=keyf) if movers else None
ref_beh = u32(ref + 0xE8) if ref else 0
FALLBACK_ROW = struct.pack('<12H', 0x0152, 0x0153, 0x0154, 0x0155, 0x0156, 0x0157,
                           0x0130, 0x013D, 0x013E, 0, 0, 0)
if ref:
    print('reference mover ent=0x%08X beh=0x%08X vt=0x%08X' % (ref, ref_beh, u32(ref_beh)),
          flush=True)

# targets: 2 nearest idle crowd + nearest edward
near_idle = sorted(idlers, key=keyf)[:2]
targets = [e for e in near_idle if f3(e + 0x40)]

ed_tgt = None
if edwards:
    ed = min(edwards, key=keyf)
    ed_beh = u32(ed + 0xE8)
    ed_vt = u32(ed_beh)
    print('edward ent=0x%08X beh=0x%08X beh_vt=0x%08X pos=%s'
          % (ed, ed_beh, ed_vt, str(f3(ed + 0x40))), flush=True)
    tpos = (ppos[0] + fwd[0] * 4.0 + right[0] * 1.2,
            ppos[1] + fwd[1] * 4.0 + right[1] * 1.2,
            ppos[2])
    wr(ed + 0x40, struct.pack('<fff', *tpos))
    time.sleep(0.3)
    print('edward teleported -> %s' % str(f3(ed + 0x40)), flush=True)
    if 0x10000 <= ed_beh < 0x7FFF0000:
        targets.append(ed)
        ed_tgt = ed


def row_hex(e):
    beh = u32(e + 0xE8)
    if not (0x10000 <= beh < 0x7FFF0000):
        return '??'
    b = rd(beh + 0x8D0, 0x18)
    if not b or len(b) != 0x18:
        return '??'
    return ' '.join('%04X' % v for v in struct.unpack('<12H', b))


for t in targets:
    print('target 0x%08X pos=%s row=%s' % (t, str(f3(t + 0x40)), row_hex(t)), flush=True)

print('WRITING', flush=True)
t0 = time.time()
last_row = None
start_pos = {t: f3(t + 0x40) for t in targets}
sampled = False
while time.time() - t0 < 10.0:
    row = last_row
    if ref and 0x10000 <= ref_beh < 0x7FFF0000:
        b = rd(ref_beh + 0x8D0, 0x18)
        if b and len(b) == 0x18:
            last_row = b
            row = b
    if row is None:
        row = FALLBACK_ROW
    for t in targets:
        beh = u32(t + 0xE8)
        if 0x10000 <= beh < 0x7FFF0000:
            wr(beh + 0x8D0, row)
    el = time.time() - t0
    if 5.0 < el and not sampled:
        sampled = True
        for t in targets:
            print('  mid t=%.1f 0x%08X pos_delta=%.2fm row=%s'
                  % (el, t, d2(f3(t + 0x40) or start_pos[t], start_pos[t]), row_hex(t)),
                  flush=True)
    time.sleep(0.05)

print('write phase done', flush=True)
for t in targets:
    p = f3(t + 0x40)
    print('post 0x%08X pos_delta=%.2fm row_now=%s'
          % (t, d2(p, start_pos[t]) if p else -1.0, row_hex(t)), flush=True)
if ed_tgt:
    print('edward final pos=%s' % str(f3(ed_tgt + 0x40)), flush=True)
print('done', flush=True)
