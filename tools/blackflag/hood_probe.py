#!/usr/bin/env python3
"""Probe: bytes at the candidate hood-mesh offsets + catalog of the 68 95 5d 41 marker."""
import struct

PATH = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'
d = open(PATH, 'rb').read()
print('file size 0x%x' % len(d))

for off in (0x0509ED, 0x0905ED, 0x2009E5, 0x0920E5):
    if off < len(d):
        print('bytes at 0x%06x: %s' % (off, d[off:off + 32].hex(' ')))

pat = bytes.fromhex('68955d41')
j = d.find(pat)
n = 0
print()
print('=== occurrences of 68 95 5d 41 ===')
while j >= 0:
    n += 1
    ctx = d[max(0, j - 40): j + 24]
    print('  @0x%06x  before: %s | after: %s' % (j, ctx[:40].hex(' '), ctx[40:].hex(' ')))
    j = d.find(pat, j + 1)
print('total:', n)
