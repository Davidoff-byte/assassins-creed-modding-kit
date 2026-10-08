import anvil
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
import re
kw=re.compile(r"knife|weapon|invent|arsenal|shop|tools?$|thrown|throwable", re.I)
n=0
for (o,tid,name,header,payload) in res:
    if kw.search(name):
        print(f"0x{o:08X} type=0x{tid:08X} len={len(payload):7d} {name!r}")
        n+=1
        if n>60: break
print("total matched (shown up to 60)", n)
