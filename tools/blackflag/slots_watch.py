#!/usr/bin/env python3
"""Walk-request hunt: locate the request-slot object for live NPCs and sample
position + slots while they walk, to learn the walk request values."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
MAXC = 10

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


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

print('candidate chars:', len(chars))

tracked = []
for a, ch, cnt in chars:
    ctl = u32(a + 0xE8)
    if not (0x10000 <= ctl < 0x7FFF0000):
        continue
    o1 = u32(ctl + 0x18)
    if not (0x10000 <= o1 < 0x7FFF0000):
        continue
    sub = u32(o1 + 0xC)
    if not (0x10000 <= sub < 0x7FFF0000):
        continue
    sl = rd(sub + 0x2F50, 0x18)
    if not sl:
        continue
    slots = struct.unpack('<IIIIII', sl)
    pos = struct.unpack_from('<fff', rd(a + 0x40, 12), 0)
    tracked.append([a, ch, cnt, ctl, o1, sub, list(slots), list(pos)])
    if len(tracked) >= MAXC:
        break

print('tracked:')
for t in tracked:
    print('  ent=0x%08X ch=%d cnt=%d ctl=0x%08X sub=0x%08X slots=%s pos=(%.1f,%.1f,%.1f)' % (
        t[0], t[1], t[2], t[3], t[5], ['%08X' % s for s in t[6]], *t[7]))

print('--- sampling %.0fs ---' % DUR)
t0 = time.time()
while time.time() - t0 < DUR:
    for t in tracked:
        sl = rd(t[5] + 0x2F50, 0x18)
        p = rd(t[0] + 0x40, 12)
        if not sl or not p:
            continue
        slots = struct.unpack('<IIIIII', sl)
        pos = struct.unpack('<fff', p)
        moved = math.hypot(pos[0] - t[7][0], pos[1] - t[7][1])
        if moved > 0.05 or slots != tuple(t[6]):
            print('t=%4.1f ent=0x%08X moved=%.2f pos=(%.1f,%.1f) slots=%s' % (
                time.time() - t0, t[0], moved, pos[0], pos[1],
                ['%08X' % s for s in slots]))
        t[7] = list(pos)
        t[6] = list(slots)
    time.sleep(0.15)
print('done')
