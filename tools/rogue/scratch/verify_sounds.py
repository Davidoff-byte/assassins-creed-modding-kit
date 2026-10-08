import os,sys
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
from forge import Forge
import anvil, container_rw as crw
f=Forge(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
e=[x for x in f.entries if x["name"]=="ACC_W_P_French_Cutlass_Secondary"][0]
blob=f.data[e["offset"]:e["offset"]+e["size"]]
tmp=os.path.join(os.environ["TEMP"],"_v2.data"); open(tmp,"wb").write(blob)
c=crw.load(tmp)
for (o,t,n,h,p) in anvil.walk_files(crw.decompress_all(c["files"]["blocks"])):
    if "SoundSet" in n: print(f"{n}: {len(p)} bytes")
print("forge size", len(f.data))
