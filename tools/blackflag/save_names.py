import glob
import os
import re

game = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
files = sorted(set(
    glob.glob(os.path.join(game, "DataPC*.forge")) +
    glob.glob(os.path.join(game, "multi", "**", "*.forge"), recursive=True) +
    glob.glob(os.path.join(game, "dlc_*", "**", "*.forge"), recursive=True)
))

names = set()
for f in files:
    try:
        with open(f, "rb") as fh:
            data = fh.read(24 * 1024 * 1024)
    except OSError:
        continue
    for m in re.finditer(rb"[\x20-\x7E]{4,80}", data):
        names.add(m.group().decode("latin-1"))

out = r"C:\Users\Administrator\Documents\Default Project\bf-coop\tools\forge_names.txt"
with open(out, "w", encoding="utf-8", errors="replace") as fh:
    fh.write("\n".join(sorted(names)))
print("names saved:", len(names), "->", out)
