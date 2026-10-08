import anvil, re
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
names=[n for (o,t,n,h,p) in res]
print("=== names starting ACC_WR / ACC_W / ACC_Tool / Player- / Tool ===")
for n in names:
    if re.match(r"^(ACC_WR|ACC_W_|ACC_Tool|Tool_|PlayerTool|ACC_Player|CHR_W_P_)", n):
        print("  ", n)
print()
print("=== names containing 'SpawnedProjectile' or 'Projectile' ===")
for n in names:
    if re.search(r"Projectile", n):
        print("  ", n)
