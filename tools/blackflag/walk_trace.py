#!/usr/bin/env python3
"""READ-ONLY: high-rate trace of a walking crowd NPC's candidate anim regions.

Picks the best mover (ch 16..25), then samples at ~10 Hz for DUR seconds:
  ent+0x40 pos (speed), ctl+0x2680..0x2740, ctl+0x28C0..0x2960,
  ctl+0xE20..0xEE0 (swap partners), ctl+0x16C0..0x16E0.
Logs changed-byte events with timestamps to a file. No writes.

Usage: walk_trace.py <pid> [dur_sec] [outfile]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
OUT = sys.argv[3] if len(sys.argv) > 3 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\walk_trace.txt")

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


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
                        cnt, ch = struct.unpack_from('<HH', blob, 0x64)
                        if 16 <= ch <= 25 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

p0 = {a: f3(a + 0x40) for a, ch, cnt in chars}
time.sleep(1.5)
scored = []
for a, ch, cnt in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = abs(p[0] - q[0]) + abs(p[1] - q[1])
        scored.append((d, a, ch, cnt))
scored.sort(reverse=True)
movers = [s for s in scored if s[0] > 0.3]
if not movers:
    print('NO MOVING NPC (world paused?)')
    sys.exit(2)
best = movers[0]
ent, ch, cnt = best[1], best[2], best[3]
print('target ent=0x%08X ch=%d cnt=%d moved=%.2f' % (ent, ch, cnt, best[0]), flush=True)

ctl = u32(ent + 0xE8)
print('ctl=0x%08X' % ctl, flush=True)

REGIONS = [
    ('ctA', 0x2680, 0xC0),
    ('ctB', 0x28C0, 0xA0),
    ('ctC', 0x0E20, 0xC0),
    ('ctD', 0x16C0, 0x20),
    ('ctE', 0x22B0, 0x30),
    ('ctF', 0x13F0, 0x60),
]

base_data = {}
for name, roff, rlen in REGIONS:
    d = rd_buf(ctl + roff, rlen)
    if d:
        base_data[name] = d
prev = dict(base_data)

t0 = time.time()
lastpos = f3(ent + 0x40)
lines = []
speed_hist = []
while time.time() - t0 < DUR:
    t = time.time() - t0
    pos = f3(ent + 0x40)
    if pos and lastpos:
        dt = 0.1
        spd = (((pos[0] - lastpos[0]) ** 2 + (pos[1] - lastpos[1]) ** 2) ** 0.5) / max(dt, 1e-6)
        speed_hist.append((t, spd))
    lastpos = pos
    for name, roff, rlen in REGIONS:
        cur = rd_buf(ctl + roff, rlen)
        if cur is None:
            continue
        old = prev.get(name)
        if old is None:
            prev[name] = cur
            continue
        if cur != old:
            i = 0
            while i < len(cur):
                if cur[i] != old[i]:
                    j = i
                    while j < len(cur) and cur[j] != old[j]:
                        j += 1
                    lines.append('t=%6.2f %s+0x%03X [%d] %s > %s' % (
                        t, name, roff + i, j - i,
                        old[i:j].hex().upper(), cur[i:j].hex().upper()))
                    i = j
                else:
                    i += 1
            prev[name] = cur
    time.sleep(0.1)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('# target ent=0x%08X ch=%d ctl=0x%08X\n' % (ent, ch, ctl))
    f.write('# speed samples (t, m/s):\n')
    for t, s in speed_hist[::10]:
        f.write('#  t=%5.1f spd=%4.1f\n' % (t, s))
    for line in lines:
        f.write(line + '\n')

print('events=%d -> %s' % (len(lines), OUT), flush=True)
for line in lines[:80]:
    print(line, flush=True)
if len(lines) > 80:
    print('... (%d more in file)' % (len(lines) - 80), flush=True)
