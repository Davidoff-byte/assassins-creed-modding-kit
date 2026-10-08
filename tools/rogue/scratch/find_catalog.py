import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
# group by type id
from collections import Counter
cnt=Counter(tid for (o,tid,n,h,p) in res)
# the item/grant catalog is likely a specific type; find types whose names start ACGA_ and have 'Outfit'/'Weapon'
tys={}
for (o,tid,n,h,p) in res:
    if n.startswith("ACGA_"):
        tys.setdefault(tid, []).append(n)
for tid,names in sorted(tys.items(), key=lambda kv:-len(kv[1]))[:6]:
    print(f"type 0x{tid:08X}: {len(names)} ACGA_ names; e.g. {names[:3]}")
    # search knife/throw
    hits=[n for n in names if re.search(r"knife|throw|dagger|rope|smoke", n, re.I)]
    print("   knife/throw-ish:", hits[:10])
