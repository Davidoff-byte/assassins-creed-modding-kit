#!/usr/bin/env python3
"""who_refs.py <corpus_root> <regex> [max]

Scans the mass-decompiled part files and prints every line matching <regex>
together with the ENCLOSING FUNCTION name (from the // ==== header).
This is the raw-text complement to gamedb (which only indexes strings/functions,
not arbitrary code identifiers like DAT_ globals or constants).

Examples:
  python who_refs.py C:\\...\\mp_src 01a1c454
  python who_refs.py C:\\...\\sp_src "4dd5f8c" 40
"""
import os
import re
import sys

HDR = re.compile(r'^// ==== (\S+) @ ([0-9a-fA-F]+) ====\s*$', re.M)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    root = sys.argv[1]
    pat = re.compile(sys.argv[2])
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 80
    files = sorted(f for f in os.listdir(root) if f.startswith("part_") and f.endswith(".c"))
    count = 0
    funcs = {}
    for fn in files:
        path = os.path.join(root, fn)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
        except OSError:
            continue
        cur = None
        for i, ln in enumerate(lines):
            m = HDR.match(ln)
            if m:
                cur = m.group(1)
                continue
            if pat.search(ln):
                funcs[cur] = funcs.get(cur, 0) + 1
                print(f"{cur}\t{fn}:{i + 1}\t{ln.strip()[:150]}")
                count += 1
                if count >= limit:
                    print(f"# hit limit {limit}")
                    print("# " + ", ".join(sorted(funcs)))
                    return 0
    print(f"# total: {count} in {len(funcs)} functions")
    print("# " + ", ".join(sorted(funcs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
