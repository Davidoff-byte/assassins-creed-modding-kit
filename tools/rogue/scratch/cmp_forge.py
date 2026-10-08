from pathlib import Path
g=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge").read_bytes()
off=0x007658000; size=458780
cur=g[off:off+size]
Path(r"C:\Users\ADMINI~1\AppData\Local\Temp\cur_secondary.data").write_bytes(cur)
old=Path(r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data").read_bytes()
print("cur", len(cur), "old", len(old))
n=min(len(cur),len(old)); diff=[i for i in range(n) if cur[i]!=old[i]]
print("byte diffs:", len(diff))
for i in diff[:40]:
    print(f"  0x{i:06X}: cur={cur[i]:02X} old={old[i]:02X}")
