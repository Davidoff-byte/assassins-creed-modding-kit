#!/usr/bin/env python3
"""Build mod11: combined A/B test on top of mod7.

  Channel 1 (CONTENT test): ship sailors -> CHR_U_EdwardKenwayStandard content.
      If Edward draws anywhere in the swap system, it should be on sailors.
  Channel 2 (TARGET test): Spanish civ trio -> CHR_U_Duncan_Walpole content.
      The look that DID render on crew before; tests whether the civ defs
      accept any swap at all (mod9/mod10 went invisible with Edward content).

Recipe identical to mod5/7/9/10: append source def as a private EOF copy per
target; patch the source def's 2 self-identity hash occurrences to the target
hash; repoint the target TOC records (OT offset/size + name-rec size)."""
import struct
import shutil
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

SRC = r'D:\bf4_mod\DataPC_extra_chr_mod7.forge'
DST = r'D:\bf4_mod\DataPC_extra_chr_mod11.forge'

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


edw, edw_d = load('CHR_U_EdwardKenwayStandard')
edw_occ = occ(edw_d, edw['hash32'])
print('EdwardStandard: hash=0x%08X size=%d occ=%s' % (edw['hash32'], len(edw_d), [hex(o) for o in edw_occ]))

dun, dun_d = load('CHR_U_Duncan_Walpole')
dun_occ = occ(dun_d, dun['hash32'])
print('Duncan:         hash=0x%08X size=%d occ=%s' % (dun['hash32'], len(dun_d), [hex(o) for o in dun_occ]))

plan = []
for t, (src, sdata, ssz, socc) in {
    # sanity channel: Duncan content on the ship crew (this rendered back on 10/8)
    'CHR_G_M_Pirate_Jackdaw_Sailors': (dun, dun_d, len(dun_d), dun_occ),
    # content channel: Edward content on the generic sailors (dock NPCs)
    'CHR_C_M_Generic_Sailors': (edw, edw_d, len(edw_d), edw_occ),
    # target channel: does the civ trio accept ANY swap?
    'CHR_C_M_Spanish_Medium': (dun, dun_d, len(dun_d), dun_occ),
    'CHR_C_M_Spanish_Poors': (dun, dun_d, len(dun_d), dun_occ),
    'CHR_C_M_Spanish_Rich': (dun, dun_d, len(dun_d), dun_occ),
}.items():
    plan.append((t, src, sdata, ssz, socc))

print('copying mod7 -> mod11 ...')
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
    diffs = [i for i in range(0, min(len(d), len(sdata)), 4) if d[i:i+4] != sdata[i:i+4]]
    print('VERIFY %-34s off=0x%x size=%d diffs=%s' % (name, o, s, [hex(i) for i in diffs[:8]]))
