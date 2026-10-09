#!/usr/bin/env python3
"""READ-ONLY: find behavior objects (objects whose +4 field == entity pointer) for
the player and both live Edwards; dump anim control fields and request slots.

No writes at all.
"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
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


# --- find player + edwards ---
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
                        if ch == 32 and cnt == 34:
                            player = a
                        if ch == 29 and cnt == 32:
                            chars.append(a)
                    j = b.find(VT, j + 4)
            off += n
    addr = base + size

edwards = chars[:4]
print('player=0x%08X edwards=%s' % (player, ['0x%08X' % e for e in edwards]))

needles = {'player': player}
for i, e in enumerate(edwards):
    needles['edw%d' % i] = e

# --- scan heap for needles: find objects with +4 == entity ---
hits = {k: [] for k in needles}
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
                for name, val in needles.items():
                    pat = struct.pack('<I', val)
                    j = b.find(pat)
                    while j >= 0 and len(hits[name]) < 200:
                        hits[name].append(base + off + j)
                        j = b.find(pat, j + 4)
            off += n
    addr = base + size

for name, addrs in needles.items():
    ent = addrs
    print('== needle %s ent=0x%08X : %d refs' % (name, ent, len(hits[name])))
    # objects with +4 == ent: hit at P means u32(P)==ent; object S=P-4
    found = 0
    for p in hits[name]:
        s = p - 4
        vt = u32(s)
        # plausible vt: image or heap code-ish range
        if (0x00400000 <= vt <= 0x05400000) or (0x46000000 <= vt <= 0x80000000):
            f8 = u32(s + 8)
            fc = u32(s + 0xC)
            print('   G? S=0x%08X vt=0x%08X +8=0x%08X +C=0x%08X' % (s, vt, f8, fc))
            found += 1
            if found >= 8:
                break
    if found == 0:
        print('   (no +4-pattern object found; raw refs: %s)' % (
            ', '.join('0x%08X' % p for p in hits[name][:10])))

# --- dump ctls ---
def dump_ctl(label, ent):
    ctl = u32(ent + 0xE8)
    print('-- %s ent=0x%08X ctl(ent+E8)=0x%08X' % (label, ent, ctl))
    if not ctl:
        return
    print('   ctl+4=0x%08X ctl+8=0x%08X ctl+C=0x%08X ctl+18=0x%08X' % (
        u32(ctl + 4), u32(ctl + 8), u32(ctl + 0xC), u32(ctl + 0x18)))
    b = rd(ctl + 0x8D0, 0x20)
    if b:
        print('   ctl+8D0: %s' % b.hex().upper())
    sl = rd(ctl + 0x2F50, 0x18)
    if sl:
        print('   ctl+2F50 slots: %s' % ','.join('%08X' % v for v in struct.unpack('<6I', sl)))

dump_ctl('player', player)
for i, e in enumerate(edwards):
    dump_ctl('edw%d' % i, e)

# also dump the player's known probe object G=0x48161620 if present
G = 0x48161620
if u32(G + 4) == player:
    print('-- G=0x48161620 vt=0x%08X +4=0x%08X +8=0x%08X +C=0x%08X' % (
        u32(G), u32(G + 4), u32(G + 8), u32(G + 0xC)))
else:
    print('-- G=0x48161620 +4=0x%08X (not player entity now)' % u32(G + 4))
print('done')
