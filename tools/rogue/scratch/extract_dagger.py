import anvil
c=anvil.read_container(r"blobs/CUR_ACC_W_P_ShayDefaultSword_Secondary.data")
out=r"C:\Users\ADMINI~1\AppData\Local\Temp\atk_dagger"
import os
os.makedirs(out, exist_ok=True)
for (o,t,n,h,p) in anvil.walk_files(c["files"]):
    safe="".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in n)
    open(os.path.join(out, safe+".bin"),"wb").write(p)          # class data
    open(os.path.join(out, safe+".hdr.bin"),"wb").write(h+p)    # header + class data
    print(safe, "len", len(p), "hdr", len(h))
