#!/usr/bin/env python3
"""Map all references (u32 ids) to hood objects inside the assassin def,
and find every id in the two hood id-families."""
import struct

PATH = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'
d = open(PATH, 'rb').read()

IDS = {
    0x34014A76: '_Hood_Down_LOD0',
    0x34014B52: 'Hood_Down',
    0x34014B53: 'CHR_G_Male_Assassins_Hood_Down_LOD1',
    0x4B05F306: 'CHR_G_Male_Assassins_Hood_Up_LOD1',
    0x4B05F32A: '_Hood',
    0x4B05F316: '0x4B05F316(?)',
}

print('=== occurrences of known hood ids ===')
for vid, label in IDS.items():
    pat = struct.pack('<I', vid)
    j = d.find(pat)
    n = 0
    while j >= 0:
        ctx = d[max(0, j - 12): j + 16]
        print('  0x%08X %-38s @0x%06x  ctx: %s' % (vid, label, j, ctx.hex(' ')))
        n += 1
        j = d.find(pat, j + 1)
    if n == 0:
        print('  0x%08X %-38s  (no occurrences)' % (vid, label))

print()
print('=== all u32 ids in families 0x4B05F3xx / 0x34014xxx present ===')
seen = {}
for i in range(0, len(d) - 4):
    v = struct.unpack_from('<I', d, i)[0]
    if (v & 0xFFFFFF00) == 0x4B05F300 or (v & 0xFFFF0000) == 0x34010000:
        seen.setdefault(v, []).append(i)
for v in sorted(seen):
    locs = seen[v]
    print('  0x%08X  x%d  @ %s' % (v, len(locs), ', '.join('0x%06x' % x for x in locs[:6])))
