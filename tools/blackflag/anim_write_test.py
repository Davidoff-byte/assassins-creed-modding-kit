#!/usr/bin/env python3
# =====================================================================
# !!! DO NOT RUN - CRASHED THE GAME (2026-10-09). Direct writes to
# beh+0x8D0 corrupt pointer fields on live objects. See MODLOG entry
# "CRASH POST-MORTEM" + bf-coop/crash_dump_analysis.txt.            !!!
# =====================================================================
"""Direct anim-state test: find a free Edward + the player + crowd movers,
print their state rows at beh+0x8D0, then write a walking-family row into the
Edward for 4s and an idle-family row for 4s, with per-second readback:
does our write stick (engine doesn't own the region) or get stomped (engine
re-derives it every frame)?
"""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x1F0FFF, False, pid)


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


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


VT = struct.pack('<I', 0x01E4CE90)
mbi = MBI()
addr = 0x10000
edwards = []
players = []
crowd = []
while addr < 0x7FFF0000 and len(crowd) < 400:
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
                        if ch == 29 and cnt == 32:
                            edwards.append(a)
                        if ch == 32 and cnt == 34:
                            players.append(a)
                        if 16 <= ch <= 25 and cnt >= 16:
                            crowd.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('edwards:', ['0x%08X' % e for e in edwards])
print('players:', ['0x%08X' % p for p in players])
print('crowd candidates:', len(crowd))

# world-live check: watch first crowd char's position for 1.2s
live = False
if crowd:
    p0 = rd(crowd[0] + 0x40, 12)
    time.sleep(1.2)
    p1 = rd(crowd[0] + 0x40, 12)
    if p0 and p1:
        a0 = struct.unpack('<fff', p0)
        a1 = struct.unpack('<fff', p1)
        d = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
        live = True  # char exists; but motion tells world state
        print('world check: char moved %.2fm in 1.2s -> world %s' % (
            d, 'LIVE' if d > 0.2 else 'frozen (focused? paused?)'))

if not edwards:
    raise SystemExit('no edward found')


def row_of(ent):
    beh = u32(ent + 0xE8)
    if not (0x10000 <= beh < 0x7FFF0000):
        return None, None, None
    b = rd(beh + 0x8D0, 0x12)
    if not b:
        return beh, None, None
    return beh, ' '.join('%04X' % v for v in struct.unpack('<9H', b)), beh


ent = edwards[0]
beh = u32(ent + 0xE8)
pos0 = struct.unpack('<fff', rd(ent + 0x40, 12))
print('target ent=0x%08X beh=0x%08X pos=(%.1f,%.1f,%.1f)' % (ent, beh, *pos0))
b, r, _ = row_of(ent)
print('edward row before: %s' % r)
if players:
    pb, pr, _ = row_of(players[0])
    print('player beh=0x%08X row: %s' % (pb, pr))

WALK = struct.pack('<9H', 0x0152, 0x0153, 0x0154, 0x0155, 0x0156, 0x0157, 0x0130, 0x013D, 0x013E)
IDLE = struct.pack('<9H', 0x0020, 0x0021, 0x0022, 0x0023, 0x0024, 0x0025, 0x0026, 0x0027, 0x0028)


def burst(row, dur, label):
    t0 = time.time()
    last = -1.0
    while time.time() - t0 < dur:
        wr(beh + 0x8D0, row)
        t = time.time() - t0
        if t - last >= 1.0:
            last = t
            bb = rd(beh + 0x8D0, 0x12)
            pp = rd(ent + 0x40, 12)
            if bb and pp:
                pos = struct.unpack('<fff', pp)
                print(' %-4s t=%.1f back=%s pos=(%.1f,%.1f)' % (
                    label, t, ' '.join('%04X' % v for v in struct.unpack('<9H', bb)),
                    pos[0], pos[1]))
        time.sleep(0.05)


burst(WALK, 4, 'walk')
burst(IDLE, 4, 'idle')
bb = rd(beh + 0x8D0, 0x12)
print('final row: %s' % ' '.join('%04X' % v for v in struct.unpack('<9H', bb)))
print('done')
