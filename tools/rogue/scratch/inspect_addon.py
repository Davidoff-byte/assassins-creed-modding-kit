import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
want={"Addon_Human_Weapon_SmallWeapon","Addon_Human_Weapon_Sword_MainHand","CHR_Weapon_AddOn","Addon_Human_Weapon_Ref"}
for (o,t,n,h,p) in res:
    if n in want:
        print(f"\n===== {n}  (type 0x{t:08X}, {len(p)} B) =====")
        strs=re.findall(rb"[ -~]{4,}", p)
        for s in strs[:40]:
            print("   ", s.decode("latin-1"))
