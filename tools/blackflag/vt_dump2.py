#!/usr/bin/env python3
"""READ-ONLY: dump a vtable's slots from the live process and resolve gamedb names.

Usage: vt_dump2.py <pid> <vtaddr_hex> [slots]
"""
import ctypes
import struct
import sqlite3
import sys

pid = int(sys.argv[1])
vt = int(sys.argv[2], 16)
slots = int(sys.argv[3]) if len(sys.argv) > 3 else 32
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


def name_of(v):
    r = cur.execute("SELECT name FROM functions WHERE name LIKE ?",
                    ('FUN_%08x' % v,)).fetchone()
    if not r:
        r = cur.execute("SELECT name FROM functions WHERE name LIKE ?",
                        ('FUN_%08X' % v,)).fetchone()
    return r[0] if r else ''


b = rd(vt, slots * 4)
print('vt=0x%08X' % vt)
for i in range(slots):
    v = struct.unpack_from('<I', b, i * 4)[0]
    tag = ''
    if 0x400000 <= v <= 0x6F00000:
        tag = name_of(v) or 'code?'
    print('  slot %02X: 0x%08X  %s' % (i, v, tag))
