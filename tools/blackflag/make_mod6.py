#!/usr/bin/env python3
"""Build mod6: crew -> AhTabai (hooded mentor), sailors -> Duncan Walpole (hooded robes).
Both as private EOF copies with self-identity hashes patched to the target entry hash."""
import struct
import shutil
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

SRC = r'D:\bf4_mod\DataPC_extra_chr_mod5.forge'
DST = r'D:\bf4_mod\DataPC_extra_chr_mod6.forge'

info = ft.parse_forge(SRC)
D6 = info['D6']
mm = info['mm']


def find(n):
    for e in info['entries']:
        if e['name'] == n:
            return e
    raise SystemExit('entry not found: %s' % n)


def occ(dat, h):
    pat = struct.pack('<I', h)
    out = []
    j = dat.find(pat)
    while j >= 0:
        out.append(j)
        j = dat.find(pat, j + 1)
    return out


pairs = [
    ('CHR_U_AhTabai', 'CHR_G_M_Pirate_Jackdaw_Sailors'),
    ('CHR_U_Duncan_Walpole', 'CHR_C_M_Generic_Sailors'),
]

plan = []
for srcname, dstname in pairs:
    s = find(srcname)
    t = find(dstname)
    so, ssz = ft.data_range(s, D6)
    data = bytes(mm[so:so + ssz])
    occs = occ(data, s['hash32'])
    matches = [o for o in occs if data[o + 4:o + 8] == b'\x07\x00\x00\x00']
    print('%s: toc hash32=0x%08X size=%d  occurrences=%s  identity-like=%s'
          % (srcname, s['hash32'], ssz, [hex(o) for o in occs], [hex(o) for o in matches]))
    plan.append(dict(src=s, tgt=t, data=data, occ=matches))

print('copying mod5 -> mod6 ...')
shutil.copyfile(SRC, DST)

with open(DST, 'r+b') as f:
    for p in plan:
        f.seek(0, 2)
        eof = f.tell()
        f.write(p['data'])
        # patch identity occurrences -> target hash
        for o in p['occ']:
            f.seek(eof + o)
            f.write(struct.pack('<I', p['tgt']['hash32']))
        # redirect target entry
        t = p['tgt']
        ot = bytearray(t['ot_raw'])
        struct.pack_into('<I', ot, 0, eof)
        struct.pack_into('<I', ot, 16, len(p['data']))
        f.seek(t['ot_pos'])
        f.write(bytes(ot))
        nr = bytearray(t['name_rec_raw'])
        struct.pack_into('<I', nr, 0, len(p['data']))
        f.seek(t['name_rec_pos'])
        f.write(bytes(nr))
        print('  %s -> copy@0x%x size=%d (identity patches: %d)'
              % (t['name'], eof, len(p['data']), len(p['occ'])))

print('wrote', DST)
