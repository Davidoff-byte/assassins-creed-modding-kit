# BFCoop — reverse-engineering notes

Reverse-engineering notes for Black Flag co-op. Two binaries:
- **`AC4BFSP.exe`** — single-player/campaign (our target to mod).
- **`AC4BFMP.exe`** — multiplayer (the oracle: it already networks an AnvilNext avatar).

Base addresses: both are x86, image base `0x400000` (confirmed in-game).

> **CURRENT TRUTH (2026-10-07) — read this first.** The numbered sections below are the
> chronological research log; where they disagree with this box, this box wins.
>
> **THE BIG PICTURE (2026-10-07 full review, after the spawn-system RE + full game-data extraction):**
> The co-op = **host-authoritative two instances** (the SP engine has NO netcode; a true hosted
> world = an engine rewrite and is OUT OF SCOPE — be honest about this in every plan).
> The player-avatar chain: READ+NETWORK = done (two machines live); BODY = the open problem
> (below); LOOK = mod pipeline proven; MARKER = not started; ANIMATIONS = read done, play pending;
> KILL-SYNC = design only; SHIPS = later.
>
> **BODY — the open problem (the "haunting").** The hijacked crowd body is visible but
> UNSATISFIABLE: streamed/culled when its home cell unloads ("GhostBody: body lost, rescanning"),
> its AI fights the driver between packets, and it re-picks -> the partner "teleports between
> strangers". **Persist-hijack = the leading fix hypothesis:** detach a hijacked body from the
> world's streaming/cull registration so it survives and can be driven permanently.
> Supporting data: nodes are scene-registered (marker `+0x68` = 0x04DD5F8C, `+0xC8` = same
> constant, `+0xE8` = controller link) and bodies ARE lost on streaming.
> UNPROVEN: WHICH system frees them (entity registry by key? septum? refcount?) — the pin-down
> experiment (watch a body die across a cell unload) = the next live test.
>
> **RUNTIME ENTITY CREATION = CLOSED (engine constraint, proven by ~6 approaches + freezes).**
> The engine creates characters only during world loads; mid-game creation chokes the renderer
> (audio-continues freezes). The spawn system itself IS fully mapped (below) — the wall is
> render/scene registration timing, not our understanding. Do NOT retry non-load-time creation.
>
> **THE SPAWN SYSTEM (fully mapped 2026-10-07 — keep, it explains everything):**
>  - Class ids = CRC32 of names: `crc32("Entity")=0x0984415E` (full-body class, vt 0x1E4CE90),
>    `crc32("EntityGroup")=0x3F742D26`, `crc32("ManagedObject")=0xBB96607D`, plus SaveGame /
>    MissionHistory. Other live classes (0x9467F2BB etc.) = registered ids, not simple name CRCs.
>  - Mass creator `FUN_00a201a0(classId, keyLo, keyHi, 0)` (RVA 0x6201A0): class resolve
>    (FUN_00a33f00) + find-or-create by key (FUN_00a1f160) + instantiate (FUN_00a359c0 =
>    alloc FUN_004061f0 + ctor at descriptor+0x30 + keyed registration
>    FUN_00a20230/FUN_00a20f40 ONLY when the key pair is non-zero). Engine's own census:
>    `Entity` keys = (32-bit world hash, block index 7/8); the 246x-dominant class uses (0,0).
>    Live bodies (children 19-32, f7c=-0.50) = `Entity`-class instances. `FUN_005fd730(group,hash)`
>    = the PARTS spawner (children 1-11) — NOT the character spawner. Zero/fake keys = valid but
>    EMPTY unregistered bodies.
>  - **The captured ids (0x462A56BC etc.) are RUNTIME keys, not name hashes** (108M+ string tests:
>    63M forge TOC names + 45M content strings + exe strings + variants = ZERO matches; the
>    hash-reverse hunt is CLOSED).
>
> **2026-10-08 UPDATE — the clone/duplicate arc (supersedes parts of "CREATION = CLOSED"):**
>  - **Class map nailed** by full-memory class-id resolution: vt `0x1E4CE90` = class **"Entity"**
>    (`0x0984415E`) — 2788 instances = ALL body nodes INCLUDING the player's own (find_player_ctl's
>    node). vt `0x1E4A128` = **"EntityGroup"** (`0x3F742D26`) — the old "character candidates"
>    were EntityGroups (their +0xC = FUN_00503600 deep copy; calling it as a clone = the historic
>    AVs). vt `0x1E64680` = class `0x2F4222CA` with the COMPLETE clone (sync FUN_006deff0 / async
>    FUN_006def40) — **no live instances** (decoy/mission-only).
>  - **The node clone** = `Entity vtable+0xC = FUN_0052A980` (instantiate via desc 0x275E670 +
>    recursive child clone FUN_00a27550 + job post 0x27F6A44). LIVE-PROVEN: returns a real node
>    on crowd bodies (rc=0, stable 10 s+); AVs on stale ones and on the PLAYER's node.
>    **The copy is INVISIBLE: a raw node copy has NO GRAPHICS** — the visual is built at spawn by
>    the graphic-instance factory (the parked outfit path). Unregistered copies also get freed by
>    the engine eventually (the pin tech exists to prevent that).
>  - **Streamer spawn** `FUN_005FD730(hash)` decoded: fast path = template-handle poll; slow path
>    = clone-the-template (vt+0xC) + activate (`FUN_00526590` flags+spatial) + flush
>    (`FUN_00a2e820`). Calls with our hashes return 0 (template-handle validity fails at call
>    time); SpawnWatch captures live per-area template hashes (e.g. 0x47CD5ECC, 0x479DB35C).
>  - **THE QUEUED TEST (built, not yet run)** — the ASYNC clone (`Entity vt+0x8` = serialize +
>    engine-side deserialize = the documented render-safe path). Shipped as CloneLive v5
>    (non-player sources get a +3 m offset spot trick; post-scan finds the copy; move+activate+
>    flush). Procedure: close game -> deploy latest `build-x86` asi -> in-world -> CloneLive=true.
>  - **Freeze fix shipped 2026-10-08:** the act-controller rescan stalled the game ~3 s every
>    ~10 s (and scan-stormed at menus — likely behind the recurring nvwgf2um driver crashes).
>    Fixed (no periodic rescans + 3-20 s backoff + two-pass scan). User-verified: "game feels fine".
>  - **Live verdict 2026-10-08 ~19:01 (build 3B713A6D, live game):** all three clone rungs x 10 candidates:
>    player body = all fail; 9/10 crowd bodies = all fail (SYNCCLONE/DEEPCOPY rc=1 = SEH, ASYNC AV);
>    ONE success -> object vt `0x1E64680` = **WorldEntityGroup** (name resolved) = a group CONTAINER;
>    persisted 105 s (not freed). Live memory dump vs source body: node fields copied, but graphic/scene
>    slots `+0xAC/+0xB0/+0xD4` = 0 and controller `+0xE8` = 0, `+0x50` = static default definition ->
>    **invisible shell; memory-copy CANNOT produce a rendered body.** Renderable bodies = engine spawn/
>    streamer pipeline only (same conclusion as Skyrim Together's design; see logs/ai/SKYRIM-TOGETHER-LESSONS.md).
>  - **SpawnTest replay ret=0 live:** replaying the engine's own (mgr, key-ptr) 2 min after capture fails
>    (transient key) -> next: capture key CONTENTS + args + caller RVA, replay a reconstructed key.
>  - **NavTest live:** picker's "speed" field = garbage (picked 211 m/s); attempts rc=3 (idle gate) ->
>    rc=0 (accept) -> no movement. Next: position-delta mover detection.
>  - Class names: `0x2F4222CA` = **WorldEntityGroup** (sync-clone class), `0x0984415E` = Entity,
>    `0x3F742D26` = EntityGroup, `0x406089A4` = Action. Behavior classes = non-CRC id scheme (mixed).
>
> **2026-10-09 UPDATE — the body problem solved differently: shells dead -> keyed characters -> forge reskin.**
>  - **Shell/adopt route CLOSED (falsified):** the world load only find-or-creates MISSING keys — a live
>    planted shell makes the load skip the key entirely (the sniper shell never got a single LOAD HIT
>    across a save load + round trip). Earlier "adoptions" were heap block reuse. Plant count also
>    destabilizes load-end (29 shells -> deterministic +0x4C10BA crash; <=8 survive). Do NOT retry planting.
>  - **Keyed persistent characters FOUND (the partner frame):** the Havana docks hold persistent keyed
>    NPCs rebuilt every load: key `(0xF00056E0,0)` -> entity `0x45B497A0` @ (111,-66); key `(0xF000570A,0)`
>    -> entity `0x460F4610` @ (109,-73). World key->entity registry walkable: find the 8-byte (lo,hi) pair,
>    entry base = pair-0xC = {ptr, rc, flags(0x8000000x), keyLo, keyHi}, stride 0x14.
>  - **Forge def-redirect = the ACTIVE route (user: "if we can write, we write"):** mod9 = mod7 +
>    `CHR_C_M_Spanish_Medium/Poors/Rich` (Havana street/dock folk) -> private copies of
>    **`CHR_P_EdwardKenway_Walpole`** (Edward in the Walpole-disguise robes; id-hash patched per target).
>    Deployed to the game (MD5 `C641619371A42C160E69C391C7F7E82F`), AdoptTest=false, relaunched.
>    Fallbacks in D:\bf4_mod: mod8 (same targets, Duncan source), mod7, pristine original.
>  - **Directive:** this is the big co-op addition (Skyrim Together scale) — keep writing forward.
>  - **SUPERSEDED (10-09):** dock folk were confirmed as Edward (mod15 keeper) and the full drive pipeline went
>    live end-to-end (peer -> handshake -> targeted pick -> despawn pin -> per-frame drive, err = 0.00 m).
>    The current open item is the crowd ANIMATION play side (update below).
>  - **2026-10-09 (evening) B4 play-side UPDATE - the two sides are different classes; walk-state regions + the state machine located.**
>    - Player vocabulary captured live (read-only v21 probes): run a=0x48 e=1 c=0x57; climb d=0x83/0x07; idle c=0x3F d=0x2A; request slots stay -1; 6-tuple surface confirmed (a->+0x8D4 blend, c->+0x8D8 hang, d->+0x8E0 phase, e/f bytes).
>    - The ghost (crowd class, vt 0x026E34D8) does NOT share the player layout at +0x8D0 (player = scalars; crowd = pointers/mixed - this is the crash RCA). Never value-copy between the classes.
>    - Read-only walk-vs-stand diff: 349 offsets change walking / 0 standing. Candidates: ctl+0x26E0.., ctl+0x28F0.. (double-buffered swap pairs in FUN_00d7e290), ent+0x74.., ent+0xB4/0xB8.
>    - Crash chain = the state machine: FUN_00513360 -> vt+0x94 -> FUN_00625D70 -> FUN_00750440 -> FUN_007437A0 = refcounted state-object swap at controller+0x2C (abs +0x8DC - the field the raw write clobbered).
>    - NEXT: read-only hooks on the swap chain + staging writers while a verified NPC walks; drive the ghost via the engine path only.
>
> **TOOLING (2026-10-07):** QuickBMS (`bf-coop/tools/bms/`) + `scimitar_alt.bms` (RetingencyPlan
> compendium) extracts AC4 forges; reimport2 verified (SAME-SIZE swaps only — the forge offset
> table is not rewritten; pad replacements to the exact slot length). ALL ~25 forges extracted to
> `D:\bf4_extract` (~90k named files; character forge fully named: CHR_U_*/CHR_G_*/CHR_C_*,
> incl. `CHR_G_M_Assassin`, `CHR_G_F_Assassin`, shared `CHR_U_Assassins_*` textures, all Tulum
> assassins). Mod pipeline proven end-to-end on `DataPC_extra_chr.forge` (backup:
> `D:\bf4_mod\backup`).
>
> **Read path (verified in-game).** Player feet + facing:
> `mgr = *(u32*)0x02ABE588` (RVA `0x026BE588`) -> `+0x4C` -> holder -> `camobj` -> `+0x68` -> block
> -> `+0x174` -> provider; **feet = provider+0x110 (vec3), quaternion = provider+0x100 (vec4)**.
> `block+0x50` is the camera-target eye = feet + ~1.2 m. The camera ring (`mgr+0x90` / `+0xE0`) is
> the camera, not the player.
>
> **The character node (the thing to write).** Class vtable `0x01E4CE90`, allocation **exactly 0x100
> bytes**. Fields: `+0x00` vtable, `+0x04` id (allocation counter), `+0x08` player-only pointer to an
> identity-matrix attachment, `+0x10` 4x4 matrix (**row 3 at `+0x40` = feet — write this to move the
> character**), `+0x50` flags, `+0x60` children-array pointer (**the rig**), `+0x66` child count,
> `+0x68` handle marker constant `0x04DD5F8C`, `+0x7C` exactly `-0.50` for humanoids, `+0xC8`/`+0xE8`
> per-character controller objects. **Nothing past `+0x100` belongs to this object** (earlier
> "self-node" and "+0x110 vtable" reads were neighbouring allocations — corrected).
>
> **Drivable, renderable bodies.** Class + marker + `f7c == -0.50` + **child count >= 16** (real
> crowd bodies 18-20; the player 27; inactive proxies 8-14 never render; markers = 1). Exclude
> anything within ~2.5 m of the local player. Pull a body from up to ~200 m to the target and write
> its matrix every frame; release (stop writing) when packets stop — its own AI takes over.
>
> **Verified end-to-end:** fake-peer UDP -> plugin picks a body -> drives it -> user watched an NPC
> circle them; the player-teleport write is also user-confirmed. **Two real machines (2026-10-06,
> Radmin VPN): LIVE** — `GhostBody: picked body 0x3784D1B0 at 61.5 m from peer` + `peer=1 body=1@...
> fresh=1 d=13.8..18.9`; both players saw each other's ghost in-game; the driven body **turns to match
> the peer** (**+Y forward convention confirmed live**). Tracking slightly choppy (20 Hz + ~105 ms +
> live crowd AI); peer climbing shows as a vertical teleport (no animation/parkour linkage yet).
> (See MODLOG, 2026-10-06.)
>
> **B4 action system (2026-10-06, decoded).** The player's actions are the **BhvAssassin** behavior
> (registered in the name registry FUN_00a1c970; family: BhvAssassin / BhvGenericNPC / BhvAnimal).
> Chain: dispatcher FUN_01af9f40 → update FUN_01ac1ad0 (applies the **request slots**
> `[owner+0x2F50..0x2F60]`, `-1` = unchanged, into the live fields) → FUN_01ab52c0 writes the live
> action struct on the behavior component in one burst: `+0x8D4` blend, `+0x8D8` hang (`0x3F`),
> `+0x8DC`, `+0x8E0` phase (`0x2A`=action, `0x07`=post-action), `+0x8E4`/`+0x8E5` bytes. Component
> resolved via FUN_013aec10(owner+4) (list base `+0x60`, count `+0x66`). Scripted actions override
> through FUN_00e0e5b0. The crowd counterpart (**the ghost's behavior**) is **BhvGenericNPC**
> (`0x026E2820`) — the next play-side target.
>
> **Open (2026-10-07):** (1) the persist-hijack mechanism — the ONE key experiment; (2) the ghost
> look — mod target hunt (pipeline proven; abandon the field-poke family, it is exhausted);
> (3) the partner marker/HUD (D3D overlay + world->screen projection); (4) the B4 play side
> (animations on the ghost body); (5) kill-sync events (host-authoritative, same-mission NPC
> matching); (6) ships (later).

## 1. BF MP oracle — the networked-avatar design (from `DecompBFMPOracle`)

### NetPlayer — the networked character class
- `FUN_004fd528(param1,param2)` **registers `NetPlayer`**: `DAT_01a1b678 = FUN_00c23e4e(param1,param2)`
  (a factory), stores the class id at `+4`, and names it with `FUN_00c18fb4("NetPlayer")`.
- `FUN_00699771` does the same for **`NetPlayerActionHistoryManager`** (`DAT_01a2241c`).
- So a networked avatar is a **registered object class** produced by a factory and identified by an
  id — the "entity identity" mechanism we need for cross-machine agreement.

### Movement replication is **field-by-field by offset**, with a priority
- `FUN_004bf90e` registers replicated fields via
  `FUN_00c2fdfc(obj, offA, offB, offC, priority, flag)`:

  | offA | offB | offC | priority | flag |
  |---|---|---|---|---|
  | `0x80`  | `0xa0`  | `0xc0`  | 1 | 0 |
  | `0xe8`  | `0xf4`  | `0x100` | 1 | 0 |
  | `0x128` | `0x138` | `0x148` | `0x7fffffff` | 1 |
  | `0x1f8` | `0x22c` | `0x260` | 2 | 0 |
  | `0x170` | `0x1a0` | `0x1d0` | `0x7fffffff` | 1 |

  ⇒ **These are the movement fields** (position/orientation/velocity) on the networked object. The
  two high-priority (`0x7fffffff`) ones are likely position + orientation.
- It then registers the messages: **`S2C_SetMoveReplicationMode`** (**the movement mode**),
  `C2S_SetSpawnState` (**spawn**), `OnSendToEntity`/`OnSendDecoyToEntity`,
  `S2C_GettingIrrelevant` / `S2C_GettingRelevant` (**interest management**),
  `S2C_ActivateMute`, `C2S_NeedsResynchro` (**resync**), `M2All_SetCastingTeleportState` /
  `M2All_UseTeleportRespawn`, snare effects, `M2M_OnKilledByGun`, `C2S_OnShieldHitTaken`, …
- `FUN_0136f74c` is the **handler table**: `S2C_SetMoveReplicationMode` → handler `FUN_004bfcd3`
  (message/opcode passed through `FUN_00c3348c(obj, slot, "Name")`).

### Parkour / actions are replicated as **discrete events**, not warped positions
- `FUN_004ce584` registers the action/transition message set and more replicated fields:
  - field sets at large offsets (`0x10f0..0x2b90`, `0x7700..0xb140`, `0x2bc0..0x5540`,
    `0x5570..0x76d0`) — the larger character/action object,
  - then messages: **`S2C_Transition`**, **`S2C_TransitionToLedgeClimb`**,
    `S2C_TransitFromLedgeOrClimbToDieRagdoll`, `S2C_PostRespawn`, `S2C_NotifyDamageKill`, … and (per
    the earlier string dump) **`M2R_ReplicateEnterCustomActionState` /
    `M2R_ReplicateExitCustomActionState`** and **`R2M_ForceLedgeRelease`**.
- ⇒ This is the recipe for **"parkour together"**: replicate the *ledge climb / custom action*
  as a discrete enter/exit event, and let each client play the animation — do **not** stream raw
  root-motion positions.

### Master/replica vocabulary
Message prefixes seen: `S2C_` (server→client), `C2S_` (client→server), `M2R_` (master→replica),
`R2M_`, `M2All_`, `R2All_`, `M2M_`. The wire model is **master/replica with interest management**
(`GettingRelevant/Irrelevant`) and resync (`NeedsResynchro`).

## 2. What this means for BF SP

- `NetPlayer` is MP-only, but it **replicates an underlying character/move object** whose fields sit
  at `0x80/0xe8/0x128/0x1f8/0x170`. Our job in `AC4BFSP.exe`:
  1. find the **character object** the player uses (leads: `g_MainPlayerPosition`, `PlayerSpawnEvent`),
  2. identify those **same field semantics** (position/orientation) on it,
  3. spawn/find a **second** such character and drive its fields from the peer,
  4. replicate parkour as **action enter/exit events** (bf MP's custom-action scheme).
- The **spawn** path is `C2S_SetSpawnState` + `SpawnPlayerParams` (string-confirmed); find its
  BF SP equivalent.

## 3. BF SP engine anchors (from the `BF4SP` Ghidra project)

Analysis: `AC4BFSP.exe` imported + analysed (IPL: `-import`), then dumped via `DumpAllBFSP.java` →
`bfsp_functions.txt` / `bfsp_strings.txt` / `bfsp_string_refs.txt`. Image base `0x400000`.

**The task-graph registrar is the same pattern as Rogue.** Registrars (names + stored fn pointer):
- `FUN_00470b00` — engine-frame registrar (`Ai::UpdateCamera`, `Engine::BeginFrame`, …).
- `FUN_00663590` — AI-world registrar (`Ai::AIUpdate`, `Ai::SpawningManagerUpdate`, …).
- `FUN_005863d0` — registers `Anim::UpdateDisplacement`.

**Per-frame task functions (RVA = value; base `0x400000`):**

| Task | Function |
|---|---|
| **`Ai::UpdateCamera`** | **`0x0063bbb0`** (registered as a `LAB_`, per-frame, safe hook — same as Rogue's choice) |
| `Anim::UpdateDisplacement` | `0x0065ddc0` |
| `Ai::AIUpdate` | `0x006632c0` (also `0x00663390`) |
| `Ai::SpawningManagerUpdate` | `0x0070e800` (also `0x00455240`) |
| `Ai::AdjustCameraAfterPhysics` | registered (name seen) |
| camera manager | `"FocusCameraManager"` → `FUN_0071ba10` |

**Correction / gotcha:** `g_MainPlayerPosition` (and `ShadeConstantMainPlayerPosition`) are
**shader uniform names**, not code globals — they appear in a `g_*` shader-constant list
(`g_EyeDirection`, `g_DisolveFactor`, `g_LightShaftColor`, …) with **no code xrefs**. So that early
"named global" lead was a false friend; the player transform must be found the Rogue way
(camera/player path).

**Confirmed:** `AC4BFSP.exe` has **no `NetPlayer` / `SetMoveReplication`** strings (SP has no
netcode) — as expected; we build that layer.

## 4. BF SP camera/transform path (B1) — found

Following the Rogue method on BF SP:

- **`Ai::UpdateCamera` = `FUN_0063bbb0`** — the per-frame hook point (safe, same role as Rogue's).
  Its **first callee is `FUN_0063ba70`**, the real camera update.
- **Camera manager global = `0x02abe588`** (found in `FUN_0063ba70`:
  `MOV ECX, dword ptr [0x02abe588]` before calling the ring accessor; Rogue's equivalent was
  `0x14329dd08`).
- **Ring slot accessor `FUN_004ee120(manager, i)`** returns
  `manager + 0xE0 + ((*(int *)(manager + 0x130) - i + 5) % 5) * 0x10`.
  - `manager + 0x130` = **frame counter** (compare Rogue `+0x190`).
  - `manager + 0xE0 + idx*0x10` = **orientation quaternion** (4 floats; `FUN_0063ba70` reads 16 bytes
    here and runs quaternion→matrix math).
- **Position ring (inferred):** Rogue's layout had the quaternion ring at `counter-0x50` and the
  position ring at `counter-0xA0`. BF SP matches the quaternion offset exactly (`+0xE0 = 0x130-0x50`),
  so the position ring should be **`manager + 0x90 + idx*0x10`** (3–4 floats). **Confirm in-game.**
- **Read recipe (to implement):**
  `mgr = *(u32*)0x02abe588; idx = (*(u32*)(mgr+0x130)) % 5;`
  `pos = *(f32×3)(mgr + 0x90 + idx*0x10); quat = *(f32×4)(mgr + 0xE0 + idx*0x10);`

This is the BF SP analogue of Rogue's proven M2 read path — enough to port the `PlayerTransform`
hook (32-bit) and get B1 verified in-game.

## 5. B1 CONFIRMED in-game (2026-10-06, overnight)

**The plugin loads into Black Flag and reads a live transform.** Deployed:
- `dinput8.dll` — Ultimate ASI Loader **v9.7.4 (x86)** (the Rogue loader is x64; BF needs 32-bit).
- `plugins\AC.BlackFlag.PatchFix.asi` — our build; `plugins\AC.BlackFlag.PatchFix.ini` written.
- Log: `plugins\AC.BlackFlag.PatchFix.log`.

First successful run (game at the main menu):
```
PlayerTransform: base 0x400000 hook 0x63BBB0 camMgrSlot 0x...E588
PlayerTransform: installed
CamProbe: installed
Initialization complete: 2/2 enabled hooks installed
PlayerTransform: pos=(1.3,7.1,1.3) quat=(0.000,0.000,0.913,0.409) mgr=0xC18E860
```
- **`mgr` is a valid camera manager (0xC18E860); the quaternion is unit-length (0.913² + 0.409² = 1.0)** — so the ring read is correct.
- Position is static at the menu; it will move once in-world.

### RVA correction (my arithmetic bug)
The camera-manager global is at **`0x02abe588`**; with image base `0x400000` the RVA is
**`0x026BE588`**. I first wrote `0x26ABE588` (digit transposition) → the plugin read
`base+0x26ABE588 = 0x26EBE588`, a bogus address (it failed safely — null manager, no crash).
Same correction for the camera-position globals: `0x02abe530` → RVA `0x026BE530`,
`0x02abe540` → RVA `0x026BE540`.

### Camera object chain (for the avatar hunt)
- `FUN_00417650` writes the camera position global from the **camera object**:
  `camobj = **(u32**)(manager + 0x4C)`; position `vec4` at **`camobj+0x10`**, orientation
  `vec4` at **`camobj+0x20`**.
- `FUN_005062e0` is the per-frame **ring writer**: advances `manager+0x130` (`% 5`) and copies the
  transform into `manager + (idx+9)*0x10` = **`+0x90 + idx*0x10`** — confirming the position ring.
- `FUN_0040bea0` returns the camera position from globals `0x02abe530`/`0x02abe538`.
- `FUN_0071ba10` ("FocusCameraManager") picks an **entity** from an array at `obj+0x28`
  (count `+0x2E`) and stores the **focus entity at `obj+0x914`** — a candidate "current player entity".

### Probe armed
`CamProbe` (read-only, default on) dumps, at 0.5 Hz: the manager pointer, camera position, the
`manager+0x4C → camobj` chain and its `+0x10`/`+0x20` vec4s, one-level pointer scan of the camera
object, and a scan of `manager[0..0x200]` for pointers to objects holding a float triple at the
camera position (candidate player/character objects). **Game left running at the menu with the probe
installed** — loading a save will capture the in-world data.

## 6. B3 lead — candidate character objects (in-world probe, 2026-10-06)

In-world (camera at ~`(-490,358,4)`), the probe found, via the camera object:

- **Chain:** `mgr` (`0xC18E860`) → `+0x4C` → holder → **`camobj`**; `camobj+0x10` = camera position
  (vec4), `camobj+0x20` = orientation (vec4).
- **`camobj+0x68` → target object** holding positions **~5 units from the camera**:
  - `+0x10` / `+0x30` = the camera transform (e.g. `(-490.5,358.7,4.6)`),
  - **`+0x50` / `+0x60` / `+0x70` = `(-493.1,358.9,…)` — the third-person offset, i.e. the
    candidate PLAYER BODY position.**
- Also on the manager: `mgr+0x20 → 0xC18E884` (camera-ish position at `+0x6C`),
  `mgr+0x68 → 0xC11FDE0` (at `+0x60`).
- The camera object **cycles through a pool** (`camobj` changes sample to sample), so the stable
  anchor is the **manager**, not the camera object.

**Next (B3):** in-world, track the `camobj+0x68 → +0x50/+0x60` triple while walking; if it stays
~5 units from the camera and rotates with the player, that is the player body transform — then match
it against the BF MP oracle's replicated fields (`0x80/0xe8/0x128/0x1f8/0x170`, move-mode `+0x398`).

### CONFIRMED (2026-10-06, second run) — it is the player body

Walk-and-turn capture at 4 Hz (`logs/b3-player-position-confirmed-*.log`):

- **Walking straight:** the offset `cand − cam` is rock stable at `(-0.3, -2.8, -0.6)` — the
  candidate moves 1:1 with the camera.
- **Turning:** the offset **rotates in the XY plane** — `(-0.3,-2.8) → (2.5, 0) → (0.5, +2.3)` —
  i.e. the camera orbits a *fixed world point* while the body stays put.
- The target object (`0x39B7FE50` that run) was **stable across the whole walk**.

⇒ **`camobj+0x68 → object+0x50` is the player's world body/pivot position**, reachable from the
stable manager chain: `mgr (0x02abe588) → +0x4C → holder → camobj → +0x68 → obj → +0x50`.

**Next:** dump that object's *pointers* (not just float triples) to find the owning **character
entity**, then match the entity against the BF MP oracle's replicated fields
(`0x80/0xe8/0x128/0x1f8/0x170`, move-mode `+0x398`) and test driving a second body.

**Capture:** `bf-coop/logs/b1-confirmed-20261006-001506.log` (633 KB, in-world probe data included).

## 7. B3 write test — NEGATIVE (2026-10-06, live)

Live write into the running game (`memwrite` on the process, no rebuild):

- Read `obj+0x50` (the confirmed player-body position): `(-548.407, 282.528, 4.800)`.
- Wrote `X = -543.4` (a +5 nudge).
- **Immediate read-back: `-543.40` — the write landed.**
- **<1 s later the engine had overwritten it** (`-551.72, 275.55, 4.52`) and the player kept moving
  normally; the camera transform continued to track the real player.

⇒ **`obj+0x50` is a *derived* transform the engine recomputes each frame — writing it does not move
the player.** It is a downstream copy (camera/render side), not the authoritative character state.

**What this means for B3:** reading is solved, but the *drive* path is elsewhere. The next target is
the **writer** of that transform block — the code that copies the character's transform into it each
frame reads the real character object, and following it upstream should reach the authoritative
**character/entity** whose transform we can move.

## 8. Shared gotchas
- 32-bit (x86) — all addresses/packaging are 32-bit; the plugin must be `ARCH x86`.
- Ghidra headless on `AC4BFSP.exe` needs a **large heap** (8 GB OOM'd; 20 GB worked).
- No anti-cheat; offline/LAN only. Reverse BF MP **offline only**; never run its live PvP.

### Confirmed: the "param_2" source transform (2026-10-06)
- FUN_01122150(this = provider, param2 = source, bufA = this+0x20, bufB = this+0x30) — the camera-target smoother. Called by FUN_01128F70 / FUN_012398A0 (vtable methods of the provider class).
- One source node per character (the class described in CURRENT TRUTH above). **Correction (2026-10-06 late):** an earlier note here read "+0x8 -> self+0x110"; that is wrong — `+0x8` is a player-only pointer to an identity-matrix attachment, and the captured object is only 0x100 bytes (the "self+0x110" value was the neighbouring allocation's address). The later "self-node" heuristic was an adjacency coincidence too.
- Providers (camera targets, vtable 0x02697010): +0x20 buffer (eye ~feet+1.2), +0x100 quaternion, +0x110 feet position. Chain: mgr 0x2ABE588 -> +0x4C -> holder -> camobj -> +0x68 -> block -> +0x174 -> provider; block+0x50 = provider+0x20 copy.
- Tooling: tools/bp-capture-param2.ps1 captures EAX (the source node) at AC4BFSP.exe+0xD2218E for up to N hits and dumps the object.
