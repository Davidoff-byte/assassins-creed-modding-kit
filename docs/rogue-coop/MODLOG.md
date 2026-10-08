# MODLOG — AccCoop (Assassin's Creed Rogue co-op)

## 2026-10-04 — recon + plan + M1

### Context
- Builds on the existing `AC.PatchFix` plugin work (see `..\MODLOG.md`, `..\HANDOFF.md`) and mirrors
  the method used for the Dishonored co-op RE (`C:\Users\Administrator\dishonored-coop-re`) and the
  DoI→DS3 passthrough (`..\doi-ds3-passthrough`).

### Recon findings
- `ACC.exe` x64, no anti-cheat, engine codename **scimitar** (AnvilNext).
- **No gameplay netcode.** All `*Online*` strings are Ubisoft OSDK/Uplay; "Desynchronization" is
  AC's mission-fail. `NetSessionManager` / `StreamingInstallMultiplayerAvailableEvent` are type
  names with no code xrefs. ⇒ co-op must be synthesised, not unlocked.
- Spawn machinery present: `SpawnEntityOperator(Data)`, `UnSpawnEntityOperator(Data)`,
  `GetCharacterEntityOperator(Data)`, `AnimatedEntityComponent`, `RigidBodyComponent` — the route to
  a remote avatar.
- Camera anchors: `CAMERA_MANAGER_LOAD`, `CAMERA_INTERPOLATE` (already in `AC.PatchFix` scan table),
  `Ai::UpdateCamera` / `AdjustCameraAfterPhysics` strings.
- Player offsets known from prior RE: `player+0x218` (fight type), `player+0xaf8` (state).

### Decisions
- Route: **state-sync co-op** — ASI plugin reads local player transform, sends 64-byte UDP packets,
  drives a remote avatar at the peer transform. Ghost co-op (per-client world/AI).
- Protocol locked as a 64-byte LE datagram in `common/coop_proto.h`.

### Scope revision (user clarification, same day)
User wants **shared-world co-op** (not ghost): one world + shared AI, mirrored kills, shared ships,
board/sail together, join over **LAN via Radmin VPN**. Plan rewritten to a staged,
host-authoritative **replication layer**; Black Flag's `AC4BFMP.exe` is now the required reference
implementation (Rogue = Black Flag minus the MP binary; both confirmed separate exes).
- Architecture staged: S1 avatars → S2 event sync (kills) → S3 NPC correction → S4 ships → S5 world.
- Critical path flagged: the **entity identity problem** (agreeing which NPC is NPC X across machines).
- Engine anchors found: AI world tick `FUN_14010f850`, physics pipeline `FUN_1402b4840`, camera
  `FUN_1400d53b0` (manager global already pattern-resolved), graphics world `FUN_1405d4320`.

### M1 — protocol + oracle (DONE)
- `common/coop_proto.h`: envelope (16 B) + three payloads — Player (64 B), EntitySnapshot (24 B +
  28 B/entity), Event (28 B) — plus flags and event kinds.
- `tools/fake_peer.py` round-trips all three and runs a real-socket loopback. Latest run:
  `player 64 B / entities 136 B / event 28 B / simulated stream 160 msgs / loopback 4/4`.

### Next (M2)
- [in progress] Decompiled the four per-frame registrars → found the engine is a **task-graph
  scheduler** and mapped the real task functions (`Ai::UpdateCamera=FUN_1403664e0`,
  `Ai::SpawningManagerUpdate=FUN_14046b6f0`, `Ai::AIUpdate=FUN_140107450`, …). See `RE-NOTES.md`.
- [done] Decompiled the camera internals: **`DAT_14329dd08` = camera manager**; live camera
  world **position** at `manager+0xF0+i*0x10` and **quaternion** at `manager+0x140+i*0x10`, index
  `i=(*(u32)(manager+0x190)+5)%5`. Hook signatures captured for `Ai::UpdateCamera`,
  `Ai::AdjustCameraAfterPhysics`, `Ai::AIUpdate`, `Ai::SpawningManagerUpdate`. (RE-NOTES §6.)
