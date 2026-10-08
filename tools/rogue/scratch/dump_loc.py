import re
d=open("blobs/loc_english.bin","rb").read()
# ascii runs
runs=re.findall(rb"[ -~]{6,}", d)
print("ascii runs:", len(runs))
for r in runs[:25]:
    print("  ", r[:80].decode("latin-1"))
# utf16
u16=re.findall(rb"(?:[ -~]\x00){5,}", d)
print("utf16 runs:", len(u16))
for r in u16[:10]:
    print("  U16", r[:80].decode("utf-16-le","replace"))
