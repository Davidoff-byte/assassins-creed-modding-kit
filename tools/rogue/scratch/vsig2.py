from pathlib import Path
pe=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe").read_bytes()
s=bytes.fromhex("40 53 48 83 EC 20 48 83 B9 F8 00 00 00 00 48 8B D9 75 52 4C 8B 05 F6 F4 1E 01 BA 10 00 00 00 B9 F0 11 00 00")
print("AI_FM_ACCESSOR matches:", pe.count(s))
