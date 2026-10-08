import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
for (o,tid,name,header,payload) in res:
    if name in ("UIInventoryContext","Shops"):
        open(f"blobs/{name}.bin","wb").write(payload)
        print("=== ", name, "len", len(payload), "===")
        for m in re.finditer(rb"[ -~]{3,}", payload):
            s=m.group().decode("latin-1")
            print(f"  0x{m.start():04X}: {s}")
