#!/usr/bin/env python3
"""Sprint-deliver v2: bodies sprint toward the player AND face where they move.
Writes the yaw basis rows (+0x10/+0x20) using the same math as the plugin
(row0=[c,s], row1=[-s,c]; for direction (dx,dy): row0=[dy,-dx], row1=[dx,dy]),
so the AI's own turning no longer wins. Position at +0x40 as before.

Usage: python sprint_drive2.py <pid> <duration_s> addr1 [addr2 ...]"""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
dur = float(sys.argv[2])
addrs = [int(a, 16) for a in sys.argv[3:]]
SPRINT = 7.0   # m/s
STOP = 2.5     # hold distance

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


def face(dirx, diry):
    """Rotation basis for facing unit direction (dirx,diry) with +Y-forward."""
    return struct.pack('<ffff', diry, -dirx, 0.0, 0.0) + \
           struct.pack('<ffff', dirx, diry, 0.0, 0.0)


state = {}
for a in addrs:
    blob = rd(a, 0x100)
    if not blob:
        raise SystemExit('cannot read 0x%08X' % a)
    vt = struct.unpack_from('<I', blob, 0)[0]
    cnt, ch = struct.unpack_from('<HH', blob, 0x64)
    ok = vt == 0x01E4CE90 and ch == 29 and cnt == 32
    print('0x%08X vt=0x%08X ch=%d cnt=%d %s' % (a, vt, ch, cnt, 'OK' if ok else 'BAD'))
    if not ok:
        raise SystemExit('signature mismatch - aborting')
    state[a] = list(struct.unpack_from('<fff', blob, 0x40))

dt = 0.05
t0 = time.time()
last_print = -10.0
ticks = 0
while time.time() - t0 < dur:
    lt = time.time()
    f = player_feet()
    if f and abs(f[0]) + abs(f[1]) > 20:
        for a in addrs:
            cur = state[a]
            dx = f[0] - cur[0]
            dy = f[1] - cur[1]
            d = math.hypot(dx, dy)
            if d > 0.01:
                ux, uy = dx / d, dy / d
            else:
                ux, uy = 0.0, 1.0
            if d > STOP:
                step = min(SPRINT * dt, d - STOP * 0.5)
                cur[0] += ux * step
                cur[1] += uy * step
                if abs(f[2] - cur[2]) < 2.5:
                    cur[2] = f[2]
                # face the movement direction (= toward the player)
                wr(a + 0x10, face(ux, uy))
            else:
                # holding: keep facing the player
                wr(a + 0x10, face(ux, uy))
            wr(a + 0x40, struct.pack('<fff', *cur))
        ticks += 1
    now = time.time() - t0
    if now - last_print >= 3:
        last_print = now
        txts = []
        for a in addrs:
            d = math.hypot(state[a][0] - f[0], state[a][1] - f[1]) if f else -1
            txts.append('%.0fm' % d)
        print('t=%4.0fs player=(%.1f,%.1f) dists=%s ticks=%d' % (
            now, f[0], f[1], ','.join(txts), ticks))
        sys.stdout.flush()
    sl = dt - (time.time() - lt)
    if sl > 0:
        time.sleep(sl)
print('done; ticks=%d' % ticks)
