#!/usr/bin/env python3
"""State-map capture: track walking NPCs for ~40s each; snapshot the six-entry
state table at beh+0x8D0 (+0x8E0) as u16s alongside position, to map idle/walk/
turn state families."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

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
                        if 16 <= ch <= 25 and cnt >= 16:
                            pos = struct.unpack_from('<fff', blob, 0x40)
                            chars.append([a, ch, list(pos)])
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

time.sleep(1.0)
movers = []
for c in chars:
    p = rd(c[0] + 0x40, 12)
    if not p:
        continue
    pos = struct.unpack('<fff', p)
    if math.hypot(pos[0] - c[2][0], pos[1] - c[2][1]) > 0.3:
        movers.append(c)
print('movers: %d of %d chars' % (len(movers), len(chars)))

t0 = time.time()
last = {}
while time.time() - t0 < DUR and movers:
    for c in movers[:4]:
        ent = c[0]
        beh = u32(ent + 0xE8)
        if not (0x10000 <= beh < 0x7FFF0000):
            continue
        b = rd(beh + 0x8D0, 0x12)
        p = rd(ent + 0x40, 12)
        if not b or not p:
            continue
        vals = struct.unpack('<9H', b)
        pos = struct.unpack('<fff', p)
        key = vals
        if last.get(ent) != key:
            last[ent] = key
            print('t=%5.1f ent=0x%08X tabs=%s pos=(%.1f,%.1f)' % (
                time.time() - t0, ent,
                ' '.join('%04X' % v for v in vals[:9]), pos[0], pos[1]))
    time.sleep(0.2)
print('capture done')
