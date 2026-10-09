#!/usr/bin/env python3
"""gamedb queries: find the 0x179376c wrapper + all callers of NavigateTo."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()


def find(pat):
    cur.execute("SELECT id, name, file_id, start_line, end_line FROM functions "
                "WHERE name LIKE ?", (pat,))
    return cur.fetchall()


print('wrapper candidates (179376):', find('%179376%'))
navto = find('%01785ed0%')
print('navto:', navto)
if navto:
    fid = navto[0][0]
    cur.execute("SELECT f.name, f.file_id, f.start_line FROM edges e "
                "JOIN functions f ON f.id = e.src_id WHERE e.dst_id = ?", (fid,))
    callers = cur.fetchall()
    print('callers of NavigateTo: %d' % len(callers))
    seen = set()
    for name, file_id, line in callers:
        key = (name, line)
        if key in seen:
            continue
        seen.add(key)
        print('   %s   (file_id=%s line=%s)' % (name, file_id, line))
