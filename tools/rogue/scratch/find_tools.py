import anvil, re
from collections import Counter
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
# group by type id, show a few example names per type
tys={}
for (o,tid,n,h,p) in res:
    tys.setdefault(tid, []).append((n,len(p)))
print("total resources", len(res), "types", len(tys))
# find types whose names look like tool/weapon/gear/loadout definition tables
kw=re.compile(r"tool|loadout|gear|quickselect|equipment|playerweapon|weaponset|inventory", re.I)
for tid,items in sorted(tys.items(), key=lambda kv:-len(kv[1])):
    ex=[n for n,_ in items]
    hit=[n for n in ex if kw.search(n)]
    if hit:
        print(f"\nTYPE 0x{tid:08X}  count={len(items)}")
        for n in hit[:12]: print("   ", n)
