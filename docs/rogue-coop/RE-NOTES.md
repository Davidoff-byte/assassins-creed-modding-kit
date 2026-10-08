# AccCoop — ACC.exe reverse-engineering notes

Base `0x140000000`. From Ghidra project `C:\Users\Administrator\ghidra-acc\ACC.Rogue` (`ACC.exe`).
These are the per-frame anchors for the co-op replication layer.

## 1. The engine is a task-graph scheduler

`FUN_1400d53b0`, `FUN_14010f850`, `FUN_1402b4840`, `FUN_1405d4320` are **registrars**, not ticks.
Each builds named task nodes into a scheduler struct and stores the **real task function** in the
node. Node shape (per registration): a 4-qword slot where `+0x00=fn`, `+0x10`(varies), and a
`FUN_1408118f0(node, "Namespace::Name", fn, flag, data)` call attaches the name; `FUN_140814420`
and `FUN_1408118e0` bracket it.

⇒ Two integration options for the mod:
1. **Hook a named task function** (read-only MidHook) — safe, no engine internals.
2. **Register our own task node** into the graph (cleanest) — needs the scheduler's add API.

## 2. Real per-frame task functions (the ones that matter)

| Task name (engine string) | Function | Use for AccCoop |
|---|---|---|
| `Ai::UpdateCamera` | `FUN_1403664e0` | fastest read of camera pos/rot (M2) |
| `Ai::AdjustCameraAfterPhysics` | `FUN_140358f00` | camera after physics |
| **`Ai::SpawningManagerUpdate`** | **`FUN_14046b6f0`**, `FUN_14046b7e0` | **entity/NPC spawn path → remote avatar (M4)** |
| `Ai::AIUpdate` | `FUN_140107450`, `FUN_1401075c0` | AI/entity update → NPC iteration (M6) |
| `Ai::CoordinatorUpdate` | `FUN_1400feef0` (multi), `FUN_1400fecf0` (single) | AI coordinator |
| `Ai::UpdatePreActionGather` / `ActionGatherComponents` | `FUN_1402b2730` | world/action gather |
| `Ai::UpdateCharacterActionSet` | `FUN_140420b30` | animation action set (posture for avatar) |
| `Anim::UpdateDisplacement` | `FUN_140420bc0` | root motion / displacement |
| `Anim::ActionUpdateEvents` | `FUN_14041fc90` | animation events (attacks, kills) |
| `Anim::UpdateActionBones` | `FUN_14041fcf0` | skeleton bones |
| `Anim::SkeletonUpdateForRagdoll` | `FUN_14022cb60` | ragdoll/death skeleton |
| `Physic::AfterSimulation` (registered in `FUN_1402b4840`) | *(see graph)* | **final transforms each frame** |
| `Ai::UpdateAfterPhysics*` | — | post-physics hook |

> Exact node offsets still to confirm; the names above are read directly from the registrar
> decompiles (`decomp_set.txt`).

## 3. Registrar → task names observed

- **`FUN_1400d53b0`** (engine frame): `Engine::BeginFrame`, `Graphic::BeginGraphicFrame`,
  `Graphic::GraphicFrame`, `Graphic::EndGraphicFrame`, `Engine::BeginEngineFrame`,
  `Engine::UniverseComponentStep`, `Engine::DominoStep`, `Engine::PreActionStep`,
  `Engine::PreActionWorldStep`, `Engine::Step`, `MenusAndSounds`, `Fire::FireStep`,
  `Online::UpdateOnline`, `Ai::UpdateCinematicManager`, **`Ai::UpdateCamera`**,
  `Ai::AdjustCameraAfterPhysics`(=`AdjustCameraAfterPhysics`), `Engine::UpdateWhileEngineIsPaused`,
  `Engine::EngineLoop::Step`, `Engine::StepPreWorlds`, `Engine::StepDispatchEvents`,
  `AfterAIAndSkel`, `Sound::Update`/`SoundManagerUpdate`, `Anim::ActionManagerUpdate`,
  `Ai::AccomplishmentManagerUpdate`, `Graphic::EndEngineFrame`, `Engine::EndFrame`.
