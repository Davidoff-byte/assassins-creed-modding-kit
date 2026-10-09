#!/usr/bin/env python3
"""Resolve: (1) DIFF vtable addresses in gamedb (case-insensitive + nearest fallback),
(2) functions containing specific lines in part_00093.c."""
import bisect
import sqlite3

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
con = sqlite3.connect(DB)
cur = con.cursor()

# --- all function starts for fallback ---
addrs = []
for (name,) in cur.execute("SELECT name FROM functions"):
    if name.upper().startswith('FUN_') and len(name) >= 12:
        try:
            addrs.append(int(name[4:12], 16))
        except ValueError:
            pass
addrs = sorted(set(addrs))

def resolve(a):
    r = cur.execute("SELECT name, file_id FROM functions WHERE name LIKE ?",
                    ('FUN_%08x' % a,)).fetchone()
    if not r:
        r = cur.execute("SELECT name, file_id FROM functions WHERE name LIKE ?",
                        ('FUN_%08X' % a,)).fetchone()
    if r:
        return '%s (file %s)' % r
    i = bisect.bisect_right(addrs, a) - 1
    if i >= 0:
        return 'within FUN_%08X +0x%X' % (addrs[i], a - addrs[i])
    return '?'

diffs = [0x0186B340, 0x016A1640, 0x018071A0, 0x016A1670, 0x017FFCD0, 0x0169B340,
         0x018071F0, 0x00FC4A90, 0x018246A0, 0x004AE410, 0x017FFCE0, 0x0169B350,
         0x01807210, 0x016B0750, 0x0076C900, 0x0076BF10, 0x01807350, 0x016A16A0]
print('== vtable diff resolution ==')
for a in diffs:
    print('0x%08X  %s' % (a, resolve(a)))

print()
print('== functions containing part_00093.c lines ==')
row = cur.execute("SELECT id FROM files WHERE path LIKE 'part_00093%'").fetchone()
print('part_00093 file id:', row)
if row:
    fid = row[0]
    for ln in (34397, 34403, 34412, 22733, 22739, 16377, 21857):
        r = cur.execute(
            "SELECT name, start_line, end_line FROM functions "
            "WHERE file_id=? AND start_line<=? AND end_line>=?",
            (fid, ln, ln)).fetchone()
        print('line %d -> %s' % (ln, r))
print('done')
