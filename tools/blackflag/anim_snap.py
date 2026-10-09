#!/usr/bin/env python3
"""READ-ONLY: high-rate snapshot of a walking crowd NPC's ctl regions.

Picks a genuine walker (steady 0.3..8 m/s), then samples at ~10 Hz for DUR sec:
  pos/speed; ent+0x70..0x80; ent+0xB0..0xC0;
  ctl+0x8B0..0x8F0 (incl. state ptr at +0x8DC + its deref header);
  ctl+0x26C8..0x2700; ctl+0x28E0..0x2918; ctl+0xEB8..0xEF0; ctl+0xE20..0xE58;
  ctl+0x2F40..0x2F80 (request-slot area).
CSV per sample. No writes.

Usage: anim_snap.py <pid> [dur_sec] [outfile]
"""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
OUT = sys.argv[3] if len(sys.argv) > 3 else (
    r"C:\Users\Administrator\Documents\Default Project\bf-coop\anim_snap.csv")

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None


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
                        if 16 <= ch <= 31 and 16 <= cnt <= 64:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

# --- steady-walker picker: prefilter -> verify top candidates ----
p0 = {a: f3(a + 0x40) for (a, ch, cnt) in chars}
time.sleep(1.5)
scored = []
for (a, ch, cnt) in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 / 1.5
        scored.append((d, a, ch, cnt))
scored.sort(reverse=True)
print('top movers (prefilter):')
for (d, a, ch, cnt) in scored[:8]:
    print('  ent=0x%08X ch=%d cnt=%d d=%.2f' % (a, ch, cnt, d), flush=True)


def steady(a):
    ps = [f3(a + 0x40)]
    for _ in range(3):
        time.sleep(0.5)
        ps.append(f3(a + 0x40))
    spd = []
    for i in range(1, 4):
        if not ps[i] or not ps[i - 1]:
            return None
        dd = ((ps[i][0] - ps[i - 1][0]) ** 2 + (ps[i][1] - ps[i - 1][1]) ** 2) ** 0.5 / 0.5
        spd.append(dd)
    return spd if all(0.3 < s < 8.0 for s in spd) else None


best = None
for (d, a, ch, cnt) in [(d, a, ch, cnt) for (d, a, ch, cnt) in scored if 0.3 < d < 8.0][:10]:
    spd = steady(a)
    if spd:
        best = (a, ch, cnt, spd)
        break
if not best:
    for (d, a, ch, cnt) in [(d, a, ch, cnt) for (d, a, ch, cnt) in scored if 0.12 < d <= 0.3][:8]:
        spd = steady(a)
        if spd:
            best = (a, ch, cnt, spd)
            break

if not best:
    print('NO STEADY WALKER FOUND (world paused or all streaming)')
    sys.exit(2)

ent, ch, cnt, spd = best
ctl = u32(ent + 0xE8)
print('target ent=0x%08X ch=%d cnt=%d speeds=%s ctl=0x%08X' % (
    ent, ch, cnt, ['%.1f' % s for s in spd], ctl), flush=True)


def hx(b):
    return b.hex().upper() if b else '-'


lines = []
t0 = time.time()
prev = None
while time.time() - t0 < DUR:
    t = time.time() - t0
    pos = f3(ent + 0x40) or (0, 0, 0)
    so = u32(ctl + 0x8DC)
    so_d = rd(so, 0x10) if 0x10000 <= so <= 0x7FFF0000 else None
    spd_now = 0.0
    if prev:
        dt = t - prev[0]
        if dt > 0:
            spd_now = ((pos[0] - prev[1][0]) ** 2 + (pos[1] - prev[1][1]) ** 2) ** 0.5 / dt
    prev = (t, pos)
    lines.append('%.2f,%.2f,%.2f,%.2f,%.2f,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (
        t, pos[0], pos[1], pos[2], spd_now,
        hx(rd(ent + 0x70, 0x10)), hx(rd(ent + 0xB0, 0x10)),
        hx(rd(ctl + 0x8B0, 0x40)),
        '0x%08X' % so, hx(so_d),
        hx(rd(ctl + 0x26C8, 0x38)), hx(rd(ctl + 0x28E0, 0x38)),
        hx(rd(ctl + 0xEB8, 0x38)), hx(rd(ctl + 0xE20, 0x38)),
        hx(rd(ctl + 0x2F40, 0x40))))
    time.sleep(0.1)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('t,x,y,z,speed,e70,eB0,c8B0,so,soHdr,c26C8,c28E0,cEB8,cE20,c2F40\n')
    f.write('\n'.join(lines) + '\n')
print('written %s (%d samples)' % (OUT, len(lines)), flush=True)
