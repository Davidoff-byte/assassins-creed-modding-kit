#!/usr/bin/env python3
"""Inspect AhTabai def identity record contexts."""
import struct

PATH = r'D:\bf4_extract\extra_chr\CHR_U_AhTabai'
d = open(PATH, 'rb').read()
H = 0x2EA6444C
print('size', len(d))

for off in (0x3E1, 0x17C0):
    print('--- @0x%x ---' % off)
    print(d[max(0, off - 32): off + 32].hex(' '))

# find name string occurrences
nb = b'CHR_U_AhTabai'
j = d.find(nb)
while j >= 0:
    print('name string @0x%x  ctx: %s' % (j, d[j:j + 48].hex(' ')))
    j = d.find(nb, j + 1)
