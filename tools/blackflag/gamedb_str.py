#!/usr/bin/env python3
"""Dump all behavior-ish names found in the strings index."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()

for pat in ('Bhv%', '%GenericNPC%', '%Crowd%', 'Nav%', 'CSrv%'):
    cur.execute("SELECT DISTINCT text FROM strings WHERE text LIKE ? LIMIT 30", (pat,))
    hits = [h[0] for h in cur.fetchall()]
    print('%s -> %d: %s' % (pat, len(hits), hits[:28]))
