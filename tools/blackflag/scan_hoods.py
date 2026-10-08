#!/usr/bin/env python3
"""Scan character defs across all extraction folders for Hood_Up / Hood_Down strings."""
import os

ROOTS = [r'D:\bf4_extract']
needles = [b'Hood_Up', b'Hood_Down', b'_Hood']
hits = {}
for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.startswith('CHR_'):
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) < 50 * 1024:
                    continue
                d = open(p, 'rb').read()
            except Exception:
                continue
            found = [n.decode() for n in needles if n in d]
            if found:
                rel = os.path.relpath(p, root)
                hits[rel] = found

print('files containing hood markers: %d' % len(hits))
for rel in sorted(hits):
    print('  %-72s %s' % (rel, ','.join(hits[rel])))
