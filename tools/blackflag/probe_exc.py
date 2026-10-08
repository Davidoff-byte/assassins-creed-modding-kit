#!/usr/bin/env python3
"""Probe minidump for the access-violation record and candidate fault addresses."""
import struct
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

path = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\Administrator\AppData\Local\CrashDumps\AC4BFSP.exe.18848.dmp")
d = open(path, 'rb').read()
print('dump size', len(d))
needle = struct.pack('<I', 0xC0000005)
idx = d.find(needle)
print('first 0xC0000005 at', idx)
for k in range(3):
    if idx < 0:
        break
    chunk = d[idx: idx + 56]
    print('occurrence %d at 0x%x:' % (k, idx))
    for row in range(0, 56, 8):
        print('   +%02d: %s' % (row, chunk[row:row + 8].hex(' ')))
    idx = d.find(needle, idx + 1)
for target in (0x621E23, 0xA21E23, 0x64A813D4):
    pat8 = struct.pack('<Q', target)
    pat4 = struct.pack('<I', target)
    j8 = d.find(pat8)
    j4 = d.find(pat4)
    print('0x%X: u64@%s u32@%s' % (target, j8, j4))
