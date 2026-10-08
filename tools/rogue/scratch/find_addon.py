import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
for (o,t,n,h,p) in res:
    if re.search(r"Addon|WM_Shay|Sword.*Dagger|Dagger.*Sword", n, re.I):
        print(f"type=0x{t:08X} len={len(p):6d} {n}")
