#!/usr/bin/env python3
"""Live-inspect an Edward body: entity fields, its controller (+0xE8), the
controller's vtable + anim-state fields, and the player's controller for
comparison (from the ActCtl log line)."""
import ctypes
import glob
import re
import struct
import sys

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


# --- find Edwards via the vt pattern ---
VT = struct.pack('<I', 0x01E4CE90)
hits = []
mbi_t = ctypes.c_ulong * 6  # not used; simple loop below uses VirtualQueryEx via ctypes


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong), ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong)]


mbi = MBI()
addr = 0x10000
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
                    hits.append(base + off + j)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

edwards = []
for a in hits:
    blob = rd(a, 0x100)
    if not blob or len(blob) < 0xF0:
        continue
    cnt, ch = struct.unpack_from('<HH', blob, 0x64)
    if ch == 29 and cnt == 32:
        edwards.append(a)

print('edwards:', ['0x%08X' % e for e in edwards])

for e in edwards[:2]:
    blob = rd(e, 0x100)
    pos = struct.unpack_from('<fff', blob, 0x40)
    c8 = struct.unpack_from('<I', blob, 0xC8)[0]
    e8 = struct.unpack_from('<I', blob, 0xE8)[0]
    print('--- edward 0x%08X pos=(%.1f,%.1f,%.1f) +0xC8=0x%08X +0xE8=0x%08X' % (e, *pos, c8, e8))
    if 0x10000 <= e8 < 0x7FFF0000:
        v = u32(e8)
        print('    ctl vt=0x%08X' % v)
        head = rd(e8, 0x40)
        if head:
            print('    ctl head:', ' '.join('%08X' % struct.unpack_from('<I', head, i)[0] for i in range(0, 0x40, 4)))
        anim = rd(e8 + 0x8D0, 0x30)
        if anim:
            print('    ctl+0x8D0..0x900:', ' '.join('%08X' % struct.unpack_from('<I', anim, i)[0] for i in range(0, 0x30, 4)))
        q = rd(e8 + 0x138, 0x10)
        if q:
            print('    ctl+0x138:', ' '.join('%08X' % struct.unpack_from('<I', q, i)[0] for i in range(0, 0x10, 4)))

# --- player ctl from the log ---
log = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.log"
lines = []
try:
    with open(log, 'r', errors='ignore') as f:
        lines = f.readlines()[-4000:]
except OSError:
    pass
pc = None
for ln in reversed(lines):
    m = re.search(r'ActCtl: player ctl=0x([0-9A-Fa-f]+) vt=0x([0-9A-Fa-f]+)', ln)
    if m:
        pc = int(m.group(1), 16)
        print('player ctl from log: 0x%08X vt=0x%08X' % (pc, int(m.group(2), 16)))
        break
if pc and 0x10000 <= pc < 0x7FFF0000:
    anim = rd(pc + 0x8D0, 0x30)
    if anim:
        print('    player ctl+0x8D0..0x900:', ' '.join('%08X' % struct.unpack_from('<I', anim, i)[0] for i in range(0, 0x30, 4)))
