#!/usr/bin/env python3
"""merge_symbols.py - build the merged naming table from the overnight analysis outputs.

Inputs (bf4_re/analysis):
  propnames_{sp,mp}.tsv   func -> suggested name (string-anchored)
  cross_sp_mp.tsv         sp_func, mp_func, shared_string_count (>=2)
Output:
  symbol_suggestions.tsv  exe, func, suggestion, source, weight
    source: "own" (its own exe's proposal) or "via-mp"/"via-sp" (transferred, weight=shared count)
"""
import os
import csv

A = r"C:\Users\Administrator\bf4_re\analysis"


def load_props(tag):
    d = {}
    p = os.path.join(A, f"propnames_{tag}.tsv")
    if not os.path.exists(p):
        return d
    with open(p, "r", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        next(r, None)
        for row in r:
            if len(row) >= 2:
                d[row[0]] = row[1]
    return d


def main():
    sp = load_props("sp")
    mp = load_props("mp")
    rows = []
    for fn, sn in sp.items():
        rows.append(("sp", fn, sn, "own", 0))
    for fn, sn in mp.items():
        rows.append(("mp", fn, sn, "own", 0))

    cross = os.path.join(A, "cross_sp_mp.tsv")
    transferred = 0
    if os.path.exists(cross):
        with open(cross, "r", encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            next(r, None)
            for row in r:
                if len(row) < 3:
                    continue
                a, b, n = row[0], row[1], int(row[2])
                if a not in sp and b in mp:
                    rows.append(("sp", a, mp[b], "via-mp", n))
                    transferred += 1
                if b not in mp and a in sp:
                    rows.append(("mp", b, sp[a], "via-sp", n))
                    transferred += 1

    out = os.path.join(A, "symbol_suggestions.tsv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["exe", "func", "suggestion", "source", "weight"])
        w.writerows(rows)
    print(f"wrote {out}: {len(rows)} rows ({transferred} transferred via cross-map)")


if __name__ == "__main__":
    main()
