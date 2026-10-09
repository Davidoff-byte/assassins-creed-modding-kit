#!/usr/bin/env python3
"""Find the crowd behavior (BhvGenericNPC) + friends in the gamedb index."""
import sqlite3

DB = r'C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite'
db = sqlite3.connect(DB)
cur = db.cursor()

for pat in ('%BhvGenericNPC%', '%BhvAssassin%', '%BhvAnimal%'):
    cur.execute("SELECT name, kind, file_id, line FROM symbols WHERE name LIKE ? "
                "LIMIT 12", (pat,))
    hits = cur.fetchall()
    print(pat, '->', len(hits), 'symbols')
    for h in hits:
        print('   ', h)
    cur.execute("SELECT text, file_id, line FROM strings WHERE text LIKE ? LIMIT 8",
                (pat,))
    sh = cur.fetchall()
    for h in sh:
        print('    str:', h)
