import anvil, struct, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
for target in ("ACGA_Crafting_SmokeBombPouch_1","ACGA_Crafting_RopeDartPouch_1","ACGA_WeaponUpgrade_BerserkGrenade_3"):
    for (o,tid,name,h,p) in res:
        if name==target:
            print(f"=== {name} type=0x{tid:08X} len={len(p)} ===")
            print("qwords/quads:")
            for i in range(0, min(len(p),160), 4):
                u=struct.unpack_from("<I",p,i)[0]
                print(f"  +0x{i:03X}: {u:08X} ({u})")
            # ascii
            for m in re.finditer(rb"[ -~]{3,}", p):
                print("   str:", m.group().decode("latin-1"))
            break
