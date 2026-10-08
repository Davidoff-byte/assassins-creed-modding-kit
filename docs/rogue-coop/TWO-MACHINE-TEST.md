# AccCoop — how to test with your friend (two machines)

**Read this with `dist/README.txt`.** This first test verifies the **link** (each machine hears the
other). The on-screen avatar comes after Route A's discovery step.

## 0. Preconditions
- **Same game version on both machines.** `certutil -hashfile "ACC.exe" MD5` must be
  `A323729F3799A808C8148B695E1E23B8`. If your friend's differs, stop — tell me.
- **Radmin VPN** installed, both joined to the same private network (the IPs look like `26.x.x.x`).
- The package in `acc-coop/dist/` on both machines.

## 1. Install (each machine)
1. `dinput8.dll` → `<Rogue>\dinput8.dll` (the ASI loader; skip if they already have one).
2. `AC.Rogue.PatchFix.asi` and `AC.Rogue.PatchFix.ini` → `<Rogue>\plugins\`.

## 2. Configure (each machine)
Edit `<Rogue>\plugins\AC.Rogue.PatchFix.ini` `[Coop]`:
- **You:** `RemoteIp1..4` = friend's Radmin IP; `ClientId=1`
- **Friend:** `RemoteIp1..4` = your Radmin IP; `ClientId=2`

Example: friend is `26.0.0.7` → `RemoteIp1=26  RemoteIp2=0  RemoteIp3=0  RemoteIp4=7`.
Ports stay `27700` on both.

## 3. Run
1. Radmin up; confirm you can **ping** each other (`ping 26.0.0.x`).
2. Launch Rogue on **both**; both load into gameplay; both **walk around ~30 s**.
3. On each machine open `<Rogue>\plugins\AC.Rogue.PatchFix.log` and look for:

```
PlayerTransform: BODY=(1070.9,396.3,6.6) cam=(...) speed=3.6 state=2
PlayerTransform: BODY=(...) ... peer=1
```

`peer=1` on **both** machines = **the link works.** (First allow ACC.exe through the Windows
Firewall on Private networks if prompted.)

## 4. What each outcome means
| Symptom | Meaning |
|---|---|
| `PlayerTransform: installed` + `BODY=` lines | plugin loaded, reading your body |
| `peer=1` on both | UDP link works both ways 🎉 |
| no `BODY=` lines | plugin didn't load (loader/version) |
| no `peer=1` | wrong `RemoteIp`, Radmin down, or firewall |

## 5. What's next (Route A — the visible avatar)
The link test proves the **data** path. Route A turns that into something you can *see*. It needs one
**discovery launch** (mine): enumerate the live actors and find the NPC transform offset + AI-freeze
flag. Then:
- we pick a donor NPC, drive its transform to the peer position → **a body appears at your friend's
  spot** (rough: stock NPC model, likely sliding — a proof, not a pretty avatar).
- after that, the "spawn a real Shay" route (B) is the long-term goal.

Send me the two logs (or the `peer=1` lines) after you test, and the discovery is the next step.
