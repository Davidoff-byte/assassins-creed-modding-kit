import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
names=[n for (o,t,n,h,p) in res]
print("=== resource names matching throw|dagger|knife|projectile (weapon-ish) ===")
for n in names:
    if re.search(r"throw|dagger|knife", n, re.I):
        print("  ", n)
print()
print("=== ACC_WR_Player* / ACC_W_Player* resources ===")
for n in names:
    if re.search(r"ACC_W[RP]?_?Player", n, re.I):
        print("  ", n)
