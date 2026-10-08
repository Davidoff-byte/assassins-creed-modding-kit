import sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
from forge import Forge
import container_rw as crw

f=Forge(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
e=[x for x in f.entries if x["name"]=="ACC_W_P_ShayDefaultSword_Secondary"][0]
blob=f.data[e["offset"]:e["offset"]+e["size"]]
tmp=os.path.join(os.environ["TEMP"],"verify.data"); open(tmp,"wb").write(blob)
c=crw.load(tmp)
files=crw.decompress_all(c["files"]["blocks"])
pat=bytes([0,1,1,1,1,0,1,0]); i=files[:0x700].find(pat)
print("entry size", e["size"])
print("bools at", hex(i) if i!=-1 else "not found")
print("bytes around:", files[0x5A6:0x5B4].hex(" "))
