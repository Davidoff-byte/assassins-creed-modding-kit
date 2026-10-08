import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
names=[n for (o,t,n,h,p) in res]
print("=== names with Shay / CHR_P / PlayerCharacter / BuildTable ===")
for n in names:
    if re.search(r"Shay|CHR_P_|PlayerCharacter|BuildTable|Attachment", n, re.I):
        print("  ", n)
