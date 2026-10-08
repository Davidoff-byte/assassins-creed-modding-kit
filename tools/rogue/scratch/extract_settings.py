import struct, sys
import anvil
c = anvil.read_container(r"blobs\CUR_Game Bootstrap Settings.data")
res = list(anvil.walk_files(c["files"]))
for (o, tid, name, header, payload) in res:
    if name == "Game Bootstrap Settings":
        open("blobs/settings_payload.bin","wb").write(payload)
        print("wrote settings_payload.bin", len(payload), "type=0x%08X"%tid, "hdr", len(header))
        break
