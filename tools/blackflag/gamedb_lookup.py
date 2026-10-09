#!/usr/bin/env python3
"""gamedb_lookup.py - map addresses to enclosing gamedb functions.

Usage: gamedb_lookup.py <addr> [addr ...]   (hex, 0x optional)
Prints the schema of the functions table once, then each hit.
"""
import bisect
import sqlite3
import sys

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
con = sqlite3.connect(DB)
cur = con.cursor()

print('== functions schema ==')
for r in cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='functions'"):
    print(r[0])
print('== symbols schema ==')
for r in cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='symbols'"):
    print(r[0])

addrs = []
for (name,) in cur.execute("SELECT name FROM functions"):
    if name.startswith('FUN_') and len(name) >= 12:
        try:
            addrs.append(int(name[4:12], 16))
        except ValueError:
            pass
addrs = sorted(set(addrs))
print('total FUN_ entries:', len(addrs))


def fileof(faddr):
    fn = 'FUN_%08X' % faddr
    r = cur.execute("SELECT file_id FROM functions WHERE name=?", (fn,)).fetchone()
    return r[0] if r else None


for arg in sys.argv[1:]:
    t = int(arg, 16)
    i = bisect.bisect_right(addrs, t) - 1
    if i < 0:
        print('0x%08X -> (below first FUN)' % t)
        continue
    fn = addrs[i]
    fid = fileof(fn)
    print('0x%08X -> FUN_%08X +0x%X file_id=%s' % (t, fn, t - fn, fid))
