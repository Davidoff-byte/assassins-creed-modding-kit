#!/usr/bin/env python3
"""Dump a live entity's memory (0x800 bytes) and search it for known def
hash32s (all forges) and CHR_ debug strings - to identify its def."""
import ctypes
import re
import struct
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 17780
# (entity addr, label)
ENTS = [
    (0x47F2BE30, 'THE EDWARD NPC (key F00030AE)'),
    (0x37F7FA70, 'THE PLAYER'),
]
SIZE = 0x800

GAME = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
FORGES = [
    GAME + r"\DataPC_extra_chr.forge",
    GAME + r"\DataPC.extra",
    GAME + r"\DataPC.forge",
]

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
            h2n.setdefault(h, nm)
            named += 1
    print('loaded %-45s entries=%d named=%d' % (fg.split('\\')[-1], len(info['entries']), named))
print('hash map size: %d' % len(h2n))

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, PID)
if not h:
    raise SystemExit('cannot open pid')

def rd(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), buf, n, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None

for ent, lbl in ENTS:
    print('=' * 78)
    d = rd(ent, SIZE)
    print('ENTITY 0x%08X  %s  (read %s bytes)' % (ent, lbl, len(d) if d else 0))
    if not d:
        continue
    print('-- head:')
    for i in range(0, 0x80, 16):
        row = d[i:i + 16]
        print('   +%03X %s  |%s|' % (i, ' '.join('%02x' % b for b in row),
                                     ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)))
    hits = []
    for i in range(0, len(d) - 3):
        v = struct.unpack_from('<I', d, i)[0]
        nm = h2n.get(v)
        if nm:
            hits.append((i, v, nm))
    print('-- known-def-hash hits: %d' % len(hits))
    for i, v, nm in hits[:40]:
        print('   +0x%03X  0x%08X -> %s' % (i, v, nm))
    strs = [(m.start(), m.group().decode('latin1')) for m in re.finditer(rb'[ -~]{5,}', d)]
    if strs:
        print('-- strings:')
        for off, s in strs[:40]:
            print('   +0x%03X  %s' % (off, s))
