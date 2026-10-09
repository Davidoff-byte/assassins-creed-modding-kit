#!/usr/bin/env python3
"""Find the function whose address range contains a given code address."""
import re
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()
cur.execute("SELECT id, name, file_id, start_line, end_line FROM functions "
            "WHERE name LIKE 'FUN_%'")
rows = cur.fetchall()
addrs = []
for fid, name, file_id, sl, el in rows:
    m = re.match(r'FUN_([0-9a-fA-F]{8})$', name)
    if m:
        addrs.append((int(m.group(1), 16), fid, name, file_id, sl, el))
addrs.sort()
starts = [a[0] for a in addrs]


def containing(x):
    import bisect
    i = bisect.bisect_right(starts, x) - 1
    return addrs[i] if i >= 0 else None


for x in (0x179376c, 0x1793766, 0x186f647, 0x1385f99):
    c = containing(x)
    if c:
        print('0x%X -> %s (file_id=%s lines %s-%s)' % (x, c[2], c[3], c[4], c[5]))
    else:
        print('0x%X -> none' % x)
