# AccCoop — A4 research: the remote avatar (spawn / hijack)

Goal: get a second character on screen at the peer's position so two players can "see each other"
and eventually parkour together. This is the hardest part of Stage S1.

## 1. Black Flag MP — the reference for a networked avatar

`AC4BFMP.exe` (x86) strings show exactly how a networked player + avatar are handled:

- **Spawn:** `SpawnPlayerParams`, `MultiSpawnPlayerComponent`, `PlayerSpawnActivatorComponent`,
  `PlayerSpawnedEvent` — the player spawn flow.
- **Avatar/identity:** `avatarID`, `NetPlayer`, `NetPlayerActionHistoryManager`.
- **Skins (the playable Assassin characters):** `CharacterSkinsComponent`,
  `CharacterSkinInventoryItem`, `SKIN_CHOSEN`, `SkinsList`, `M2All_SwapSkinEventWithId`,
  `D2M_RequestSwapSkin`, `C2S_Skin_UnselectSkin`, `S2C_NotifyReservedSkinForRequestedVIP`.
- **Playable archetypes:** `::CHR_Playable`, `ArchetypeDef`, `ArchetypeUIDesc`.

⇒ In MP, each player is a **`NetPlayer`** spawned from `SpawnPlayerParams` and wearing a chosen
**character skin** (`CHR_Playable`). Rogue has the same engine vocabulary (`SpawnPlayerParams`,
`SpawnCharacterParams`, `PlayerSpawnActivatorComponent`) but no `NetPlayer` layer.

> Note: BF MP avatar **models** are BF content and are not portable into Rogue (no game files cross;
> and the skeletons/anim sets differ). Use BF as a *design* reference only — the Rogue avatar must be
> built from Rogue's own `CHR_*` assets (e.g. `CHR_P_Shay_*`, or an NPC archetype).

## 2. Rogue's spawn systems (mapped)

- **Scene spawners:** `SceneSpawner`, `AbstractSceneSpawner`, `SceneSpawnerHandle`,
  `AbstractSceneSpawnerSource`, `SpawnSettings`/`SpawnSettingsClip`, `EntitySpawnedActor`.
- **AI spawn manager:** `Ai::SpawningManagerUpdate` = `FUN_14046b6f0` / `FUN_14046b7e0`. Iterates
  spawner sources at `obj+0x10` (count u16 at `+0x1a`); per source calls vtable `+0xd8`/`+0xe0`/`+0xf0`
  and the pick helpers `FUN_14045c560` / `FUN_140465c20` (which select and then call the source's
  spawn/despawn). `FUN_140465c20` **despawns** via `FUN_1400c8ca0(obj+0x8, actor)` — the inverse
  (spawn/create) is nearby and worth hunting (`FUN_1400c8*`).
- **Spawn type names** (`SpawnPlayerParams`, `SpawnCharacterParams`, `SpawnOperator`, …) have **zero
  code xrefs** — reflection-table only. Cannot grep to the spawn call.
- **Gear entity create/destroy (Route B lead):**
  `FUN_1400c8c40(world, desc, cb)` → `FUN_1400c8740(DAT_143299fd0, desc, cb, flag)` = Gear **create**;
  `FUN_1400c8ca0(world, obj)` → `FUN_1400c7910(DAT_143299fd0, obj)` = Gear **destroy**.
  `DAT_143299fd0` is the Gear world. `desc` (arg 2) is an ~8-qword descriptor copied into a 0x68-byte
  registry record; `cb` (arg 3) is a completion/ref callback. ⇒ spawning means building a **valid
  character descriptor** (archetype id + transform + …) — those fields are opaque here, so Route B is
  the deep/risky path and needs more RE (or live experiments).

## 3. Actor enumeration (the list to hijack or spawn into)

`FUN_140100530(aiGlobal, partition, filter, outA, outB)` (called by `Ai::AIUpdate` `FUN_140107450`
with `aiGlobal = DAT_14329bd78`, partitions 1/0/3):

