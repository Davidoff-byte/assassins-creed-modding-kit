#!/usr/bin/env python3
"""Map class CRC32 ids -> names using the PS3 pubnames list."""
import re
import zlib

PUB = r"C:\Users\Administrator\Documents\Default Project\bf-coop\logs\ps3_pubnames.txt"

targets = {
    0x6328D910, 0x06A717F0, 0xD9BE9799, 0x620D4153, 0x2DBA1DC4, 0x125ECE99,
    0x32191DBC, 0xC731F93D, 0xE32A8929, 0x6CFF2E10, 0x4BC5CC40, 0x77AB19B4,
    0xDADBBB2D, 0xFA21FFCF, 0xD0762DAD, 0x4E198B7F, 0x5B7B0E0A, 0xC5F51B5E,
    0xA2FC6E1B, 0x57EEEEC7, 0x872A9D97,
}

pat = re.compile(r'^0x[0-9a-fA-F]+\s+(\S+)')
classes = set()
with open(PUB, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        m = pat.match(line)
        if not m:
            continue
        name = m.group(1)
        parts = name.split('::')
        if len(parts) >= 2 and parts[0] == 'scimitar':
            cls = parts[1]
        elif len(parts) == 1 and parts[0].startswith(('CSrv', 'ISrv', 'Srv')):
            cls = parts[0]
        else:
            continue
        cls = re.sub(r'[<(].*$', '', cls)
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', cls):
            continue
        classes.add(cls)

byid = {}
for c in sorted(classes):
    byid[zlib.crc32(c.encode()) & 0xFFFFFFFF] = c

print('unique classes seen:', len(classes))
print('--- target ids ---')
for t in sorted(targets):
    print('0x%08x -> %s' % (t, byid.get(t, '?')))

srv = sorted((h, c) for h, c in byid.items() if c.startswith('CSrv'))
print('--- CSrv classes: %d (showing all) ---' % len(srv))
for h, c in srv:
    print('0x%08x %s' % (h, c))
