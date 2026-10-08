from pathlib import Path
pe=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe").read_bytes()
sig=bytes.fromhex("40 57 48 83 EC 20 48 8B 09 48 8B FA 48 85 C9 74 3D 48 8B 49 40 48 89 5C 24 30 48 8B 1D")
print("KNIFE_PROBE matches:", pe.count(sig))