- Partition chunk = `aiGlobal + (partition+7)*0x10`; it is a TArray-ish pair:
  data pointer at `chunk+0`, **count (u16) at `chunk+0x0a`**.
- Entries are **actor pointers** `E`. Per actor:
  - `*(E+0xc0)` = a context/component; `FUN_14082a2d0(*(E+0xc0), tag)` queries it
    (`FUN_140829440(*(ctx+0x40), &key)`), tags `DAT_14329dcc8` / `DAT_14329dcbc`.
  - `E+0x3b0` = component array (count u16 at `E+0x3ba`).
- So a usable actor walk is: read `aiGlobal = read64(base+0x329BD78)`, then for each partition read
  `chunk = aiGlobal + (p+7)*0x10`, `n = read16(chunk+0x0a)`, `data = read64(chunk)`, then
  `E = read64(data + i*8)`.

This is the concrete first probe: **enumerate live actors** and identify the player vs NPCs.

## 4. Two implementation routes

| | Route A — hijack an NPC | Route B — spawn a fresh avatar |
|---|---|---|
| Idea | Pick a live NPC actor, freeze its AI, drive its transform to the peer position each frame | Call the engine's spawn to create a character at the peer position |
| Pros | No spawn API needed; enumerate + write | Clean, a real avatar |
| Cons | Reuses a world NPC (it "disappears" from its AI role); need to stop its controller | Spawn call is deep + no code xrefs; risky to drive from a hook |
| Risk | Medium (need actor transform + AI freeze) | High (engine internals + crash class) |

Both are "call engine internals from a hook" territory — the exact crash class we hit with the
movement-state accessor (a fault permanently disables the callback). Mitigations: do the risky calls
in a **separate functor** (so A1 survives), guard every pointer with `VirtualQuery`, and stage it.

## 5. Concrete next probes (when we resume)

1. **Actor walk probe** — read `DAT_14329bd78` + partitions, log actor pointers and counts; try to
   tell the player apart (it's the actor whose context matches the camera/body). Pure reads.
2. **Find the actor transform** — for a candidate actor, scan a few offsets for a float triple near
   the known player body position (we have ground truth from `PlayerTransform` now).
3. **AI freeze** — find the actor's controller/AI-enable flag (near `E+0xc0` context or `E+0x3b0`
   components) and clear it, so the hijacked NPC stops acting.
4. **Spawn hunt (Route B)** — decompile around `FUN_1400c8ca0` (despawn) to find the create counterpart,
   and the `SceneSpawner` spawn entry.

## 6. Reality check

Route A is the realistic first "see each other": a walking NPC body at the peer's position. Route B
(a true Shay avatar) is the long-term goal and the most uncertain. Expect several careful
build → launch → read-log cycles, each protected by the crash-isolation design above.

## 7. RESULT (2026-10-04): Route A plumbing works; `+0x800` is the wrong field

- **Discovery:** the `PlayerProbe` found the player actor in **partition 1** with its position at
  **`actor+0x800`** (and occasionally a second copy at `+0x854`).
- **HijackAvatar** implemented and run: enumerates actors, picks the first non-player, and writes the
  peer position to `donor+0x800` every frame in `Ai::AIUpdate`. Logged **78–152 writes**, tracking a
  spoofed peer precisely (`donor=0x852CE5E0 -> peer=(1061.9,423.0,13.3)` …). So **network → write
  works.**
- **But NO visible body**, even when the donor was driven to the player's *own* position (self-loop,
  impossible to miss). ⇒ `+0x800` is a **cached/derived** field that the move/render system
  overwrites each frame (or the chosen donor isn't a visible character).
- **Next (the real work):**
  1. Find the actor's **move/render transform** (what the renderer actually uses) — candidates: the
     move component from the player chain (`FUN_140103f90`), the component array at `E+0x3b0`, or a
     4×4 matrix near the actor. Extend the probe to report **every** offset matching the position,
     then write each and observe.
  2. Pick a **visible human donor** (not just "first non-player actor").
- Everything up to the transform is proven: enumeration, donor selection, per-frame write, and the
  full UDP path.