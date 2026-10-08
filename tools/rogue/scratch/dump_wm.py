import anvil, struct
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
for (o,t,n,h,p) in res:
    if n in ("ACC_WM_ShayDefaultSword_Primary","ACC_WM_ShayDefaultSword_Secondary"):
        print(f"\n===== {n} type=0x{t:08X} len={len(p)} =====")
        for i in range(0,len(p),4):
            u=struct.unpack_from("<I",p,i)[0]
            f=struct.unpack_from("<f",p,i)[0]
            print(f"  +0x{i:03X}: {u:08X}  f={f:.4g}")
