import anvil
for tag,path in [("STK","blobs/STK_Game Bootstrap Settings.data")]:
    c = anvil.read_container(path)
    res=list(anvil.walk_files(c["files"]))
    fs=[(o,tid,name,header,payload) for (o,tid,name,header,payload) in res if "FightSettings" in name]
    print(tag, "FightSettings resources:", [(hex(o),name,len(p)) for (o,tid,name,h,p) in fs][:5])
    if fs:
        o,tid,name,h,p=fs[0]
        open(f"blobs/FightSettings_{tag}.bin","wb").write(p)
        print(tag,"0x360-0x380:", p[0x360:0x380].hex(" "))
