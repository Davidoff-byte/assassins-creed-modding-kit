#!/usr/bin/env python3
"""Dump a vtable/descriptor region from the live game and resolve each pointer
against the gamedb function index."""
import ctypes
import sqlite3
import struct
import sys

pid = int(sys.argv[1])
targets = [int(x, 16) for x in sys.argv[2:]] or [0x026E34D8]

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


db = sqlite3.connect(r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite')
cur = db.cursor()
name_cache = {}


def fname(a):
    if a in name_cache:
        return name_cache[a]
    cur.execute("SELECT name, file_id, start_line FROM functions WHERE name=?",
                ('FUN_%08x' % a,))
    r = cur.fetchone()
    name_cache[a] = r
    return r


for t in targets:
    print('==== region 0x%08X ====' % t)
    blob = rd(t - 0x20, 0x180)
    if not blob:
        print('  unreadable')
        continue
    for i in range(0, 0x180, 4):
        v = struct.unpack_from('<I', blob, i)[0]
        addr = t - 0x20 + i
        info = ''
        if 0x400000 <= v <= 0x2C00000 and i >= 0x20:
            r = fname(v)
            if r:
                info = ' -> %s (file_id=%s line=%s)' % r
        print('  +%03X: %08X%s' % (i - 0x20 if i >= 0x20 else 0, v, info))
