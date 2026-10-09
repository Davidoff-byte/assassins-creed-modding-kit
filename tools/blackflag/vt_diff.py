#!/usr/bin/env python3
"""READ-ONLY: diff player vs crowd behavior vtables; resolve slot fns via gamedb."""
import ctypes
import sqlite3
import struct
import sys

pid = int(sys.argv[1])
k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)

def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value == n else None

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
con = sqlite3.connect(DB)
cur = con.cursor()

def fn_name(addr):
    r = cur.execute("SELECT name FROM functions WHERE name=?",
                    ('FUN_%08X' % addr,)).fetchone()
    if r:
        return r[0]
    # maybe near-start lookup: try any function whose start <= addr (name encodes abs addr)
    r = cur.execute(
        "SELECT name FROM functions WHERE name LIKE 'FUN_%' ORDER BY name DESC LIMIT 1"
    ).fetchone()
    return '?'

VTP = 0x026FA898   # player behavior vt
VTC = 0x026E34D8   # crowd behavior vt
N = 48             # slots

bp = rd(VTP, N * 4)
bc = rd(VTC, N * 4)
if not bp or not bc:
    raise SystemExit('vtable read failed')

print('slot  player_vt      crowd_vt       same?  player_fn / crowd_fn')
for i in range(N):
    p = struct.unpack_from('<I', bp, i * 4)[0]
    c = struct.unpack_from('<I', bc, i * 4)[0]
    same = 'SAME' if p == c else 'DIFF'
    if p == c:
        print('%02X   0x%08X   0x%08X   %s' % (i, p, c, same))
    else:
        print('%02X   0x%08X   0x%08X   %s   %s / %s' % (
            i, p, c, same, fn_name(p), fn_name(c)))
print('done')
