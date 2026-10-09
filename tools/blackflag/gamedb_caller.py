#!/usr/bin/env python3
"""Identify the caller of the request setter: file 115, find the function
containing line 2369 and who calls IT."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()
cur.execute("SELECT id, path FROM files WHERE id=115")
print('file:', cur.fetchall())
cur.execute("SELECT id, name, start_line, end_line FROM functions "
            "WHERE file_id=115 AND start_line<=2369 AND end_line>=2369")
rows = cur.fetchall()
print('containing fn:', rows)
if rows:
    fid = rows[0][0]
    cur.execute("SELECT f.name, f.file_id, f.start_line FROM edges e "
                "JOIN functions f ON f.id=e.src_id WHERE e.dst_id=?", (fid,))
    callers = cur.fetchall()
    seen = set()
    print('callers of', rows[0][1], ':', len(callers))
    for name, file_id, line in callers:
        if (name, line) in seen:
            continue
        seen.add((name, line))
        print('   %s (file_id=%s line=%s)' % (name, file_id, line))
