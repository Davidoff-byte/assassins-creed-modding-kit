#!/usr/bin/env python3
"""Inspect the assassin def's internal records, especially hood parts."""
import re

PATH = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'
d = open(PATH, 'rb').read()

# All printable strings >= 4 chars with positions
strs = [(m.start(), m.group().decode('latin1')) for m in re.finditer(rb'[ -~]{4,}', d)]
print('total strings:', len(strs))

KW = re.compile(r'hood|LOD|body|head|visual|assassin|mesh|skin|cloth|robe|skeleton|bone|hand|foot|mat_|material', re.I)
print('=== interesting strings ===')
for off, s in strs:
    if KW.search(s):
        # context after the string: up to 24 bytes
        a = off + len(s)
        ctx = d[a:a + 24]
        print('  0x%06x  %-52s | after: %s' % (off, s[:52], ctx.hex(' ')))
