#!/usr/bin/env python3
"""gamedb_rel.py - callers (and optional callees) of gamedb functions.

Usage: gamedb_rel.py FUN_00abcdef [FUN_...] ...
"""
import sqlite3
import sys

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info(edges)")]
print('edges columns:', cols)

for arg in sys.argv[1:]:
    name = arg if arg.startswith('FUN_') else 'FUN_%08X' % int(arg, 16)
    row = cur.execute("SELECT id, file_id, start_line FROM functions WHERE name=?",
                      (name,)).fetchone()
    if not row:
        print('%s: NOT FOUND' % name)
        continue
    fid, ffid, fl = row
    q = ("SELECT f.name, f.file_id FROM edges e JOIN functions f ON f.id=e.src_id "
         "WHERE e.dst_id=?")
    c = cur.execute(q, (fid,)).fetchall()
    seen = set()
    uniq = []
    for n, fi in c:
        if n in seen:
            continue
        seen.add(n)
        uniq.append((n, fi))
    print('== %s id=%s file=%s line=%s: %d callers' % (name, fid, ffid, fl, len(uniq)))
    for n, fi in uniq[:200]:
        print('   %s (file %s)' % (n, fi))
