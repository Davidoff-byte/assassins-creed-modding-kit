import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
names=[name for (o,tid,name,h,p) in res]
print("total resources:", len(names))
acga=[n for n in names if n.startswith("ACGA_")]
print("ACGA_ count:", len(acga))
for n in acga:
    if re.search(r"knife|throw|dagger|blade|tomahawk|tool", n, re.I):
        print("  ", n)
print("--- all ACGA (first 80) ---")
for n in acga[:80]:
    print("  ", n)
