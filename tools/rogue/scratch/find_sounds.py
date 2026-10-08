import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
names=[n for (o,t,n,h,p) in res]
print("=== WeaponSoundSet_* resources ===")
seen=set()
for n in sorted(names):
    if n.startswith("WeaponSoundSet") and n not in seen:
        seen.add(n); print("  ", n)
