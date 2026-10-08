from pathlib import Path
pe=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe").read_bytes()
a=bytes.fromhex("40 53 48 83 EC 20 8B D9 48 8B CA E8 20 11 FE FE 48 85 C0 74 71 48 8B C8 E8 13 CB 00 FF 48 8B C8 48 85 C0 74 61 48 8B 00 33 D2 FF")
b=bytes.fromhex("40 53 48 83 EC 20 8B DA E8 B3 11 FE FE 48 85 C0 74 71 48 8B C8 E8 A6 CB 00 FF 48 8B C8 48 85 C0 74 61 48 8B 00 33 D2 FF")
print("KNIFE_QTY:", pe.count(a), "KNIFE_QTY_MAX:", pe.count(b))
