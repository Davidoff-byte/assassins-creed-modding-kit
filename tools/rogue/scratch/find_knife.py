import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
print("resources with 'knife' in name:")
for (o,tid,name,header,payload) in res:
    if re.search(r"knife", name, re.I):
        print(f"  0x{o:08X} type=0x{tid:08X} len={len(payload):6d} {name!r}")
print()
print("resources with 'inv' or 'equip' or 'arsenal' or 'outfit' in name:")
n=0
for (o,tid,name,header,payload) in res:
    if re.search(r"invent|equip|arsenal|outfit|player.*item", name, re.I):
        print(f"  0x{o:08X} type=0x{tid:08X} len={len(payload):6d} {name!r}"); n+=1
        if n>25: break
