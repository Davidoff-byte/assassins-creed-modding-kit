import re
import sys

path = sys.argv[1]
keywords = [k.lower() for k in sys.argv[2].split(",")] if len(sys.argv) > 2 else []
out_path = sys.argv[3] if len(sys.argv) > 3 else None

data = open(path, "rb").read()
strings = [s.decode("ascii", "ignore") for s in re.findall(rb"[\x20-\x7e]{5,}", data)]
print(f"{path}: {len(strings)} ascii strings")

if out_path:
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(strings))
    print(f"wrote all strings -> {out_path}")

if keywords:
    seen = set()
    hits = 0
    for s in strings:
        low = s.lower()
        if any(k in low for k in keywords) and s not in seen:
            seen.add(s)
            hits += 1
            print(s)
    print(f"--- {hits} unique keyword matches ---")
