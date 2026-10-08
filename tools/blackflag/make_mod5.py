#!/usr/bin/env python3
"""Build mod5: like mod4 (crew redirected to private assassin copy at EOF),
but patch the copied def's two self-identity hashes so it registers as the
crew's asset (0xE78D9C36) instead of the assassin's (0x815F7672)."""
import struct
import shutil
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SRC = r'D:\bf4_mod\DataPC_extra_chr_mod4.forge'
DST = r'D:\bf4_mod\DataPC_extra_chr_mod5.forge'
ASSASSIN = r'D:\bf4_extract\extra_chr\CHR_G_M_Assassin'

COPY_OFF = 0x5B290000          # where mod4 appended the private copy
HASH_ASSASSIN = 0x815F7672     # old identity (2 occurrences in the def)
HASH_CREW = 0xE78D9C36         # new identity (crew)

print('copying mod4 -> mod5 ...')
shutil.copyfile(SRC, DST)

# locate the occurrences of the assassin hash inside the ORIGINAL def bytes
data = open(ASSASSIN, 'rb').read()
pat = struct.pack('<I', HASH_ASSASSIN)
offs = []
j = data.find(pat)
while j >= 0:
    offs.append(j)
    j = data.find(pat, j + 1)
print('hash 0x%08X occurrences inside def: %s' % (HASH_ASSASSIN, [hex(o) for o in offs]))
if not offs:
    sys.exit('no occurrences found!')

newpat = struct.pack('<I', HASH_CREW)
with open(DST, 'r+b') as f:
    for o in offs:
        f.seek(COPY_OFF + o)
        f.write(newpat)
        print('patched copy+0x%x -> 0x%08X' % (o, HASH_CREW))

# verify: copy bytes vs def bytes, expect diffs exactly at offs
with open(DST, 'rb') as f:
    f.seek(COPY_OFF)
    blob = f.read(len(data))
diff = [k for k in range(len(data)) if blob[k] != data[k]]
print('diff count vs original def: %d (expected %d)' % (len(diff), len(offs)))
for k in diff[:10]:
    print('  at copy+0x%x: %02x -> %02x' % (k, data[k], blob[k]))
print('verification %s' % ('OK' if len(diff) == len(offs) else 'PROBLEM'))
