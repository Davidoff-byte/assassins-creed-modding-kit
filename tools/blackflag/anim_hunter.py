#!/usr/bin/env python3
"""Background hunter: wait until the game world is actually running (NPCs
moving), then capture where the crowd's animation state lives: byte-level diffs
on the controller chain of walking NPCs. Loops until N captures or timeout."""
import ctypes
import math
import struct
import sys
import time

pid = int(sys.argv[1])
WANT = 3
DEADLINE = time.time() + 3600

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


def find_chars():
    mbi = MBI()
    addr = 0x10000
    chars = []
    while addr < 0x7FFF0000 and len(chars) < 400:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)):
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
    return chars


captures = 0
while time.time() < DEADLINE and captures < WANT:
    chars = find_chars()
    time.sleep(1.0)
    movers = []
    for c in chars:
        p = rd(c[0] + 0x40, 12)
        if not p:
            continue
        pos = struct.unpack('<fff', p)
        if math.hypot(pos[0] - c[3][0], pos[1] - c[3][1]) > 0.3:
            movers.append((c[0], c[1], pos))
    if not movers:
        time.sleep(15)
        continue
    print('LIVE! movers=%d - capturing...' % len(movers))
    sys.stdout.flush()
    for ent, ch, pos in movers[:3]:
        beh = u32(ent + 0xE8)
        if not (0x10000 <= beh < 0x7FFF0000):
            continue
        print('== mover ent=0x%08X ch=%d beh=0x%08X vt=0x%08X pos=(%.1f,%.1f)' % (
            ent, ch, beh, u32(beh), pos[0], pos[1]))
        prev = {}
        for i in range(40):
            for off in (0x8D0, 0x880, 0x2F40):
                b = rd(beh + off, 0x40)
                if not b:
                    continue
                key = off
                if key in prev and b != prev[key]:
                    diffs = []
                    for k in range(0x40):
                        if b[k] != prev[key][k]:
                            diffs.append('+%03X:%02X>%02X' % (off + k, prev[key][k], b[k]))
                    p2 = struct.unpack('<fff', rd(ent + 0x40, 12))
                    print('   t=%.1f +%03X CHANGED: %s pos=(%.1f,%.1f)' % (
                        i * 0.2, off, ' '.join(diffs[:14]), p2[0], p2[1]))
                prev[key] = b
            time.sleep(0.2)
        captures += 1
        if captures >= WANT:
            break
print('hunter done, captures=%d' % captures)
