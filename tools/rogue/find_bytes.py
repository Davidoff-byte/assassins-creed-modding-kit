import sys
from pathlib import Path

d = Path(sys.argv[1]).read_bytes()
pat = bytes.fromhex(sys.argv[2].replace(" ", ""))
hits = []
i = 0
while True:
    j = d.find(pat, i)
    if j < 0:
        break
    hits.append(j)
    i = j + 1
print(f"size={len(d)} pattern={sys.argv[2]} hits={[hex(h) for h in hits]}")
