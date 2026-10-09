#!/usr/bin/env python3
"""Build mod9: Havana dock/street folk defs (Spanish civ trio) -> private copies
of CHR_P_EdwardKenway_Walpole (Edward in the Walpole disguise robes, id-patched).
So the keyed dock characters (and their civ-family neighbours) render as Edward.
Built on top of mod7 (crew+sailors already redirected)."""
import struct
import shutil
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

SRC = r'D:\bf4_mod\DataPC_extra_chr_mod7.forge'
DST = r'D:\bf4_mod\DataPC_extra_chr_mod9.forge'

info = ft.parse_forge(SRC)
D6 = info['D6']
mm = info['mm']


def find(n):
    for e in info['entries']:
        if e['name'] == n:
            return e
    raise SystemExit('not found: %s' % n)


def occ(dat, h):
    pat = struct.pack('<I', h)
    out = []
    j = dat.find(pat)
    while j >= 0:
        out.append(j)
        j = dat.find(pat, j + 1)
    return out


src = find('CHR_P_EdwardKenway_Walpole')
so, ssz = ft.data_range(src, D6)
data = bytes(mm[so:so + ssz])
occs = occ(data, src['hash32'])
print('Edward_Walpole: toc hash32=0x%08X size=%d occurrences=%s' % (src['hash32'], ssz, [hex(o) for o in occs]))

targets = [
    'CHR_C_M_Spanish_Medium',
    'CHR_C_M_Spanish_Poors',
    'CHR_C_M_Spanish_Rich',
]

print('copying mod7 -> mod9 ...')
shutil.copyfile(SRC, DST)

with open(DST, 'r+b') as f:
    for name in targets:
        t = find(name)
        f.seek(0, 2)
        eof = f.tell()
        f.write(data)
        for o in occs:
            f.seek(eof + o)
            f.write(struct.pack('<I', t['hash32']))
        ot = bytearray(t['ot_raw'])
        struct.pack_into('<I', ot, 0, eof)
        struct.pack_into('<I', ot, 16, ssz)
        f.seek(t['ot_pos'])
        f.write(bytes(ot))
        nr = bytearray(t['name_rec_raw'])
        struct.pack_into('<I', nr, 0, ssz)
        f.seek(t['name_rec_pos'])
        f.write(bytes(nr))
        print('  %s -> copy@0x%x ids->0x%08X' % (name, eof, t['hash32']))

print('wrote', DST)

info2 = ft.parse_forge(DST)
for name in targets:
    e = [x for x in info2['entries'] if x['name'] == name][0]
    o, s = ft.data_range(e, info2['D6'])
    print('VERIFY %-28s off=0x%x size=%d head=%s' % (name, o, s, info2['mm'][o:o + 8].hex(' ')))
