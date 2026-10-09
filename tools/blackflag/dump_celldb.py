#!/usr/bin/env python3
"""Dump the Cell01364_DataBlock key-list structure."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
c = read_container(os.path.join(W, "cell01364.bin"))
res = list(walk_files(c["files"]))
first = res[0]
o, tid, name, header, payload = first
print("resource:", name, "type: 0x%08X" % tid, "len:", len(payload))
print("header:", header.hex(" "))

start = 0x13
# dump region around start
region = payload[start - 8:start + 0x120]
print("--- dump from +0x%X ---" % (start - 8))
for i in range(0, len(region), 16):
    chunk = region[i:i + 16]
    hexs = chunk.hex(" ")
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"   +0x{start-8+i:04X}  {hexs:<48} {text}")

# parse stride-10 entries: u32 key at start+10*i
print("--- stride-10 parse ---")
for i in range(16):
    off = start + 10 * i
    if off + 10 > len(payload):
        break
    k = struct.unpack_from("<I", payload, off)[0]
    a = struct.unpack_from("<H", payload, off + 4)[0]
    b = struct.unpack_from("<H", payload, off + 6)[0]
    c2 = struct.unpack_from("<H", payload, off + 8)[0]
    print(f"   [{i:2d}] key=0x{k:08X} w4=0x{a:04X} {b} {c2}")
