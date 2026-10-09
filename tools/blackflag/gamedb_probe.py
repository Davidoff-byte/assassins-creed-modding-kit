#!/usr/bin/env python3
"""Inspect the gamedb index schema + locate the function containing 0x179376c."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('tables:', tables)
for t in tables:
    cur.execute('PRAGMA table_info(%s)' % t)
    cols = [r[1] for r in cur.fetchall()]
    cur.execute('SELECT COUNT(*) FROM %s' % t)
    n = cur.fetchone()[0]
    print('  %s (%d rows): %s' % (t, n, cols))
