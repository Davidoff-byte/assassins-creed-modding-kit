#!/usr/bin/env python3
"""Dump fAC (entity+0xAC) graphics objects for a set of live entities and find
pointer values shared between them - grouping entities by shared appearance
resources (candidate 'same model' groups)."""
import ctypes
import struct
import sys
from collections import defaultdict

pid = int(sys.argv[1]) if len(sys.argv) > 1 else 17780

# (entity addr, fAC value, label) - from scan at ~14:44
ENTS = [
    (0x48F56B10, 0xFD686C30, 'keyed F000890C @(37.7,-106.7) ch18'),
    (0x47F2BE30, 0xFCA2F2B8, 'cluster ch29 cnt32 @(32.1,-136.9)'),
    (0x4690F940, 0xFCA2F148, 'cluster ch18 @(30.6,-137.3)'),
    (0x483816B0, 0xFC621AA0, 'cluster ch20 cnt23 @(27.7,-137.1)'),
    (0x46703F00, 0xFC6217C8, 'cluster ch18 @(33.5,-137.7)'),
    (0x47FD3250, 0xFCA2F0A0, 'cluster ch18 @(31.3,-138.1)'),
    (0x3AE6C300, 0xFCA29270, 'cluster ch20 @(30.8,-138.7)'),
    (0x41A2F540, 0xFC624B10, 'cluster ch17 @(32.5,-139.1)'),
    (0x46703CC0, 0xFC626A80, 'cluster ch17 @(33.4,-139.2)'),
    (0x48FE2F50, 0xFCA2DF00, 'cluster ch18 @(30.0,-139.3)'),
    (0x389B8A90, 0xFD6879D8, 'ch20 @(42.8,-113.3)'),
    (0x47354370, 0xFCA2E4F8, 'ch19 @(44.0,-112.8)'),
    (0x37BD0F40, 0xFCA243A0, 'ch20 @(47.0,-106.9)'),
    (0x3AEBFFA0, 0xFCA29E08, 'dockarea F0002754 @(56.0,-76.4)'),
    (0x47FC5380, 0xFCA2A5C8, 'dockarea F000276E @(54.8,-77.6)'),
    (0x37F7FA70, 0xFCA24060, 'PLAYER ch32'),
]

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)
if not h:
    raise SystemExit('cannot open pid')

def rd(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), buf, n, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None

dumps = {}
print('=== fAC object heads (0x100 bytes) ===')
for ent, fac, lbl in ENTS:
    d = rd(fac, 0x100)
    dumps[ent] = d
    print('-- ENT 0x%08X fAC 0x%08X  %s' % (ent, fac, lbl))
    if not d:
        print('   UNREADABLE')
        continue
    for i in range(0, min(len(d), 0x100), 16):
        row = d[i:i + 16]
        print('   +%03X %s' % (i, ' '.join('%02x' % b for b in row)))

val2ents = defaultdict(set)
for ent, d in dumps.items():
    if not d:
        continue
    for i in range(0, len(d) - 3, 4):
        v = struct.unpack_from('<I', d, i)[0]
        if 0x10000000 <= v <= 0x7FFFFFFF:
            val2ents[v].add(ent)

print('=== pointer values shared by >=3 entities ===')
for v, ents in sorted(val2ents.items()):
    if len(ents) >= 3:
        print('  0x%08X shared by %d: %s' % (v, len(ents), ' '.join('%08X' % e for e in sorted(ents))))
