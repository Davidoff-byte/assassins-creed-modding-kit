#!/usr/bin/env python3
"""Look up gamedb functions/symbols near given absolute addresses (crash chain)."""
import sqlite3

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
# crash chain RVAs + image base 0x400000 -> absolute
ADDRS = [0x400000 + r for r in (
    0x3437A0, 0x3437A9, 0x35045F, 0x225DB5, 0x1133C7, 0x161E38,
    0x1134D0, 0x10EEC1, 0x199EF9, 0x1A561D, 0x1A5793, 0x1A89CF,
    0x6327A6, 0x61DB19, 0x4165CE, 0x41662E,
)]

con = sqlite3.connect(DB)
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for t in tables:
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(%s)" % t)]
    except Exception:
        continue
    low = {c.lower(): c for c in cols}
    for key in ("address", "addr", "ea", "vaddr", "va", "start", "offset", "func_addr"):
        if key not in low:
            continue
        col = low[key]
        for a in ADDRS:
            try:
                rows = cur.execute(
                    "SELECT * FROM %s WHERE %s >= ? AND %s <= ? LIMIT 4" % (t, col, col),
                    (a - 0x48, a + 0x48)).fetchall()
                for r in rows:
                    print("0x%X" % a, "|", t, "|", dict(zip(cols, r)))
            except Exception:
                pass
print("done")
