#!/usr/bin/env python3
"""Trace the behavior->slots chain for each child of an Edward: for each child,
read +0x18 -> o1, o1+0xC -> sub, and dump sub+0x2F50..0x2F68 plus a head dump."""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
ENT = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x432D7810

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


base = u32(ENT + 0x60)
cnt = struct.unpack('<H', rd(ENT + 0x66, 2))[0]
print('entity 0x%08X children=%d base=0x%08X' % (ENT, cnt, base))
for i in range(min(cnt, 40)):
    c = u32(base + i * 4)
    if not (0x10000 <= c < 0x7FFF0000):
        continue
    vt = u32(c)
    o1 = u32(c + 0x18)
    sub = u32(o1 + 0xC) if 0x10000 <= o1 < 0x7FFF0000 else 0
    line = '  [%2d] 0x%08X vt=0x%08X +0x18=0x%08X' % (i, c, vt, o1)
    if 0x10000 <= sub < 0x7FFF0000:
        sl = rd(sub + 0x2F50, 0x18)
        if sl:
            vals = struct.unpack('<IIIIII', sl)
            line += ' sub=0x%08X slots=%s' % (sub, ['%08X' % v for v in vals])
    print(line)

# also: ent+0xC8 (the other controller) chain
c8 = u32(ENT + 0xC8)
print('ent+0xC8 = 0x%08X vt=0x%08X' % (c8, u32(c8) if c8 else 0))
if c8:
    o1 = u32(c8 + 0x18)
    print('   +0x18=0x%08X' % o1)
    if 0x10000 <= o1 < 0x7FFF0000:
        sub = u32(o1 + 0xC)
        print('   sub=0x%08X' % sub)
        if 0x10000 <= sub < 0x7FFF0000:
            sl = rd(sub + 0x2F50, 0x18)
            if sl:
                print('   slots=%s' % ['%08X' % v for v in struct.unpack('<IIIIII', sl)])