- **`FUN_14010f850`** (AI world): `Ai::AIUpdate`, `Ai::NavigationPathingUpdate`,
  **`Ai::SpawningManagerUpdate`** (x2), `Ai::NavigationSteeringUpdate`, `AIWorldManagersStep1`,
  `AIWorldManagersStep2`, `Ai::CoordinatorUpdate` (multi + single threaded),
  `Ai::AIUpdateAfterAIComponents` (x2), `AfterAIWorldManagers`, `BeforeAIWorldManagers`.
  (Note: there's a `DAT_14329bb80` branch — single- vs multi-threaded coordinator.)
- **`FUN_1402b4840`** (action/animation/physics): `UpdatePreActionGather`,
  `ActionGatherComponents`, `UpdateCharacterActionSet`, `ActionUpdateBeginAnimate`,
  `Ai::ActionAdjustTime`, `Anim::UpdateDisplacement`, `Anim::ActionUpdateEvents`,
  `Anim::AfterGatherAndDisplacement`, `Anim::UpdateActionBones`,
  `Anim::UpdateActionBonesForRagdoll`, `Anim::SkeletonUpdateForRagdoll`, and the
  `*WorldIsPausedBranch` / `*EndNode` gates.

## 4. Other engine facts

- `FUN_1400d53b0(param_1)` also *runs the whole frame* when called (it's a big function that both
  registers and drives the loop) — treat hooking it with care.
- Locale/`DAT_14329bb80` selects a multi-threaded AI coordinator path.
- Physics registrar strings include `Pinocchio` (Ubisoft animation/IK) and a build id
  `UbisoftSofia_AssassinsCreedComet_Xbox360_PS3` (Sofia = Rogue's studio; "Comet" = internal name).

## 5. Next RE steps

1. Decompile `FUN_1403664e0` (UpdateCamera) → camera object + transform offsets (M2 read path).
2. Decompile `FUN_14046b6f0`/`FUN_14046b7e0` (SpawningManagerUpdate) → entity spawn API (M4 avatar).
3. Decompile `FUN_140107450` (Ai::AIUpdate) → entity list iteration + per-entity state (M6).
4. Find the scheduler's node-add API → decide "hook a task" vs "register a task".
5. Cross-check entity identity: decompile spawn + serialization; compare with `AC4BFMP.exe` (BF MP).

## 6. M2 RESULT — camera world transform (the first read path)

`DAT_14329dd08` is the **camera manager global**. `Ai::UpdateCamera` (`FUN_1403664e0`) loads it
directly: bytes `48 8B 3D 07 78 F3 02` at `0x140366501` → `0x14329DD08`.

The manager keeps a **ring of 5 camera transforms** and a counter:

| field | offset | size |
|---|---|---|
| frame counter (0..4) | `manager + 0x190` | u32 |
| position ring, 5 × vec4 | `manager + 0x0F0 + i*0x10` | 5×16 B |
| orientation quaternion ring, 5 × vec4 | `manager + 0x140 + i*0x10` | 5×16 B |
| per-camera object array | `manager + 0x08` (count u16 @ `+0x12`) | TArray |
| CameraFXInterface | `manager + 0x38` | (already used by `CameraLean`) |

Index used by the engine code is `i = (counter + 5) % 5` (= current slot). Proven in
`FUN_14034e5b0` (called first in UpdateCamera), `FUN_1403662b0`, `FUN_140357e40` (all read the same
ring, build a quaternion rotation + translate, and apply to the camera target `*(camera+0x40)`).
So reading `pos = *(f32×3)(manager + 0xF0 + i*0x10)` and `quat = *(f32×4)(manager + 0x140 + i*0x10)`
gives the live camera world transform — the basis for M2 (and the peer avatar placement).

### Hook signatures (for `AC.PatchFix` scan entries)

```
Ai::UpdateCamera            @0x1403664E0 : 48 83 EC 28 48 89 7C 24 20 E8 ?? ?? ?? ?? 48 8B 3D ?? ?? ?? ?? 48 8B 47 70 48 63 48
Ai::AdjustCameraAfterPhysics@0x140358F00 : 48 83 EC 28 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B 0D ?? ?? ?? ?? 48 83 C4 28 E9
Ai::AIUpdate                @0x140107450 : 48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 30 48 8B 41 08 48 8B F1 0F B7 78 0A 85 FF 74 75
Ai::SpawningManagerUpdate   @0x14046B6F0 : 40 56 57 41 54 48 83 EC 20 48 8B 71 08 33 FF 4C 8B E1 48 85 F6 74 09 48 8B B6 08 0F 00 00
```

The camera manager global can be resolved from the `Ai::UpdateCamera` match at `+0x16`
(`48 8B 3D` +3 → RIP-relative), or reused from `CameraLean`'s `camera_manager_load`.

### M2 implementation plan
1. `AC.PatchFix` scan entries: add the `Ai::UpdateCamera` and a `camera_manager` field.
2. New hook `PlayerTransform`: read-only `MidHook` on `Ai::UpdateCamera`; read
   `manager + 0x190` → index → position/quaternion; log at 5 Hz (or publish to a `PrintState`).
3. Verify in game: walk/turn → logged position/yaw track. Then feed the co-op protocol.

### A1 VERIFIED (final form, in game)

Implemented and confirmed: `PlayerTransform` logs
`BODY=(1049.0,424.6,19.0) … cam=(1045.9,422.3,21.7)` tracking a walk + climb, with the UDP stream
carrying the same body positions and **no crash**.

Deterministic addressing (no pattern scan), from the module base:
- hook `+0x3664E0` = `Ai::UpdateCamera`
- camera manager slot `+0x329DD08`
- player getters `+0x352C10` (`idx`), `+0x346AA0` (`object(idx)`), `+0x0D8600` (`PlayerPosition`)
- ready-gate slot `+0x32DE460` (guard before the chain)
- body = getters → `ps`, then floats at `ps+0x30` (or `read64(ps+0x40)+0x50`)

**Crash gotcha:** a fault inside the hook callback sets `s_faulted` and **permanently disables** it.
Every pointer read is now wrapped in a `VirtualQuery` readability check first.

## 7. A1 — player **body** position + movement/locomotion state (Rogue)

Found via `FUN_14103ed10`, the game's **own** "PlayerPosition" builder (it posts a struct through
`FUN_140765e50(DAT_1432c9c50, "PlayerPosition", ...)`):

- It reads **Xcoordinate / Ycoordinate / Zcoordinate** from a struct at **`+0x30 / +0x34 / +0x38`**
  (three floats), so this is a real player world position, not the camera.
- The struct comes from the player object:
  - `FUN_140352c10()` → active index into the global player array **`DAT_14329f630`**
    (count at `DAT_14329f638._2_2_`), matched against `FUN_14009dcd0()` = `*(DAT_143299fc8 + 0x88)`.
  - `FUN_140346aa0(idx)` → the player object (`*(DAT_14329f630 + idx*8)`).
  - `FUN_1400d8600(player)` → the position struct: if `*(player+0x70)` then `FUN_1402892d0(...)`
    → `FUN_1401a7a40(*(*(x+0xd10)+8))`.
- `FUN_1400d8590(player)` → `*(*(player+0x130)+0x30)` (sub-object used for health/weapon queries).

**Movement/locomotion state** — `FUN_1410231c0` returns the mode string:
`"Slow Walk" | "Walk" | "Fast Walk" | "Jog" | "Sprint"` from a movement component
(`vtable+0xd8` enum 0..5), and **`"Climb"`** when `FUN_1401a5590(x,1) == 0x1e`.
Component chain: `FUN_140352c10()` → `FUN_140346aa0` (player) → `FUN_1400d8590` → `FUN_140103f90`
(`= *(*(p+0x40)+0x100)+0x40`). **This is the parkour/animation state we need for A5** and it mirrors
what Black Flag replicated as `CustomActionState`.

Caller of the position builder is `FUN_141042ed0` and it is **throttled (~0.5 s)** — so for sync we
read the globals/accessors ourselves in a per-frame hook (alongside `Ai::UpdateCamera`), not that fn.

## 9. A4 — remote avatar (spawn / actor list) — in progress, the hard one

- Spawn type names (`SpawnCharacterParams`, `AbstractSceneSpawner`, `SpawnOperator`,
  `AbstractSceneSpawningComponent`, `EntitySpawnedActor`, `SpawnPositionComponent`,
  `PlayerSpawnActivatorComponent`) have **zero code xrefs** — they live only in the reflection table,
  so we cannot grep to the spawn function.
- **Actor enumeration found:** `FUN_140100530(aiGlobal, partition, filter, outA, outB)` iterates one
  partition at `aiGlobal + (partition+7)*0x10` (count u16 at `+0x0a`); each entry is an
  **actor/entity `E`**. Per entity: `*(E+0xc0)` is a context/component handed to
  `FUN_14082a2d0((E+0xc0), DAT_14329dcc8|DAT_14329dcbc, …)`; `E+0x3b0` is a component array
  (count u16 at `+0x3ba`). `Ai::AIUpdate` (`FUN_140107450`) calls it with `DAT_14329bd78` and
  partitions 1/0/3.
- Spawn manager `Ai::SpawningManagerUpdate` (`FUN_14046b6f0`/`FUN_14046b7e0`) iterates spawners at
  `obj+0x10` (count u16 at `+0x1a`) and calls spawner vtable `+0xe0`/`+0xf0`; the actual creation is
  in helpers `FUN_14045c560` / `FUN_140465c20` / `FUN_140468e50`.
- **Two routes:** (a) enumerate actors via the partition structure and **hijack an NPC** (freeze its
  AI, drive its transform to the peer position); (b) drive the spawner path to **create** an avatar.
  Both need further RE + live testing.

## 8. Black Flag netcode analysis (done) — the replication design to copy

Project `C:\Users\Administrator\ghidra-bf\AC4BFMP` (x86, base 0x400000). Function→string index dumped to
`bf_functions.txt` / `bf_strings.txt` / `bf_string_refs.txt`.

**It's a message + field-replication system (master/replica).**

- **Message registry** `FUN_004ce584`: for each message it does
  `FUN_011fc7e0("Name")` → id, then `FUN_00c3348c(channel, &slot, "Name")` to bind a handler slot.
  Names include (parkour-relevant in bold):
  `S2C_Transition`, **`S2C_TransitionToLedgeClimb`**, `S2C_TransitFromLedgeOrClimbToDieRagdoll`,
  `S2C_PostRespawn`, `S2C_NotifyDamageKill`, **`R2M_ForceLedgeRelease`**, `M2R_SendKickVictim`,
  `M2All_Taunt`, `M2All_StartedNewEvent`, **`M2R_ReplicateEnterCustomActionState`**,
  **`M2R_ReplicateExitCustomActionState`**, plus dozens of ability/effect events.
- **Move replication** `FUN_004bf90e`: sets up the `S2C_SetMoveReplicationMode` channel and registers
  the **replicated field set** through `FUN_00c2fdfc(obj, offA, offB, offC, priority, flag)`:
  offsets **0x80, 0xE8, 0x128, 0x1F8, 0x170**, priorities `1` (normal) and `0x7fffffff` (high).
  It also registers `C2S_SetSpawnState`, `OnSendToEntity`, `S2C_GettingIrrelevant/Relevant`,
  `S2C_ActivateMute`, `C2S_NeedsResynchro` — i.e. **interest management + resync**.
- **Per-message handler tables**: `FUN_0136f74c` (S2C_SetMoveReplicationMode → handler `FUN_004bfcd3`),
  `FUN_0137272d` (enter → `LAB_004d9140`), `FUN_01372772` (exit → `FUN_004d92e9`).
- **Networked objects**: `FUN_004fd528` registers **`NetPlayer`** via the factory `FUN_00c23e4e`;
  `FUN_00699771` registers **`NetPlayerActionHistoryManager`**; `FUN_00c18df0`/`00c334a7`/`00c1c6a3`
  are `netproxy`/`netproxyclass`.

**Design takeaways for Rogue (this is what we copy):**
1. Replicate a **set of fields by offset** with a **priority/rate per field** — not one blob.
2. Movement has a **mode** (`SetMoveReplicationMode`) toggled by **relevance**
   (`GettingRelevant`/`Irrelevant`) and a **resync** request (`NeedsResynchro`).
3. Parkour is **discrete custom-action enter/exit messages** + **ledge-climb transition** messages —
   i.e. the animation/parkour state is evented, exactly what Rogue's `FUN_1410231c0` movement state
   and `CustomAction` system expose.

## 10. A4 Route C — engine **debug-cheat** spawn + teleport (BIG FIND, 2026-10-05)

The retail `ACC.exe` ships the full developer **cheat/debug** system, compiled in (not stripped).
The command table is registered in `FUN_141ebc6e0` (`acc_00039.c:69758-71242`); every entry is a
0x68-byte record whose handler is a plain function we can call directly from a hook. This gives a
**spawn-a-character** and a **set-world-transform** path far cheaper than the SpawningManager route.

### Spawn commands → handlers (all callable)
| Menu string | Handler (RVA, base 0x140000000) | Dude type |
|---|---|---|
| `Spawn Follow Dude` | `FUN_141e91d50` = **0x1E91D50** | 0 |
| `Spawn RedBall Dude` | `FUN_141e91ec0` = 0x1E91EC0 | 1 |
| `Spawn Still Dude` | `FUN_141e91f00` = 0x1E91F00 | ? |
| `Spawn Fight Dude` | `FUN_141e91d90` = 0x1E91D90 | ? |
| `Spawn Ship Dude` | *(handler TBD)* | ? |
| `Change Debug Dude Type` | `FUN_141e5b140` | – |

Handler shape (`FUN_141e91d50(param==1)`):
```
dude = FUN_141e852c0();          // 0x40-byte debug-dude object, ctor FUN_141271d70, vtable PTR_FUN_1429fbfc0
*(u32*)(dude + 0x30) = 0;        // type
ctx  = FUN_1400ed780();          // lazily-created singleton DAT_14329c6e8
FUN_14016e190(dude, ctx);        // activate/register (-> FUN_14016b0d0(DAT_14329de70, dude, ctx))
```
Debug-dude objects are kept in a global array **`DAT_14329def0`** (pointer), count = low 14 bits of
**`DAT_14329def8`** (RVA 0x329DEF0 / 0x329DEF8).

### Teleport / set-world-transform (the API A4 actually wants)
`FUN_141eab190(char)` (RVA 0x1EAB190) — "Teleport Character" (menu cmd `FUN_141eb0320`, mode 1):
```
if (*(char*)(char + 0x811)) {                 // has a saved/ghost position
  FUN_141eaaf30(char, mtx[64]);               // build 4x4 world matrix (camera DAT_14329dd08 + saved pos)
  comp  = *(u64*)(char + 0x20);
  iface = (*(*comp + 0x90))(comp, 0xd);       // get interface id 0xD from the component
  if ((*(*iface + 0x28))(iface, mtx)) {
     (*(*iface + 0x30))(iface, mtx);          // <<< SET WORLD TRANSFORM
     if ((*(*iface + 0x48))(iface)) (*(*iface + 0x50))(iface, 0);
  }
}
```
So: to place a character at an arbitrary world transform, call the interface-0xD
`vfunc+0x30(iface, mtx4x4)`. This is the rendered move/transform — **not** a cached field.

### Why the old HijackAvatar failed (explained)
`char + 0x800` (3 floats pos) / `char + 0x811` (bool) is the **ghost-mode saved-position slot**, not the
live/render transform. Writing a random donor's `+0x800` (A4-RESEARCH §7) only edited that slot, which
the renderer ignores. The render transform is behind the component/interface above.

### Bonus: entity identity lead (S2)
Debug strings show entity ids formatted as 64-bit: `EntitySpawnedCondition_ID_0x%08llX`,
`SpawnedTargetEntity ID:0x%08llX`, `SceneSpawnerID=0x%08llX`, `Spawned Cinematic Entity ID:%s`.
⇒ entities carry a **64-bit id/hash** — the strongest candidate for the S2 cross-machine identity key.

### Probe shipped
New hook **`DebugSpawn`** (`src/hooks/debug_spawn.cpp`): MidHook on `Ai::SpawningManagerUpdate`
(0x46B6F0); when `[DebugSpawn] Enabled=true` and the player-ready gate (0x32DE460) is set, it calls
`FUN_141e91d50(1)` once and logs `spawned=<bool> dudeArray=<ptr> count=<n>`. Default OFF.
**Verify in game:** enable it → a second (follower) body should appear near Shay. That alone is the
first S1 milestone ("a second character exists"); driving it to the peer position is the next step.


