import re, glob, bisect
funcs=[]
for fn in glob.glob(r"C:\Users\Administrator\ghidra-acc\acc-decomp\*.c"):
    try:
        txt=open(fn,encoding="utf-8",errors="replace").read().splitlines()
    except: continue
    for l in txt:
        m=re.match(r"// ([0-9a-fA-F]{6,}) size=(\d+) (\S+)", l)
        if m:
            funcs.append((int(m.group(1),16), int(m.group(2)), m.group(3), fn))
funcs.sort()
starts=[f[0] for f in funcs]
callers=[0x14180AC4E,0x141803865,0x142102CD9,0x141870D2A,0x141871100,0x14183E08C,0x14183E0E9,0x14183E2CA,0x141839D76,0x1418551A3,0x14184EA3C,0x14185543E,0x14185128D,0x14183FF0D,0x141840362,0x14180CFFE,0x14183C002,0x141850947,0x141856727,0x141856736,0x14183B99B,0x1417F6FAE,0x14180B7CE,0x1417F9B59,0x141804AFB,0x1417F6FC2,0x141869639,0x14186983E]
def find(va):
    i=bisect.bisect_right(starts,va)-1
    if i<0: return None
    a,sz,name,fn=funcs[i]
    if a<=va<a+sz: return (name,a,sz,fn)
    return None
for c in callers:
    r=find(c)
    print(f"0x{c:X} -> {r[0] if r else '??'}  (+0x{c-r[1]:X})" if r else f"0x{c:X} -> ??")
