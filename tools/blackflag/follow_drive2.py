#!/usr/bin/env python3
"""Intuitive follow-drive: the Edward walks toward the player at a natural
pace, stops when near, resumes when the player moves away. Ground-following
only (keeps his own Z unless the player's height differs by <2.5m - stairs
fine, roofs => he waits below = no parkour, which is the point of the test).

Usage: python follow_drive2.py <pid> <entity_hexaddr> [duration_s]"""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
ent = int(sys.argv[2], 16)
dur = float(sys.argv[3]) if len(sys.argv) > 3 else 420.0

STOP_D = 2.6        # stop walking when closer than this
GO_D = 3.8          # resume walking when farther than this
WALK_SPEED = 2.1    # m/s
RUN_SPEED = 4.0     # m/s when far away
RUN_DIST = 12.0     # distance at which he starts to jog

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x1F0FFF, False, pid)
if not h:
    raise SystemExit('OpenProcess failed for pid %d' % pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


def wr(a, d):
    n = ctypes.c_size_t(0)
    return k32.WriteProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), d,
                                  len(d), ctypes.byref(n))


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0


def player_feet():
    mgr = u32(0x2ABE588)
    if not mgr:
        return None
    holder = u32(mgr + 0x4C)
    if not holder:
        return None
    camobj = u32(holder)
    if not camobj:
        return None
    block = u32(camobj + 0x68)
    if not block:
        return None
    prov = u32(block + 0x174)
    if prov:
        b = rd(prov + 0x110, 12)
        return struct.unpack('<fff', b) if b and len(b) == 12 else None
    cnt = u32(mgr + 0x130)
    idx = cnt % 5
    b = rd(mgr + 0x90 + idx * 0x10, 12)
    return struct.unpack('<fff', b) if b and len(b) == 12 else None


blob = rd(ent, 0x100)
if not blob:
    raise SystemExit('cannot read entity 0x%08X' % ent)
vt = struct.unpack_from('<I', blob, 0)[0]
cnt, ch = struct.unpack_from('<HH', blob, 0x64)
print('entity 0x%08X vt=0x%08X ch=%d cnt=%d' % (ent, vt, ch, cnt))
if not (vt == 0x01E4CE90 and ch == 29 and cnt == 32):
    raise SystemExit('signature mismatch - aborting')

cur = list(struct.unpack_from('<fff', blob, 0x40))
walking = False
t0 = time.time()
last_print = -10.0
tick_dt = 0.05
ticks = 0

while time.time() - t0 < dur:
    lt = time.time()
    f = player_feet()
    if f and abs(f[0]) + abs(f[1]) > 20:
        px, py, pz = f
        fx, fy, fz = cur
        dx = px - fx
        dy = py - fy
        dist = math.hypot(dx, dy)

        if walking and dist <= STOP_D:
            walking = False
        elif not walking and dist >= GO_D:
            walking = True

        if walking and dist > 0.01:
            speed = RUN_SPEED if dist > RUN_DIST else WALK_SPEED
            step = min(speed * tick_dt, dist - STOP_D * 0.5)
            fx += dx / dist * step
            fy += dy / dist * step
            if abs(pz - fz) < 2.5:
                fz = pz
            cur = [fx, fy, fz]
            wr(ent + 0x40, struct.pack('<fff', *cur))
        else:
            # hold position (prevents his crowd AI from wandering off)
            wr(ent + 0x40, struct.pack('<fff', *cur))
        ticks += 1

    now = time.time() - t0
    if now - last_print >= 4:
        last_print = now
        e = rd(ent + 0x40, 12)
        e = struct.unpack('<fff', e) if e and len(e) == 12 else (0, 0, 0)
        mode = ('WALK' if walking else 'stop') if f else 'n/a'
        pdist = math.hypot(e[0] - f[0], e[1] - f[1]) if f else -1
        ptxt = '(%.1f,%.1f,%.1f)' % f if f else 'none'
        print('t=%5.0fs player=%s edward=(%.1f,%.1f,%.1f) d=%.1fm %s ticks=%d' % (
            now, ptxt, e[0], e[1], e[2], pdist, mode, ticks))
        sys.stdout.flush()
    sl = tick_dt - (time.time() - lt)
    if sl > 0:
        time.sleep(sl)
print('done; ticks=%d' % ticks)
