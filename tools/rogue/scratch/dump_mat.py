import anvil, struct
c=anvil.read_container(r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data")
for (o,t,n,h,p) in anvil.walk_files(c["files"]):
    if n in ("CHR_W_Dagger_Axe","CHR_W_Dagger_Axe_Set"):
        print(f"\n===== {n} type=0x{t:08X} len={len(p)} =====")
        for i in range(0,len(p)-3,4):
            u=struct.unpack_from("<I",p,i)[0]; f=struct.unpack_from("<f",p,i)[0]
            mark=""
            if 0.0<=f<=1.5 and abs(f) > 1e-9: mark=" <- float"
            print(f"  +0x{i:03X}: {u:08X}  f={f:.5g}{mark}")
