#!/usr/bin/env python3
"""Look for self-identification (name string / name-hash) inside character def files."""
import struct

A = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'
C = r'D:\bf4_extract\extra_chr\CHR_G_M_Pirate_Jackdaw_Sailors'

a = open(A, 'rb').read()
c = open(C, 'rb').read()

HASH_A = 0x815F7672          # CHR_G_M_Assassin       (TOC hash32)
HASH_C = 0xE78D9C36          # CHR_G_M_Pirate_Jackdaw_Sailors (TOC hash32)


def scan(d, name, h32, label):
    print('==== %s (%d bytes) hash32=0x%08X ====' % (label, len(d), h32))
    nb = name.encode()
    j = d.find(nb)
    while j >= 0:
        ctx = d[max(0, j - 16): j + len(nb) + 16]
        print('  name "%s" at 0x%x  ctx: %s' % (name, j, ctx.hex(' ')))
        j = d.find(nb, j + 1)
    pat = struct.pack('<I', h32)
    j = d.find(pat)
    cnt = 0
    while j >= 0 and cnt < 10:
        ctx = d[max(0, j - 16): j + 20]
        print('  hash32 at 0x%x  ctx: %s' % (j, ctx.hex(' ')))
        cnt += 1
        j = d.find(pat, j + 1)
    if cnt == 0:
        print('  hash32 NOT found in bytes')
    # also 64-bit self hash candidate (name hash64 unknown) - print first 32 bytes
    print('  head: %s' % d[:32].hex(' '))


scan(a, 'CHR_G_M_Assassin', HASH_A, 'ASSASSIN')
scan(c, 'CHR_G_M_Pirate_Jackdaw_Sailors', HASH_C, 'CREW')