- [done] Implemented the M2 hook: scan entry `AI_UPDATE_CAMERA` in `game_data.hpp`; new
  `hooks/player_transform.{hpp,cpp}`; registered as `PlayerTransformHook`. Read-only `MidHook` on
  `Ai::UpdateCamera`; resolves the camera-manager global from `fn+0x1D`; samples pos+quat every
  frame and logs at `[PlayerTransform] LogHz` (default 2 Hz). `[Hooks] PlayerTransform=0` disables.
- [done] **Builds**: MSVC Release → `build-msvc\bin\Release\AC.Rogue.PatchFix.asi` (1,270,272 B,
  13 hooks). Strings `PlayerTransform` / `AI_UPDATE_CAMERA` verified present.
- [done] **M2 verified in game.** `Pattern AI_UPDATE_CAMERA: 0x1403664E0`,
  `camera manager slot 0x14329DD08`, `PlayerTransform: installed`, and live
  `PlayerTransform: pos=(...) quat=(...)` lines that track movement.
- [done] **M3 verified, single machine (loopback).** `CoopNet: udp/27701 -> 127.0.0.1:27700`, and the
  Python oracle received **3,847 packets** (seq 1..3847) over one play session: 1,474 distinct
  positions, x −15→1085, y −15→443, z 0→101, with smooth per-frame deltas during gameplay
  (e.g. packets 1860–1874 walk x 1068.9→1070.9 at ~20 Hz, quat interpolating as the player turns).
  Flat stretches correspond to menus/cutscenes/loading. This is plan stage S1's data path, proven.

### Gotchas (each cost one launch/analysis)
- Pattern wildcard is a **single `?` per byte** — `??` parses as two bytes and matches nothing (this
  silently skipped `PlayerTransform` on the first launch).
- PowerShell `>` / `*>` redirect writes **UTF-16**; read the capture with `encoding="utf-16"` (or use
  `Out-File -Encoding utf8`). A UTF-8 read shows null bytes and 0 matches.
- The sampled transform is the **camera** (≈ the player + a 3rd-person offset), not the body/feet.
  Good enough to prove the path and to place a first avatar; the feet transform is a later refinement.

## 2026-10-04 evening — Black Flag installed; BF netcode RE + S1/A3 rig

### Black Flag (`AC4BFMP.exe`, x86) — netcode architecture (recovered from strings)
- Engine module: `scimitar/engine/gamenet/replication/netproxy.cpp` + `netproxyclass.cpp`;
  also `assassin2/gamenet/geospace.cpp`, `netstaticobjectspace.cpp`.
- Classes: **`NetPlayer`**, **`NetPlayerActionHistoryManager`**, `NetSoundReplicator`.
- Wire model is **master/replica**: opcode prefixes `M2R_` (master→replica), `R2M_`,
  plus `S2C_`/`C2S_`/`M2A_`/`A2M_`.
- It replicates exactly what S1 needs: **movement** (`S2C_SetMoveReplicationMode`),
  **custom action state** (`M2R_ReplicateEnterCustomActionState` / `...Exit...`), and
  **ledge transitions** (`S2C_TransitionToLedgeClimb`, `R2M_ForceLedgeRelease`).
- Has `extrapolation_filter`, `Interpolator`, `Interpolator2`, `PickableInterpolationData`.
- **BFMP is 32-bit and arena-only** (zero campaign-location strings); `AC4BFSP.exe` has the world
  but **zero netcode**. ⇒ BF is a design reference only; free-roam co-op is the same problem in both.

### Rogue has the engine systems BF replicated (but no net layer)
- `BaseCustomActionPack`, `CustomActionEvent`, `CustomActionEventSeed`, `CustomActionTests`.
- `FreeRunTargetingMagnetComponent`, `FreeRunCornerTurnComponent` (parkour).
⇒ our job is to **hook the player's Move + its CustomActionState** and ship them, mirroring BF's design.

