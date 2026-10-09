#!/usr/bin/env python3
"""Callers of the animation-request setter FUN_01ad9190."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()
cur.execute("SELECT id, name, file_id, start_line, end_line FROM functions "
            "WHERE name='FUN_01ad9190'")
me = cur.fetchall()
print('setter:', me)
if me:
    fid = me[0][0]
    cur.execute("SELECT f.name, f.file_id, f.start_line FROM edges e "
                "JOIN functions f ON f.id = e.src_id WHERE e.dst_id=?", (fid,))
    callers = cur.fetchall()
    print('callers: %d' % len(callers))
    seen = set()
    for name, file_id, line in callers:
        if (name, line) in seen:
            continue
        seen.add((name, line))
        print('   %s  (file_id=%s line=%s)' % (name, file_id, line))
