#!/usr/bin/env python3
"""Build mod15: THE KEEPER - pristine world + ONE swap:
  CHR_C_F_Rich <- CHR_U_EdwardKenwayStandard content (id-patched to the target).
Everything else 100% original (no Duncan probes, no soldier/slave swaps).

Evidence chain: the walking keyed NPC was Edward-look in mod12+mod13 (F_Rich
and Soldier were the only EdwardStd-content defs; F_Poor=Duncan excluded by
look; Slaves excluded by mod13). User: he "walked like a woman" -> female anim
set -> CHR_C_F_Rich. mod14 (F_Rich->Duncan) made his Edward body disappear
from the whole world (robed or choked). This keeper restores Edward on the
single candidate; the world is otherwise pristine.

Decode: he returns as Edward  -> F_Rich confirmed, THIS is the final build.
        he appears as a normal soldier instead -> he was the soldier def.
"""
import struct
import shutil
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

SRC = r'D:\bf4_mod\DataPC_extra_chr.forge'          # pristine
DST = r'D:\bf4_mod\DataPC_extra_chr_mod15.forge'

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


def load(n):
    e = find(n)
    o, sz = ft.data_range(e, D6)
    return e, bytes(mm[o:o + sz])


print("== pristine sanity ==")
for nm, expsz in [('CHR_C_F_Rich', 504891), ('CHR_U_EdwardKenwayStandard', 388137)]:
    e = find(nm)
    o, sz = ft.data_range(e, D6)
    print('  %-34s size=%-8d (expect %-8d) %s' % (nm, sz, expsz, 'OK' if sz == expsz else '??'))

edw, edw_d = load('CHR_U_EdwardKenwayStandard')
edw_occ = occ(edw_d, edw['hash32'])
print('EdwardStd: hash=0x%08X size=%d occ=%s' % (edw['hash32'], len(edw_d), [hex(o) for o in edw_occ]))

plan = [
    ('CHR_C_F_Rich', edw, edw_d, len(edw_d), edw_occ),
]

print('copying pristine -> mod15 ...')
shutil.copyfile(SRC, DST)

with open(DST, 'r+b') as f:
    for name, src, sdata, ssz, socc in plan:
        t = find(name)
        f.seek(0, 2)
        eof = f.tell()
        f.write(sdata)
        for o in socc:
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
        print('  %-34s <- %-28s copy@0x%x ids->0x%08X' % (name, src['name'], eof, t['hash32']))

print('wrote', DST)

info2 = ft.parse_forge(DST)
for name, src, sdata, ssz, socc in plan:
    e = [x for x in info2['entries'] if x['name'] == name][0]
    o, s = ft.data_range(e, info2['D6'])
    d = bytes(info2['mm'][o:o + s])
    diffs = [i for i in range(0, min(len(d), len(sdata)), 4) if d[i:i + 4] != sdata[i:i + 4]]
    print('VERIFY %-34s off=0x%x size=%d diffs=%s' % (name, o, s, [hex(i) for i in diffs[:8]]))