### S1/A3 — playback/interpolation rig (offline, DONE)
- `tools/playback_rig.py` replays a capture at render rate: naive (latest snapshot) vs interpolated
  (render 100 ms in the past; extrapolate ≤150 ms on loss), with optional loss/jitter.
- Clean walking window (packets 1850:2100): jerk **naive 43.3 → interp 6.6 (6.5× smoother)**.
- 10% loss + 30 ms jitter: **78.0 → 42.0 (1.9×)**, freezes capped at 6 frames vs 16.
- Design rule found: captures contain **scene-transition teleports** (menu↔gameplay jumps of ~1000 u)
  which the interpolator must **snap/suppress**, or it drags the avatar across the map.

### State
- M2 + M3 verified in game. Deployed plugin = our build with `PlayerTransform` + `CoopNet`;
  `[Coop] Enabled=false` (inert). Pre-coop plugin backed up at
  `plugins\_backup_stock\AC.Rogue.PatchFix.pre-coop-20261004-182727.asi`. Listener stopped.
- Black Flag installed at `D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag`;
  `AC4BFMP.exe` analyzing in Ghidra (project `C:\Users\Administrator\ghidra-bf\AC4BFMP`).
- Resume: mine BF replication fields (`NetPlayer` move + `CustomActionState`) → map to Rogue
  (`Ai::SpawningManagerUpdate` `FUN_14046b6f0`, `Ai::AIUpdate` `FUN_140107450`) → A1/A4/A5.
- Queued (BF-independent): two-machine Radmin test; player-**body** (feet) transform; unit calibration.

## 2026-10-04 (cont.) — S1/A1 DONE: player **body** position read + broadcast, in game

- **Deterministic addressing.** `PlayerTransform` now resolves from the **module base + fixed RVAs**
  (no pattern scan), so it always installs — the scanner was inconsistent on an *unchanged* exe
  (it even took down `SET_FIGHT_TYPE`/`SET_WEAPON_POSE` that launch):
  - hook `0x3664E0` (`Ai::UpdateCamera`), camera manager slot `0x329DD08`,
  - player getters `0x352C10` (`index`) / `0x346AA0` (`object by index`) / `0x0D8600` (`PlayerPosition`),
  - ready-gate slot `0x32DE460`.
- **Body read** = the engine's own PlayerPosition path (call the getters, then read the three floats
  at `ps+0x30`). **Every pointer is validated with `VirtualQuery` before dereferencing** — a fault
  permanently disables the callback (it bit us twice), so this matters.
- **VERIFIED in game:** `PlayerTransform: BODY=(1049.0,424.6,19.0)` → `(1061.2,424.8,11.4)` tracking a
  walk + climb-down/up, a small steady offset behind `cam`; the UDP stream carries the same body
  positions. No crash.
- Next: body **orientation** (yaw) — we still send the camera quat — and the **movement/pose state**
  (`FUN_1410231c0`) for parkour animations (A5); then the **remote avatar** (A4).

### A5 — movement state (hardened, speed-derived)

- The engine's own movement-state accessor (`FUN_1410231c0`'s chain: `FUN_140103f90` + two virtual
  calls + `FUN_1401a5590`) is **crash-prone from a hook** — it calls virtual methods on engine objects
  that can be freed between our read and the call. Symptom: `PlayerState: move=-1 stage=4 …` then a
  fault → permanently disabled. **Removed the hook** (files deleted; not in `AllHooks`).
- `PlayerTransform` now derives locomotion from the **body's own speed** (safe: no engine calls) and
  packs it into the packet's `anim_state`: `0 idle, 1 walk, 2 jog, 3 sprint`.
