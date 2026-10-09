#!/usr/bin/env python3
"""Dump the objects referenced by character f50 fields and search them for
known def hash32s, to test whether f50 targets are per-def binding objects
(shared by all entities of a def) and if so, reveal which def each belongs to.
Also scans for CHR_ ascii strings and prints the raw head of each object.

Usage: python dump_f50.py [pid]
"""
import ctypes
import re
import struct
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 17780

# f50 cluster values seen earlier (docks, town, player)
TARGETS = [0x5F8A2264, 0x5F9A227C, 0x5FAA227C, 0x5F8A2064, 0x5F9A207C, 0x5FDA027C]

FORGES = [r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\DataPC_extra_chr.forge"]

h2n = {}
for fg in FORGES:
    try:
        info = ft.parse_forge(fg)
    except Exception as e:
        print('forge parse fail: %s (%s)' % (fg, e))
        continue
    named = 0
    for e in info['entries']:
        nm = e.get('name')
        h = e.get('hash32')
        if nm and h:
            h2n[h] = nm
            named += 1
    print('%-70s entries=%d named=%d' % (fg.split('\\')[-1], len(info['entries']), named))

k32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, PID)
print('OpenProcess(pid=%d) -> %s' % (PID, h))
if not h:
    raise SystemExit('cannot open pid')

def rd(addr, n):
    buf = ctypes.create_string_buffer(n)
    read = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(addr), buf, n, ctypes.byref(read))
    return bool(ok), buf.raw[:read.value]

for t in TARGETS:
    print('=' * 78)
    base = t - 0x20
    ok, data = rd(base, 0x240)
    print('TARGET 0x%08X  ok=%s len=%d' % (t, ok, len(data)))
    if not ok:
        continue
    # search for known def hashes (unaligned scan)
    for i in range(0, len(data) - 3):
        v = struct.unpack_from('<I', data, i)[0]
        nm = h2n.get(v)
        if nm:
            print('   HASH 0x%08X @target%+d -> %s' % (v, i - 0x20, nm))
    # ascii strings
    for m in re.finditer(rb'[ -~]{4,}', data):
        print('   STR  @target%+d: %s' % (m.start() - 0x20, m.group().decode('latin1')))
    # raw head
    for i in range(0, min(0x80, len(data)), 16):
        row = data[i:i + 16]
        print('   %08X  %s  |%s|' % (base + i, ' '.join('%02x' % b for b in row),
                                     ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)))
