import anvil
# where do the sound sets live?
c=anvil.read_container(r"blobs/CUR_Game Bootstrap Settings.data")
res=list(anvil.walk_files(c["files"]))
for (o,t,n,h,p) in res:
    if n in ("WeaponSoundSet_Medium_Sword","WeaponSoundSet_Medium_Sword_NPC"):
        print(f"settings: {n} type=0x{t:08X} hdr={h.hex(' ')} len={len(p)}")
# and in a weapon secondary
import os
c2=anvil.read_container(r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data")
for (o,t,n,h,p) in anvil.walk_files(c2["files"]):
    print(f"weapon  : {n} type=0x{t:08X} hdr={h.hex(' ')} len={len(p)}")