- **VERIFIED:** standing → `speed=0.0 state=0`; moving → `speed=3–7 state=2`. No crash.
- **Known gaps (honest):** walk/jog/sprint thresholds need calibration; **climb is not detected** —
  a real parkour state needs the engine's accessor called where the object is guaranteed live
  (hook the engine's own call site), which is a follow-up.

## 2026-10-04 (cont.) — protocol v2 (quaternion) + CoopNet (M3 plugin side)

### Protocol v2
- Player packet now carries the engine's **native orientation quaternion** instead of Euler angles:
  `px,py,pz, qx,qy,qz,qw, vx,vy,vz, health, anim, tick, ack` = 56 B payload + 16 B envelope = **72 B**.
- `acc-coop/common/coop_proto.h`, `acc-coop/tools/fake_peer.py`, and the plugin copy
  `coop_proto.hpp` are in lockstep; oracle re-run: `player 72 B / entities 136 B / event 28 B /
  stream 160 / loopback 4/4` all green.

### CoopNet (plugin-side M3)
- `games/ac/rogue/coop/coop_net.{hpp,cpp}`: non-blocking UDP over loopback/LAN. `configure()` binds
  `LocalPort` and resolves the peer; `publish()` sends the 72 B player packet at `SendHz`;
  `poll()` drains up to 16 datagrams and keeps `latest_remote()`.
- Wired into the `PlayerTransform` callback (game thread): samples → `publish()` → `poll()`; the log
  line now appends `| peer[N]=(x,y,z)` when a peer is heard.
- Config (all under `[Coop]`, hook `[Hooks] PlayerTransform=1`): `Enabled` (default **false** —
  no socket unless asked), `RemoteIp1..4` (an `ini_field` can't hold a string, so the peer address
  is four octets; Radmin VPN is typically `26.x.x.x`), `RemotePort`, `LocalPort`, `ClientId`,
  `SendHz`.
- **Builds**: `.asi` = 1,282,560 B; strings `CoopNet: udp/`, `RemoteIp1`, `PlayerTransform: installed`
  present, `ws2_32.dll` imported.
- [ ] Two-client test (needs the user + Radmin): set the peer octets on each machine, confirm each
  logs the other's position. This is the first half of plan stage S1.

### Gotcha (cost one launch)
- The pattern scanner's wildcard is a **single `?` per byte**. Writing `??` makes the parser read
  *two* wildcard bytes, so the signature becomes too long and matches nothing:
  `Pattern AI_UPDATE_CAMERA: NOT FOUND (found 0)` → the hook is skipped and the whole feature is a
  silent no-op. All existing signatures use `? ? ? ?`. Fixed in `game_data.hpp`; rebuild verified.
  (First launch with the fix pending was otherwise clean: 10/13 hooks installed, `PlayerTransform`
  correctly reported "missing required patterns, skipping" — the diagnosis path worked.)

## Pause 2026-10-04 (late) — S1 data layer done; A4 research next

Session summary:
- **A1 (player body position): DONE** — engine's own PlayerPosition path, RVA-addressed, crash-safe
  (`VirtualQuery` guards), verified in game, streamed over UDP.
- **A5 (locomotion): done, safe** — speed-derived `idle/walk/jog/sprint` in `anim_state`; native
  parkour/climb state not yet (that engine accessor is crash-prone from a hook).
- **Black Flag netcode design decoded** (master/replica; Move + CustomActionState) — RE-NOTES §8.
- **A4 (remote avatar): mapped, hard** — actor enumeration `FUN_140100530`, spawn manager
  `FUN_14046b6f0`; spawn types have no code xrefs. See RE-NOTES §9.

Deployed: our build with `PlayerTransform` (RVA + crash-safe) + `CoopNet`; `[Coop] Enabled=true` →
loopback. Next (research, no launches): BF MP avatar/spawn system + Rogue actor/spawn internals, then
implement hijack-NPC or spawn.

## 2026-10-04 (late) — A4 Route A attempt: plumbing works, transform field wrong

- Implemented `PlayerProbe` (actor enumeration): found the player actor in **partition 1**, world
  position at **`actor+0x800`** (second copy at `+0x854`).
- Implemented `HijackAvatar`: each frame, write the peer's position to a donor actor's `+0x800`.
  **Verified**: 78–152 writes tracking a spoofed peer over UDP (`donor=0x852CE5E0 -> peer=(…)`).
- **Negative:** no visible body, even with the donor driven to the player's own position (self-loop).
  ⇒ `+0x800` is a cached/derived field, or the donor isn't visible. The **rendered** transform is
  elsewhere (move component / matrix).
- Next: find the move/render transform (extend the probe to report all matching offsets; try the move
  component) and pick a visible human donor. Full write-up: `A4-RESEARCH.md` §7.
- Package for the friend test is ready: `dist/` (position link; hijack disabled) + `TWO-MACHINE-TEST.md`.

## 2026-10-05 — scope locked S1–S3; build reconciled; **A4 Route C found**

User directive: **focus on S1–S3** (see each other → mirrored kills → NPC correction).

### Build drift fixed (we can rebuild the co-op plugin again)
The co-op hooks had been moved to `ac-rogue\excluded-hooks\` for the shipped single-sword mod, so
`registry.hpp` could no longer reproduce `dist\AC.Rogue.PatchFix.asi`. Restored into the build tree:
- headers + sources: `player_transform`, `player_probe`, `hijack_avatar` (hooks) and `coop_net.cpp`.
- `registry.hpp`: added the three co-op hooks (+ `DebugSpawn`, below). The parked combat hooks
  (`counter_*`, `combat_tweaks`, `ai_pacing`, `knife_*`) stay excluded.
- Build: MSVC Release → `build-msvc\bin\Release\AC.Rogue.PatchFix.asi` = **1,317,888 B**; strings
  confirm `PlayerTransform`, `CoopNet`, `PlayerProbe`, `HijackAvatar`, `DebugSpawn`, `ws2_32.dll`.
  A new `*.cpp` needs a `cmake -S -B` reconfigure (CONFIGURE_DEPENDS didn't re-glob for the link).

### A4 breakthrough — the retail exe has a callable **debug-cheat** system
Full detail in `RE-NOTES.md` §10. Highlights:
- **Spawn handlers**: `Spawn Follow Dude` = `FUN_141e91d50`/RVA **0x1E91D50** (also RedBall/Still/Fight/
  Ship Dude). Shape: `dude = FUN_141e852c0(); *(u32*)(dude+0x30)=type; FUN_14016e190(dude, FUN_1400ed780());`
- **Set-world-transform API**: `FUN_141eab190(char)` → interface id 0xD on `*(char+0x20)` component,
  `vfunc+0x30(iface, mtx4x4)`. Matrix built by `FUN_141eaaf30`.
- **Explains the old dead end**: `char+0x800`/`+0x811` is the **ghost-mode saved-position slot**, not
  the render transform — so writing a donor's `+0x800` was never going to move a body.
- **S2 lead**: entities carry a **64-bit id/hash** (`…ID:0x%08llX`)) — best cross-machine identity key.

### Shipped probe: `DebugSpawn`
New hook `hooks/debug_spawn.{hpp,cpp}`: MidHook on `Ai::SpawningManagerUpdate` (0x46B6F0); with
`[DebugSpawn] Enabled=true`, once the player-ready gate (0x32DE460) is set it calls
`FUN_141e91d50(1)` (Spawn Follow Dude) and logs the debug-dude array (`DAT_14329def0`, count at
`DAT_14329def8`). Default **OFF**. **In-game oracle:** a second (follower) body appears near Shay.

### Next
1. Deploy this build and enable `[DebugSpawn] Enabled=true`; confirm the follower body (S1: a second
   character exists) — no crash.
2. Find the spawned dude's **character entity** + component (`+0x20`), then drive its transform to the
   remote position each frame via the interface-0xD set-transform (matrix from peer pos+yaw).
3. Two-machine link test (`TWO-MACHINE-TEST.md`) — needs the user + Radmin.
4. S2: pin the 64-bit entity id and add a stable key to the `Event` message.

## 2026-10-05 (cont.) — first deploy + spawn probe: the call works; launch wedged

- Deployed the co-op+`DebugSpawn` build to `D:\...\plugins\` (backup:
  `plugins\_backup_stock\AC.Rogue.PatchFix.pre-debugspawn-20261005-221446.*`); ini set to
  `[Hooks] DebugSpawn=true` + `[DebugSpawn] Enabled=true`, `[Coop] Enabled=false`,
  `PlayerTransform=true`. Environment was clean (no ReShade/Bandicam/Fraps, no stray ACC).
- **First launch (pid 4136) was OK.** Plugin loaded, hooks installed, and once the ready gate was set
  the probe ran `FUN_141e91d50(1)`; `DebugSpawn: spawned=true …` persisted across frames with **no
  crash**. ⇒ the debug-spawn call (RVA 0x1E91D50) is safe to invoke from a hook from a live process.
  We were still at the menu (`PlayerTransform: body=BAD guard=1 idx=0 base=0x0`), so no body yet — the
  menu-time ready-gate is not "in-game".
- Hardened the probe: spawn is now gated on a **valid player body** (in-game), re-arms on scene
  change, and logs the debug-dude count delta (`… dudes N -> N+1`). Rebuilt = 1,319,424 B, redeployed.
- **Relaunch wedged.** ACC.exe (pid 14824) came up as a 1-thread, windowless, **unkillable zombie**;
  the plugin log froze at pattern resolution — *before any hook install*, so this is **not** the new
  code. No fresh crash dump (`Stop-Process`, `taskkill /F /T`, `um win kill` all fail: "no running
  instance"). Same class as the existing gotcha: a wedged `ACC.exe` clears only on reboot.
- **Next:** reboot → launch once → load into gameplay. Expect `DebugSpawn: … dudes N -> N+1` and a
  follower body near Shay (S1: a second engine character exists). Note the debug-dude count field is
  the **high** u16 of `DAT_14329def8` (low 14 bits are capacity).

## 2026-10-05 (cont.2) — combined probe: **both A4 routes blocked**

Deployed combined build (1,323,008 B): `DebugSpawn` (fixed — one pass per level, debounced; `Kind`
selects Follow/RedBall/Still/Fight; correct manager count) + extended `PlayerProbe` (now walks the
actor component array at `+0x3b0` and the `+0xc0` context). 16/16 hooks installed, no crash, spawn
fired exactly once (debounce works).

### Result 1 — the debug spawn creates only **transient, non-rendered** objects
All four handlers ran; manager count went `1 -> 5` (`FUN_14016b0d0` appends to the `DAT_14329de70`
list, count at `+0x0A`). Within 1 s the count fell back to 1/0 — the manager **consumes/removes them
every frame**. The "dudes" are per-frame debug markers (ghost-camera helpers), **not persistent
characters**. ⇒ Route C is a **dead end for a visible avatar.**

### Result 2 — actor-by-position scan now finds **nothing**
`PlayerProbe: player=(-175.4,71.5,12.1) actors=37 matches=0` on every tick: none of the 37
AI-partition actors (nor their `+0x3b0` components / `+0xc0` context, first 0x400 B each) contains the
player's world triple. Most likely the **player is not an AI actor**, so the player position cannot be
used as ground truth to locate it. The earlier `+0x800` "match" (A4-RESEARCH §7) was the ghost
saved-position slot, not a live transform. ⇒ the old "find the actor by position, then write it"
premise is invalid.

### Remaining options for the A4 gate (untried)
1. **Capture-and-replay spawn**: hook the NPC spawn helpers (`FUN_14045c560` / `FUN_140465c20`) or
   Gear create (`FUN_1400c8c40`) to capture a **real spawned character pointer**, then position it
   with the known set-transform API: `comp = *(char+0x20)`; `iface = (*comp->vt[0x90])(comp,0xD)`;
   `iface->vt[0x30](iface, mtx4x4)`. No full descriptor understanding needed.
2. **Self-test the set-transform API on the player** — cheapest way to validate the matrix call.
3. **Renderer-first**: find the character Draw/submit path and the transform it reads; definitive but
   heavier.

## 2026-10-05 (cont.3) — transform write-path: what the engine gives us

Recon on the decompile (`gamedb`, no game) into how to set a character's world transform:

- **The write-path is the interface-0xD call.** The engine's own teleport (`FUN_141eab190`) does:
  `comp = *(char+0x20)` → `iface = (*comp->vt[0x90])(comp, 0xD)` → `vt+0x28(iface, mtx4x4)`
  (validate) → `vt+0x30(iface, mtx4x4)` (apply) → optional `vt+0x48`/`vt+0x50`. A valid 4×4 can be
  produced by the engine's own builder `FUN_141eaaf30(char, mtx)`; its translation sits at `mtx+0x30`.
  So **the mechanism to place a character exists and is small**; the missing input is a **character
  pointer** (`char`) whose `+0x20` component implements interface 0xD.
- **The AI navigation/steering task functions are not name-locatable** (every symbol is `FUN_`; the
  registrar stores fn pointers in node fields with no clean mapping). The spawn helper
  `FUN_14045c560` is a large opaque function; `FUN_1400c8c40(world, desc, cb)` is a thin wrapper over
  `FUN_1400c8740(DAT_143299fd0, …)` (Gear create) — usable for capture-and-replay only with more RE.
- **The player object is a character** whose transform is reachable: `FUN_1400d8600(player)` →
  `player+0x70` → `FUN_1402892d0(player)` → `FUN_1401a7a40(*(*(player+0xd10)+8))`. So the player is a
  valid host for the set-transform self-test.

### Conclusion / next probe
The avatar needs (a) a character pointer and (b) a matrix. We have the matrix path and a candidate
character (the player). The **cheapest decisive test** is a crash-isolated self-test: on the player,
call the interface-0xD set-transform with a matrix from `FUN_141eaaf30(player,…)` nudged by a few
units — if Shay moves, the API + matrix are validated, and we then only need to obtain a *second*
character pointer (capture a spawn). Expect this probe to need a couple of iterations (virtual calls
from a hook are the known crash class).

## 2026-10-05 (cont.4) — set-transform self-test round 1 + the launch wedge (again)

- Added `SetTransform` (hook on `Ai::UpdateCamera`). Round 1 targeted the **player object**
  (`FUN_140346aa0`): discovery logged `player+0x20 = 0x3F7F069D3DB27E7C` — **two floats, not a
  pointer** — so the player object is **not** the teleport's `char`. The guarded call then faulted;
  the framework caught it and **disabled only that hook — the game survived** (crash isolation works
  exactly as designed). ⇒ target an **actor** instead: actors carry `+0x800`, matching `char+0x800`.
- Round 2 (build **1,339,904 B**) retargets the self-test at an **AI partition-1 actor**: logs
  `actor+0x20` and `actor+0x800`, then builds an identity matrix (translation = player body pos) and
  applies it through the interface-0xD path (`vt+0x28` validate → `vt+0x30` set).
- **The launch wedge recurred** (2nd time). After a quit→relaunch, `ACC.exe` came up as a 1-thread,
  windowless, **unkillable zombie**; the plugin log froze during init, *before any hook install*
  (⇒ not the mod). `Stop-Process` / `taskkill /F /T` all fail ("no running instance"). Only a
  **reboot** clears it. Operational rule: relaunch only once the previous `ACC.exe` is fully gone, and
  prefer one launch per boot; design tests to be maximally informative in that single launch.

## 2026-10-05 (cont.5) — actor self-test: actors are **not** the teleport `char` either

In-world (BODY tracked, `BODY=(-211.6,46.8,11.1)`). `SetTransform` discovery on an AI partition-1 actor:

```
actor=0x73FC6AE0  comp(+0x20)=0x11896  pos(+0x800)=(0,0,0)
```

- `actor+0x20` is a small integer — **not a component pointer** — and `actor+0x800` is zero.
- ⇒ actors are **not** the teleport's `char`. All three candidate host objects are now disproven:
  - player object (`FUN_140346aa0`): `+0x20` = floats;
  - AI partition actor: `+0x20` = `0x11896`, `+0x800` = 0;
  - the teleport's `char` (which has a real `+0x20` component and `+0x800`) is a **separate object**,
    most likely a cheat/debug-only character wrapper we have not located.
- Minor bug: the guarded transform block never fired (`transformed=false`) — the probe's
  `g_in_game_since`/`g_transformed` are plain (non-atomic) and the AI callback may be multi-threaded.
  Moot now, but make such state atomic next time.
- **Conclusion:** the interface-0xD set-transform path is real (the engine's own teleport uses it),
  but we have not found any object that exposes it. Next: locate the class that owns `+0x800`/`+0x811`
  (find its constructor/allocation) or trace the character render transform directly. This is a
  deeper RE task; the cheap object guesses are exhausted.

## 2026-10-05 (cont.6) — deep-RE: the teleport `char` is a **debug wrapper**, not a world character

Tracing the object that exposes `+0x800`/`+0x811`:

- It is a **~0x900-byte object** with `+0x18` → object whose `+0x70` → `+0xe18` (a world/physics
  sub-object), `+0x20` = a component (its own method reads `*(*(char+0x20)+0x1e8)`), `+0x800`
  (saved position), `+0x811` (flag), plus manager fields at `+0x808/+0x840/+0x898/+0x7e8/...`.
- Its per-frame updater `FUN_141ea2430` calls `FUN_141e9fb80` (clears the ghost flag) and has **no
  static callers** (invoked indirectly / via vtable) — the signature of a **debug-menu subsystem
  class**, not a normal character.
- The "Character to Teleport" menu parameter is a separate large debug-menu object
  (`FUN_141e264b0`, vtable `PTR_FUN_142acb2c0`).
- ⇒ The interface-0xD set-transform path is **scoped to the debug/cheat character wrapper**; it is
  **not demonstrably usable on normal NPCs**. The general character transform/spawn is still
  unlocated.

### Next (desk RE)
Find the **general** character transform, not the debug wrapper:
1. Scan AI-actor **component vtables** across actors (component array at actor+0x3b0) and identify the
   move/transform component by shared vtable identity (read-only, no game if we can pick a known
   actor type).
2. Or trace the **renderer**: find the character draw/submit path and the transform it reads.
3. Or the **physics** path (`Physic::AfterSimulation`, "Pinocchio") which writes final transforms.

## 2026-10-05 (cont.7) — near-player component scan: only a constant component found

Extended `PlayerProbe` to scan **every** actor's components (`actor+0x3b0`) for a float triple within
250 units of the player (ground truth for nearby NPCs), tagged with the component's vtable. In-game,
standing among NPCs:

- 210 `NEAR` hits, **all from one component type**: `vt=0x142397720`, `compIdx=0`, offsets 0/4/8,
  values `(46.4,0,0) / (0,0,0) / (0,0,64)` — i.e. **constant data present on every actor**, not a
  transform. (The 250-unit radius was too loose: the player was at x≈-169 and 46 is ~229 away.)
- **No component held a triple in the player's coordinate range** (none with x in -260..-80, where a
  nearby NPC's x would be).
- ⇒ This heuristic does **not** find the general character transform. Either the transform is not a
  plain float triple in the first 0x200 B of these components, or `actor+0x3b0` is not the component
  list we assumed.
- **Conclusion:** locating the general transform needs a **renderer trace** (find the character
  draw/submit path and the transform it reads) or a proper component-system RE — a larger effort.
- S1 status unchanged: transform + transport proven; remote avatar unsolved.







