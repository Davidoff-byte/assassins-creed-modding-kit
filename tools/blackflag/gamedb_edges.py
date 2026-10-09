#!/usr/bin/env python3
"""gamedb edges probe: callers of the applier/setter and their neighbors."""
import sqlite3

DB = r"C:\Users\Administrator\bf4_re\sp_src\.gamedb\index.sqlite"
TARGETS = ["FUN_01ac1ad0", "FUN_01ad9190", "FUN_01ab52c0", "FUN_013aec10",
           "FUN_01ab6680", "FUN_01abb040", "FUN_00e0e5b0", "FUN_01aa3690"]

con = sqlite3.connect(DB)
cur = con.cursor()
print("edges cols:", [r[1] for r in cur.execute("PRAGMA table_info(edges)")])
print("edges sample:")
for r in cur.execute("SELECT * FROM edges LIMIT 5"):
    print("  ", r)

# resolve ids
for t in TARGETS:
    row = cur.execute("SELECT id, name FROM functions WHERE name LIKE ?", (t + '%',)).fetchone()
    if not row:
        print(t, "-> not found")
        continue
    fid, fname = row
    # try both directions depending on schema
    cols = [c[1] for c in cur.execute("PRAGMA table_info(edges)")]
    print("==", fname, "id=", fid)
    for direction in ("in", "out"):
        try:
            if "src" in cols and "dst" in cols:
                if direction == "in":
                    rows = cur.execute("SELECT * FROM edges WHERE dst=? LIMIT 40", (fid,)).fetchall()
                else:
                    rows = cur.execute("SELECT * FROM edges WHERE src=? LIMIT 40", (fid,)).fetchall()
            elif "caller" in cols and "callee" in cols:
                if direction == "in":
                    rows = cur.execute("SELECT * FROM edges WHERE callee=? LIMIT 40", (fid,)).fetchall()
                else:
                    rows = cur.execute("SELECT * FROM edges WHERE caller=? LIMIT 40", (fid,)).fetchall()
            else:
                print("   unknown edge schema:", cols)
                break
            print("   %s-edges: %d" % (direction, len(rows)))
            for r in rows[:40]:
                print("     ", r)
        except Exception as e:
            print("   err:", e)
