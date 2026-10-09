#!/usr/bin/env python3
"""Chase pointers from an entity (depth<=3) and search every reachable block for
known def hash32s + CHR_ strings, to find which def the entity is built from."""
import ctypes
import re
import struct
import sys

sys.path.insert(0, r'C:\Users\Administrator\Documents\Default Project\bf-coop\tools')
import forge_toc as ft

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 17780
ROOT = 0x47F2BE30  # THE EDWARD NPC

TARGETS = {
    0x9A958CF0: 'CHR_U_EdwardKenwayStandard (probe content)',
    0x51BAB7D4: 'CHR_U_Duncan_Walpole (F_Poor content)',
    0xC1BB9618: 'CHR_C_F_Poor (probe target)',
    0x64D5F55C: 'CHR_C_F_Rich (probe target)',
    0x12CECF74: 'CHR_G_Spanish_Soldier (probe target)',
    0xB3DE056C: 'CHR_C_M_Slaves (probe target)',
    0x12CECF30: 'CHR_C_M_Spanish_Medium (trio)',
    0xC0A3FCE0: 'CHR_P_EdwardKenway_Default (player)',
}
# also resolve every extra_chr name matching the probe families
GAME = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
info = ft.parse_forge(GAME + r"\DataPC_extra_chr.forge")
for e in info['entries']:
    nm = e.get('name') or ''
    if re.search(r'(Walpole|EdwardKenway|Slaves|Soldier|_Poors?$|_Rich$|Spanish_(Poors|Rich|Medium))', nm):
        TARGETS.setdefault(e['hash32'], nm + '  (extra_chr)')

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, PID)
if not h:
    raise SystemExit('cannot open pid')

def rd(a, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), buf, n, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None

seen = set()
queue = [(ROOT, 'ROOT', 0)]
found = []
while queue and len(seen) < 400:
    addr, path, depth = queue.pop(0)
    if addr in seen or depth > 3:
        continue
    seen.add(addr)
    d = rd(addr, 0x200)
    if not d:
        continue
    for i in range(0, len(d) - 3):
        v = struct.unpack_from('<I', d, i)[0]
        nm = TARGETS.get(v)
        if nm:
            found.append((path, addr, i, v, nm))
    for m in re.finditer(rb'CHR_[ -~]{3,}', d):
        found.append((path, addr, m.start(), 0, 'STRING: ' + m.group().decode('latin1')))
    if depth < 3:
        for i in range(0, len(d) - 3, 4):
            v = struct.unpack_from('<I', d, i)[0]
            if 0x0F000000 <= v <= 0x7FFFFFFF and v not in seen:
                queue.append((v, path + '>+0x%X' % i, depth + 1))

print('visited %d blocks; findings: %d' % (len(seen), len(found)))
for path, addr, off, v, nm in found[:80]:
    print('  %s  @0x%08X+0x%X  %s' % (path, addr, off, nm))
