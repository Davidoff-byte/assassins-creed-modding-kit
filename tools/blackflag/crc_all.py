#!/usr/bin/env python3
"""Dump every class name (all :: components) from pubnames with its crc32 id."""
import re
import zlib

PUB = r"C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ps3_pubnames.txt"
OUT = r"C:\Users\Administrator\Documents\Default Project\bf-coop\logs\crc_all.txt"

pat = re.compile(r'^0x[0-9a-fA-F]+\s+(\S+)')
names = set()
with open(PUB, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        m = pat.match(line)
        if not m:
            continue
        for p in m.group(1).split('::'):
            p = re.sub(r'[<(].*$', '', p)
            if p and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', p):
                names.add(p)

ids = {}
for n in sorted(names):
    ids.setdefault(zlib.crc32(n.encode()) & 0xFFFFFFFF, n)

with open(OUT, 'w', encoding='utf-8') as g:
    for h, n in sorted(ids.items()):
        g.write('%08x\t%s\n' % (h, n))

print('names:', len(names), 'unique ids:', len(ids), '->', OUT)
