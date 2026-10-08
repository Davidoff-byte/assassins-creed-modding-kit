#!/usr/bin/env python3
"""Dump hood-selector regions of the assassin def + hood info of alternative defs."""
import re
import struct

A = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'
d = open(A, 'rb').read()

IDS = {
    0x34014A76: 'Hood_Down_LOD0',
    0x34014B52: 'Hood_Down',
    0x34014B53: 'Hood_Down_LOD1',
    0x4B05F306: 'Hood_Up_LOD1',
    0x4B05F316: 'F316',
    0x4B05F32A: '_Hood',
    0x4B05F337: 'F337',
    0x815F766B: 'VisualBody',
    0x815F7672: 'MASTER',
}


def dump(off, ln, label):
    print('--- %s (0x%x..0x%x) ---' % (label, off, off + ln))
    for row in range(off, off + ln, 16):
        chunk = d[row:row + 16]
        ann = []
        for k in range(0, 16, 4):
            v = struct.unpack_from('<I', chunk + b'\x00' * (4 - len(chunk[k:]))) [0] if len(chunk[k:]) >= 4 else None
            if v in IDS:
                ann.append('+%d=%s' % (k, IDS[v]))
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print('  0x%06x  %-47s  %s  %s' % (row, chunk.hex(' '), asc, ' '.join(ann)))


dump(0x10020, 0x150, '_Hood record + Hood_Down ref @0x1009A')
dump(0x6A880, 0x1C0, 'Hood_Down record + F316 ref')
dump(0x9150, 0x100, 'VisualBody record + F337 ref')

print()
print('==== AH TABAI hood context ====')
t = open(r'D:\bf4_extract\extra_chr\CHR_U_AhTabai', 'rb').read()
for m in re.finditer(rb'[ -~]{4,}', t):
    s = m.group().decode('latin1')
    if 'hood' in s.lower() or 'Hood' in s:
        a = m.start()
        print('  0x%06x %-50s ctx: %s' % (a, s[:50], t[a + len(s):a + len(s) + 24].hex(' ')))

print()
print('==== EdwardKenwayStandard hood context ====')
t = open(r'D:\bf4_extract\extra_chr\CHR_U_EdwardKenwayStandard', 'rb').read()
for m in re.finditer(rb'[ -~]{4,}', t):
    s = m.group().decode('latin1')
    if 'hood' in s.lower():
        a = m.start()
        print('  0x%06x %-50s ctx: %s' % (a, s[:50], t[a + len(s):a + len(s) + 24].hex(' ')))
