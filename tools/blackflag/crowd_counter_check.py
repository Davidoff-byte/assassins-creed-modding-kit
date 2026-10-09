#!/usr/bin/env python3
"""READ-ONLY: sample ctl+0x26E0..0x2700 and ctl+0x28F0..0x2910 for player,
edwards and top moving NPCs; two passes 1.5s apart; mark changed dwords."""
import ctypes
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
player = 0
edwards = []
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
                        if ch == 32 and cnt == 34:
                            player = a
                        elif ch == 29 and cnt == 32:
                            edwards.append(a)
                        elif 16 <= ch <= 25 and cnt >= 16:
                            chars.append((a, ch, cnt))
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

# measure movers
p0 = {a: f3(a + 0x40) for a, ch, cnt in chars}
time.sleep(1.5)
scored = []
for a, ch, cnt in chars:
    p = f3(a + 0x40)
    q = p0.get(a)
    if p and q:
        scored.append((abs(p[0] - q[0]) + abs(p[1] - q[1]), a, ch, cnt))
scored.sort(reverse=True)
movers = [s for s in scored if s[0] > 0.4][:3]

targets = [('player', player)] + [('edw%d' % i, e) for i, e in enumerate(edwards[:2])]
targets += [('mover%d' % i, m[1]) for i, m in enumerate(movers)]

print('targets:', targets, flush=True)

def region(ctl):
    return rd(ctl + 0x26D8, 0x30) , rd(ctl + 0x28E8, 0x30)

state = {}
for tag, ent in targets:
    ctl = u32(ent + 0xE8)
    if not ctl:
        continue
    a1 = rd(ctl + 0x26D8, 0x30)
    b1 = rd(ctl + 0x28E8, 0x30)
    state[tag] = (ctl, a1, b1)
    if a1 and b1:
        print('%s ent=0x%08X ctl=0x%08X' % (tag, ent, ctl), flush=True)
        print('   +26D8: %s' % a1.hex().upper(), flush=True)
        print('   +28E8: %s' % b1.hex().upper(), flush=True)

print('--- 1.5s later ---', flush=True)
time.sleep(1.5)
for tag, ent in targets:
    if tag not in state:
        continue
    ctl, a0, b0 = state[tag]
    a1 = rd(ctl + 0x26D8, 0x30)
    b1 = rd(ctl + 0x28E8, 0x30)
    if not a1 or not b1:
        continue
    da = [i for i in range(len(a1)) if a1[i] != a0[i]]
    db = [i for i in range(len(b1)) if b1[i] != b0[i]]
    print('%s ctl=0x%08X changed26D8=%d changed28E8=%d' % (tag, ctl, len(da), len(db)), flush=True)
    if da:
        print('   26D8 now: %s' % a1.hex().upper(), flush=True)
    if db:
        print('   28E8 now: %s' % b1.hex().upper(), flush=True)
print('done', flush=True)
