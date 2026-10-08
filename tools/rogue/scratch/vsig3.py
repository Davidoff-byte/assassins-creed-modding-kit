from pathlib import Path
pe=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe").read_bytes()
sig=bytes.fromhex("48 89 5C 24 10 48 89 6C 24 18 56 57 41 55 48 83 EC 20 48 8B 01 48 8B F2 48 8B F9 4C 8B 80 E8 01 00 00 49 8B 68 08")
print("AI_ACTION_AVAIL matches:", pe.count(sig))
