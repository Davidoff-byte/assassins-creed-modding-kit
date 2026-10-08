import sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
from forge import Forge
import container_rw as crw
f=Forge(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
tgt=["ACC_W_P_French_Cutlass_Secondary","ACC_W_P_ShayDefaultSword_Secondary","ACC_W_P_British_Cutlass_Secondary"]
hits=0
for e in f.entries:
    if e["name"].endswith("_Secondary"):
        blob=f.data[e["offset"]:e["offset"]+e["size"]]
        tmp=os.path.join(os.environ["TEMP"],"_v.data"); open(tmp,"wb").write(blob)
        c=crw.load(tmp); files=crw.decompress_all(c["files"]["blocks"])
        # look for the patched pattern 00 00 01 01 01 01 01 00
        j=files.find(bytes([0,0,1,1,1,1,1,0]))
        if j!=-1 and j<0x2000: hits+=1
        if e["name"] in tgt:
            print(f"{e['name']}: size={e['size']} patched={j!=-1 and j<0x2000}")
print("total _Secondary entries with patched pattern:", hits)
