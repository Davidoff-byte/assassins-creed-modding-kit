#!/usr/bin/env python3
"""Patch AhTabai copy identity ids in mod6 + verify everything."""
import struct
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

P = r'D:\bf4_mod\DataPC_extra_chr_mod6.forge'
AH_COPY = 0x5B35BE9F
AH_HASH_OFFS = (0x3E1, 0x17C0)
CREW_HASH = 0xE78D9C36

with open(P, 'r+b') as f:
    for o in AH_HASH_OFFS:
        f.seek(AH_COPY + o)
        f.write(struct.pack('<I', CREW_HASH))
        print('patched AkTabai copy+0x%x -> 0x%08X' % (o, CREW_HASH))
    # verify all identity spots
    checks = [
        (AH_COPY + 0x3E1, CREW_HASH, 'AhTabai hdr id'),
        (AH_COPY + 0x17C0, CREW_HASH, 'AhTabai name id'),
        (0x5BCC7B5B + 0x261, 0x8FB6DABC, 'Duncan hdr id'),
        (0x5BCC7B5B + 0x100B, 0x8FB6DABC, 'Duncan name id'),
    ]
    for off, want, label in checks:
        f.seek(off)
        got = struct.unpack('<I', f.read(4))[0]
        print('%-18s at 0x%x = 0x%08X  %s' % (label, off, got, 'OK' if got == want else 'MISMATCH'))

info = ft.parse_forge(P)
D6 = info['D6']
for name in ('CHR_G_M_Pirate_Jackdaw_Sailors', 'CHR_C_M_Generic_Sailors'):
    e = [x for x in info['entries'] if x['name'] == name][0]
    o, s = ft.data_range(e, D6)
    head = info['mm'][o:o + 8].hex(' ')
    print('%-32s off=0x%x size=%d head=%s' % (name, o, s, head))
print('file size:', __import__('os').path.getsize(P))
