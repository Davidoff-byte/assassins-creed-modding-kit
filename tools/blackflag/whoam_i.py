#!/usr/bin/env python3
"""Targeted forensic read: identify probe target object 0x48161620 and chains."""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
target = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x48161620
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

print('target 0x%08X:' % target)
blob = rd(target, 0x80)
if blob:
    for off in range(0, 0x80, 16):
        print('  +%03X: %s' % (off, blob[off:off+16].hex().upper()))
    print('  u32[0] (class id?) = 0x%08X' % struct.unpack_from('<I', blob, 0)[0])
    print('  u32[4] = 0x%08X' % struct.unpack_from('<I', blob, 4)[0])
else:
    print('  UNREADABLE')

# player chain
player_ent = 0x44E3FE10
ctl = u32(player_ent + 0xE8)
o1 = u32(ctl + 0x18) if ctl else 0
r = u32(o1 + 0xC) if o1 else 0
print('player ent=0x%08X ctl=0x%08X [ctl+18]=0x%08X [[ctl+18]+C]=0x%08X  == target: %s'
      % (player_ent, ctl, o1, r, r == target))
if r:
    sl = rd(r + 0x2F50, 24)
    if sl:
        print('  player slots: %s' % ','.join('%08X' % v for v in struct.unpack('<6I', sl)))

# edwards
for ent in (0x39366410, 0x45D9DFB0):
    c2 = u32(ent + 0xE8)
    o2 = u32(c2 + 0x18) if c2 else 0
    r2 = u32(o2 + 0xC) if o2 else 0
    print('edward ent=0x%08X ctl=0x%08X [ctl+18]=0x%08X [[ctl+18]+C]=0x%08X  == target: %s'
          % (ent, c2, o2, r2, r2 == target))
    if r2:
        sl = rd(r2 + 0x2F50, 24)
        if sl:
            print('  edward slots: %s' % ','.join('%08X' % v for v in struct.unpack('<6I', sl)))

# also: does target appear in first 0x220 of player ent/ctl?
for base, label in ((player_ent, 'player ent'), (ctl, 'player ctl'), (o1, 'player o1'), (r, 'player req')):
    found = []
    mem = rd(base, 0x220)
    if mem:
        packed = struct.pack('<I', target)
        j = mem.find(packed)
        while j >= 0:
            found.append(j)
            j = mem.find(packed, j + 4)
    print('%s 0x%08X: target ptr at offsets %s' % (label, base, ['+0x%X' % f for f in found] or 'none'))
print('done')
