#!/usr/bin/env python3
"""Find a walking NPC and watch where its animation-related bytes change:
samples the +0x8D0..0x910 region on the entity's controller chain for movers."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
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
                            chars.append([a, ch, cnt, list(pos)])
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

print('chars:', len(chars))
time.sleep(1.0)
movers = []
for c in chars:
    p = rd(c[0] + 0x40, 12)
    if not p:
        continue
    pos = struct.unpack('<fff', p)
    d = math.hypot(pos[0] - c[3][0], pos[1] - c[3][1])
    if d > 0.3:
        movers.append((c[0], c[1], d, pos))
print('movers:', len(movers))
for m in movers[:6]:
    print('  ent=0x%08X ch=%d moved=%.2f pos=(%.1f,%.1f)' % m)

if movers:
    ent = movers[0][0]
    beh = u32(ent + 0xE8)
    print('watching ent 0x%08X beh 0x%08X' % (ent, beh))
    prev = {}
    for i in range(14):
        for name, o, off in (('beh+8D0', beh, 0x8D0), ('beh+880', beh, 0x880)):
            if not (0x10000 <= o < 0x7FFF0000):
                continue
            b = rd(o + off, 0x40)
            if not b:
                continue
            cur = b
            if name in prev and cur != prev[name]:
                diffs = []
                for k in range(0, 0x40):
                    if cur[k] != prev[name][k]:
                        diffs.append('+%02X:%02X>%02X' % (off + k, prev[name][k], cur[k]))
                if diffs:
                    pos = struct.unpack('<fff', rd(ent + 0x40, 12))
                    print('  t=%.1f %s CHANGED: %s pos=(%.1f,%.1f)' % (
                        i * 0.25, name, ' '.join(diffs[:12]), pos[0], pos[1]))
            prev[name] = cur
        time.sleep(0.25)
print('done')
