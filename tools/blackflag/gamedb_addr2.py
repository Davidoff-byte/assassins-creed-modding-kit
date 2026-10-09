#!/usr/bin/env python3
"""Map crash-chain addresses to enclosing gamedb functions (name = FUN_XXXXXXXX)."""
import bisect
import sqlite3

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
targets = [0x7437A0, 0x75045F, 0x625DB5, 0x5133C7, 0x561E38, 0x5134D0,
           0x50EEC1, 0x599EF9, 0x5A561D, 0x5A5793, 0x5A89CF, 0x6327A6,
           0x61DB19, 0x4165CE, 0x41662E]

con = sqlite3.connect(DB)
cur = con.cursor()
addrs = []
for (name,) in cur.execute("SELECT name FROM functions"):
    if name.startswith('FUN_') and len(name) >= 12:
        try:
            addrs.append(int(name[4:12], 16))
        except ValueError:
            pass
addrs = sorted(set(addrs))
print('total FUN_ entries:', len(addrs))

# look up file for a function and any symbol names (kind='method' rows in symbols)
def fileof(faddr):
    fn = 'FUN_%08X' % faddr
    r = cur.execute("SELECT file_id FROM functions WHERE name=?", (fn,)).fetchone()
    return r[0] if r else None

for t in targets:
    i = bisect.bisect_right(addrs, t) - 1
    if i < 0:
        print('0x%06X -> ?' % t)
        continue
    fn = addrs[i]
    fid = fileof(fn)
    # neareast named symbols in file (user-named functions sometimes exist)
    print('0x%06X -> FUN_%08X (offset +0x%X) file_id=%s' % (t, fn, t - fn, fid))
print('done')
