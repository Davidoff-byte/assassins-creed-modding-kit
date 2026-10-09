#!/usr/bin/env python3
"""Multi-region byte-diff sampler, READ-ONLY (no writes ever).

Tracks player + all Edwards (ch29/cnt32) + up to 6 moving crowd NPCs.
Regions sampled per object (byte-level diffs, logged with a timestamp):
  ent+0x40   len 0x20   (position/rotation)
  ctl+0x130  len 0x20   (in-action flag area)
  ctl+0x880  len 0xC0   (observed walk 'families' area)
  ctl+0x2F40 len 0x40   (request slots area)

Usage: anim_sampler.py <pid> [duration_sec] [out_file]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 900.0
OUT = sys.argv[3] if len(sys.argv) > 3 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\sampler_out.txt")

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


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b else 0


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
                        if ch >= 16 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

player = [c for c in chars if c[1] == 32 and c[2] == 34]
edwards = [c for c in chars if c[1] == 29 and c[2] == 32]
crowd = [c for c in chars if 16 <= c[1] <= 25 and c[2] >= 16]

def f3(a):
    b = rd(a + 0x40, 12)
    return struct.unpack('<fff', b) if b else None

# baseline movers
movers = []
pos0 = {}
for a, ch, cnt in crowd:
    p = f3(a)
    if p:
        pos0[a] = p
time.sleep(2.5)
for a, ch, cnt in crowd:
    p = f3(a)
    if p and a in pos0:
        if abs(p[0] - pos0[a][0]) + abs(p[1] - pos0[a][1]) > 0.3:
            movers.append((a, ch, cnt))
movers = movers[:6]

targets = player + edwards + movers
f = open(OUT, 'w', encoding='utf-8')
def emit(line):
    f.write(line + '\n')
    f.flush()

emit('# sampler start pid=%d player=%d edwards=%d movers=%d' % (
    pid, len(player), len(edwards), len(movers)))
for a, ch, cnt in targets:
    emit('# target ent=0x%08X ch=%d cnt=%d' % (a, ch, cnt))

REGIONS = [(0x40, 0x20, 'ent'), (0x130, 0x20, 'ctl'),
           (0x880, 0xC0, 'ctl'), (0x2F40, 0x40, 'ctl')]

state = {}   # (ent, regbase) -> bytes ; plus ctl per ent
ctls = {}
for a, ch, cnt in targets:
    ctls[a] = u32(a + 0xE8)

def region_bytes(ent, off, ln, reg):
    base = ent if reg == 'ent' else ctls.get(ent, 0)
    if not base:
        return None
    return rd(base + off, ln)

for a, ch, cnt in targets:
    for off, ln, reg in REGIONS:
        b = region_bytes(a, off, ln, reg)
        if b:
            state[(a, off)] = b

# movement state per ent
mstate = {}
for a, ch, cnt in targets:
    mstate[a] = False

t0 = time.time()
lines = 0
fails = 0
while time.time() - t0 < DUR and lines < 60000:
    for a, ch, cnt in targets:
        # movement detect
        p = f3(a)
        if p is not None and a in pos0:
            moved = abs(p[0] - pos0[a][0]) + abs(p[1] - pos0[a][1]) > 0.15
            if moved != mstate.get(a, False):
                mstate[a] = moved
                emit('t=%7.1f %s ent=0x%08X pos=(%.1f,%.1f,%.1f)' % (
                    time.time() - t0, 'MOVING -->' if moved else 'STOPPED ->', a, *p))
            pos0[a] = p
        for off, ln, reg in REGIONS:
            b = region_bytes(a, off, ln, reg)
            if b is None:
                continue
            old = state.get((a, off))
            if old is None:
                state[(a, off)] = b
                continue
            if b != old:
                # log changed byte runs
                i = 0
                while i < len(b):
                    if b[i] != old[i]:
                        j = i
                        while j < len(b) and b[j] != old[j]:
                            j += 1
                        run_old = old[i:j].hex().upper()
                        run_new = b[i:j].hex().upper()
                        emit('t=%7.1f ent=0x%08X %s+0x%03X [%d] %s > %s' % (
                            time.time() - t0, a, reg, off + i, j - i, run_old, run_new))
                        lines += 1
                        i = j
                    else:
                        i += 1
                state[(a, off)] = b
    fails = 0
    time.sleep(0.10)

emit('# sampler end (%.0fs, %d lines)' % (time.time() - t0, lines))
f.close()
print('sampler done: %d lines -> %s' % (lines, OUT))
