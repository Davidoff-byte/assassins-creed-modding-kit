#!/usr/bin/env python3
"""External follow-drive: glue a chosen Edward body to the live player by
writing his feet (+0x40) every ~90ms to (player feet + offset). The same math
the plugin's ghost-drive uses, but from outside - no plugin hook needed.

Usage: python follow_drive.py <pid> <entity_hexaddr> [duration_s] [offset_x] [offset_y]"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
ent = int(sys.argv[2], 16)
dur = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
ox = float(sys.argv[4]) if len(sys.argv) > 4 else 1.6
oy = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5

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

t0 = time.time()
last_print = -10.0
writes = 0
while time.time() - t0 < dur:
    f = player_feet()
    if f and abs(f[0]) + abs(f[1]) > 20:
        wr(ent + 0x40, struct.pack('<fff', f[0] + ox, f[1] + oy, f[2]))
        writes += 1
    now = time.time() - t0
    if now - last_print >= 5:
        last_print = now
        e = rd(ent + 0x40, 12)
        e = struct.unpack('<fff', e) if e and len(e) == 12 else (0, 0, 0)
        ptxt = '(%.1f,%.1f)' % (f[0], f[1]) if f else 'none'
        print('t=%5.0fs player=%s edward=(%.1f,%.1f) writes=%d' % (
            now, ptxt, e[0], e[1], writes))
        sys.stdout.flush()
    time.sleep(0.09)
print('done; writes=%d' % writes)
