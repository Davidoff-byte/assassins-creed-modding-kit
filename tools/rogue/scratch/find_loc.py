import anvil, re
c=anvil.read_container(r"blobs/CUR_LocalizationPackage_English.data")
res=list(anvil.walk_files(c["files"]))
print("resources:", len(res))
data=b"".join(p for (o,t,n,h,p) in res)
open("blobs/loc_english.bin","wb").write(data)
print("concat len", len(data))
for kw in (rb"[Tt]hrowing[ _]?[Kk]nife", rb"[Kk]nives"):
    for m in list(re.finditer(kw, data))[:20]:
        s=max(0,m.start()-40); e=min(len(data), m.end()+60)
        chunk=data[s:e]
        # print printable
        txt="".join(chr(b) if 32<=b<127 else "." for b in chunk)
        print(f"  @0x{m.start():X}: {txt}")
