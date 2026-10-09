# MODLOG — BFCoop (Assassin's Creed IV Black Flag co-op)

> **Reading order:** for the *current* facts use `RE-NOTES.md` (CURRENT TRUTH box) and `PLAN.md`
> (status + design). This file is the chronological journal, mistakes included — corrections are
> flagged inline and in the later entries.

## 2026-10-05 — kickoff + recon

Goal (user): two-player free-roam co-op in **AC4 Black Flag single-player**, parkour together in
**Havana**, over **Radmin VPN**. Port the ACCoop (Rogue) replication layer to `AC4BFSP.exe`, using
`AC4BFMP.exe` as the networked-avatar oracle. Full plan: `PLAN.md`.

### Recon so far
- **Pinned builds (MD5):**
  - `AC4BFSP.exe` = `2058342866688F780C8B34526A65BC35` (45,056,040 bytes, x86).
  - `AC4BFMP.exe` = `A82983AC8DDB00DE30268E5C37E4BA51` (30,269,344 bytes, x86).
- **`AC4BFSP.exe`**: 42.97 MB, **x86** (32-bit), last modified 2026-10-04. Install at
  `D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag`. Same engine family as Rogue
  ("scimitar"/AnvilNext); no anti-cheat.
- **`AC4BFMP.exe`**: 28.9 MB, x86 — already has a Ghidra project at
  `C:\Users\Administrator\ghidra-bf\AC4BFMP.rep`. Contains the replication design (see below).
- **BF SP named anchors found (string dump `acc-coop\tools\bf_sp_strings.txt`):**
  - `g_MainPlayerPosition` and `ShadeConstantMainPlayerPosition` — **named globals for the main
    player position** (Rogue had no such convenience). Likely our first read path. **No addresses in
    the dump — needs Ghidra.**
  - Spawn: `PlayerSpawnEvent`, `PlayerSpawnActivatorComponent`, `EntitySpawnedActor`,
    `EntitySpawnedCondition` / `_ID_0x%08llX` (64-bit entity ids again).
  - `TeleportEvent` / `TeleportCompletedEvent`.
- **BF MP replication strings (`bf_mp_net_strings.txt`):** `NetPlayer`,
  `NetPlayerActionHistoryManager`, `S2C_SetMoveReplicationMode`,
  `M2R_ReplicateEnterCustomActionState`, `SpawnPlayerParams`, `avatarID` — the oracle to copy.
- **Plugin framework**: the AC.PatchFix clone has game targets `games/ac/rogue` and
  `games/ac/syndicate` only — **no blackflag target**; one must be added (or a Rogue-derived target
  adapted), using **x86** this time.

### Gotcha — Ghidra heap
- First analysis attempt of `AC4BFSP.exe` (43 MB, x86) **OOM'd at 8 GB heap**
  (`X86Analyzer … OutOfMemoryError: Java heap space`; project left empty), matching the known
  "Ghidra headless needs a big heap" warning. This machine has 31.8 GB RAM.
- **Retry:** `GHIDRA_HEADLESS_MAXMEM=20G`. (For reference, Rogue's 67 MB x64 `ACC.exe` analysed fine
  at 8 GB — so the x86 analyzer is the hungrier one.)

### Next
1. Ghidra headless analysis of `AC4BFSP.exe` (x86) → resolve `g_MainPlayerPosition`, the task
   registrar, and the spawn/player path to addresses. (Retry running this session, 20 GB heap.)
2. Port the ACCoop transport/protocol (engine-agnostic) and a Black Flag game target into the patch
   framework.
3. B1: read the local player transform in-game; verify it tracks walking.

## 2026-10-06 (overnight, autonomous) — **B1 CONFIRMED in Black Flag**

User granted overnight autonomy. Did the desk RE and the first real in-game test.

### Static RE (desk)
- **B0 anchors verified + extended**: `Ai::UpdateCamera` = `0x0063bbb0` (our hook, safe); camera
  manager global `0x02abe588` (found in `FUN_0063ba70`, its first callee is the camera update).
- **Ring confirmed by its writer**: `FUN_005062e0` advances `manager+0x130` (`%5`) and writes the
  transform into `+0x90 + idx*0x10`; the quaternion ring is `+0xE0`. The camera **position** comes
  from globals `0x02abe530` (vec4), read via `FUN_0040bea0`.
- **Camera object chain**: `FUN_00417650` sets the position global from
  `camobj = **(u32**)(manager+0x4C)`, pos `vec4` at `camobj+0x10`, orientation at `camobj+0x20`.
- **Candidate player entity**: `FUN_0071ba10` (FocusCameraManager) stores a **focus entity** at
  `obj+0x914` after filtering an entity array at `obj+0x28`. Next lead for B3.
- **Correction**: `g_MainPlayerPosition` is a **shader uniform** name, not a code global.
- **Spawn type-names** (`PlayerSpawnEvent`, `SpawnPlayerParams`, `PlayerSpawnActivatorComponent`)
  have **no code xrefs** (reflection-only) — same wall as Rogue; can't grep to the spawn code.

### Framework port + plugin
- Ported the patch framework core to **x86**: `crash_report.cpp` (register logging),
  `crash_handler.cpp`, `stack_walker.cpp` (x64 unwind → x86 fallback), `protect.cpp` (`SIZE_T`).
  x64 Rogue build untouched.
- New game target `games/ac/blackflag` (`ARCH x86`): game_data (`exe_name = AC4BFSP.exe`), registry,
  game_entry, `PlayerTransform` hook, ported `CoopNet` transport, and a read-only **`CamProbe`**
  discovery hook.
- Build: `AC.BlackFlag.PatchFix.asi` **1,067,520 B, i386** (x86 build dir `build-x86`).

### In-game result (the milestone)
- Deployed **Ultimate ASI Loader v9.7.4 x86** (`dinput8.dll`) + our `.asi` to the BF root/plugins.
- Backed up BF saves (`um backup` → `ac4-saves`, 46 files, 15.9 MB).
- **The plugin loaded into `AC4BFSP.exe`, installed both hooks, no crash**, and logged:
  `PlayerTransform: pos=(1.3,7.1,1.3) quat=(0.000,0.000,0.913,0.409) mgr=0xC18E860`
  — a live camera transform with a valid unit quaternion. **B1 effectively done** (needs the
  in-world "tracks walking" confirmation).
- **RVA bug found & fixed**: camera-manager RVA was `0x26ABE588`, correct is `0x026BE588`
  (`0x02abe588 − 0x400000`). The bad address failed safely (null manager, no crash).
- Game left **running at the main menu with `CamProbe` armed** so one "Continue" captures the
  in-world player/character data.

### Notes / caveats
- Two later launches needed **Ubisoft Connect** running (`upc.exe`); without it the game silently
  won't start. No wedge occurred this session. **(Corrected 2026-10-06 late: the user reports the
  game runs WITHOUT Ubisoft Connect on this install — treat upc as a fallback only.)**
- Screenshot capture (`um win shot`) timed out; autonomous menu navigation was abandoned (blind).

### Next
1. With the user present: load a save → the log captures in-world transform + CamProbe data → confirm
   B1 "tracks walking", and read the candidate player object for **B3**.
2. Then B2 (two-machine Radmin link).

## 2026-10-06 (cont.) — **B1 verified + B3 anchor confirmed** (with the user, two runs)

Two live runs with the user at the keyboard.

### Run 1 — B1 verified in-world
`PlayerTransform: pos=(-536.8,281.0,2.8) → (-490.3,358.7,3.3)`, `quat=(-0.019,-0.018,0.675,0.738)`
— **live, moving world coordinates with a valid unit quaternion. B1 done.**

### Run 2 — B3 anchor CONFIRMED (walk-and-turn at 4 Hz)
- Walking straight: the `cand − cam` offset is rock stable at `(-0.3, -2.8, -0.6)`.
- Turning: the offset **rotates in XY** — `(-0.3,-2.8) → (2.5,0) → (0.5,+2.3)` — the camera
  **orbits a fixed world point**.
⇒ **`camobj+0x68 → object+0x50` is the player's world body position.** Stable object across 340
samples. Chain: `mgr (0x02abe588) → +0x4C → holder → camobj → +0x68 → obj → +0x50`.

### Enhanced probe built + deployed
`CamProbe` now also dumps the camera target object's **vtable and every pointer field (with their
vtables)** → the next run identifies the *class*. Artifact: `AC.BlackFlag.PatchFix.asi`
1,069,568 B, deployed.

### Dead ends confirmed (do not re-chase)
- Engine **type names have no code xrefs** (`EntityActor`, `AnimatedEntityComponent`,
  `CameraTargetTracker`, `GetCharacterEntityOperator`, spawn types) — reflection-only.
- **RTTI is partial** (mostly Havok/third-party) → classes must be identified via **vtables**, not names.
- `g_MainPlayerPosition` is a **shader uniform**, not a global.

### Gotchas
- The plugin **log rotates at ~1 MB** — copy long captures out promptly (the raw walk window was lost;
  the analysis and the 106 KB `b3-inworld` capture survive).
- Launches need **Ubisoft Connect** (`upc.exe`) running, or the game silently won't start.

### Captures
- `logs/b1-confirmed-20261006-001506.log` (633 KB) · `logs/b3-inworld-20261006-001936.log` (106 KB)

### Next (one run)
Launch + load → probe names the target's class → find the owning **character entity** → match the
BF MP oracle fields (`0x80/0xe8/0x128/0x1f8/0x170`, move-mode `+0x398`) → **controlled write test**
(nudge the body position with the user present).

### 2026-10-06 (later) - writer-hunt attempts

- **Live pointer scan** for the transform block (0x4244D0D0): only **3 pointers** to it - one
  container entry holding an exe float-table pointer (0x01E3F968), and two near-identical
  camera-target entries (position at +0x20). No obvious character owner among them.
- **Static AI path is a dead end**: FUN_00663390 -> FUN_004398c0 is dynamic-array maintenance (not an
  entity iterator), and FUN_0054f3b0 is a TLS setter.
- Built **`bf-coop/tools/find-writer.ps1`**: attaches as a debugger, arms hardware **write**
  breakpoints (DR0-DR3 across four 4-byte fields of the block), reports the writer's **EIP + registers**,
  then clears and detaches. It compiles, attaches, arms (no errors) and detaches cleanly.
- Two live attempts caught **no write** - the block only updates while the player is actually moving,
  and in both windows the game had gone static. Writer still unidentified.
- **Next:** launch -> load a save -> **walk continuously** -> run `find-writer.ps1 -ProcId <pid>`;
  the EIP identifies the writing function, which reads the real character object.

## 2026-10-06 — source-transform capture (param_2) — SUCCESS
- Custom WOW64 debugger tool `tools/bp-capture-param2.ps1`: INT3 at AC4BFSP.exe+0xD2218E (inside FUN_01122150, the camera-target smoother), single-step re-arm loop, up to N hits, clean detach. Works in-game.
- Bugs fixed on the way: (1) WOW64 breakpoints arrive as ExceptionCode 0x4000001F (not 0x80000003) — mishandling crashed the game once; (2) PowerShell aliases (rd/rp) collide with function names — use plain names; (3) tool must wait for a real in-world position (menu pos reads (0,0,1.18)).
- In-world capture (Havana, player ~(-551,274,2)): EAX = 0x44B38810 — ONE source object feeding THREE camera-target providers (0x2F986910 / 0x2FC7CBC0 / 0x2FC7CD00, all vtable 0x02697010; provider+0x100 quat, +0x110 feet pos; chain block+0x174 = 0x2FC7CD00).
- Source object 0x44B38810 layout: +0x00 class ptr 0x01E4CE90; +0x04 id 0x00013457; +0x08 [corrected 2026-10-06 late: a player-only pointer to an identity-matrix attachment — the "= self+0x110" reading was the neighbouring allocation, the node is only 0x100 bytes]; +0x10 4x4 matrix (row3 @+0x40 = translation = feet); +0x60 float 31.69, +0x64 flags 0x001E0022; +0x68 magic 0x04DD5F8C; +0x74 6.68; +0x7C -0.5.
- Camera eye = source feet + ~1.2 m.
- Next: write test on source matrix translation (does the engine accept it?); then find the writer of the source transform (movement/anim update).

## 2026-10-06 (later) — BREAKTHROUGH: writing the source transform MOVES EDWARD
- User-confirmed visually: writing +20m to the source object matrix X teleported Edward (he "watched him teleport to the sides").
- The write STICKS when the player is idle; when walking, the movement system rewrites it within ~1s (write race).
- Class census: vtable 0x01E4CE90 + marker 0x04DD5F8C at +0x68 => ~2650-2670 instances (world objects + character roots + bones).
- Sub-signature: +0x8 == base+0x110 ("self-node") => 69 candidates [corrected 2026-10-06 late: this was an adjacency coincidence, not a marker — ignore].
- Live sample: 6 of 69 moved while the game ran (walking characters/props).
- Tools added: tools/live-test.ps1 (screenshot+shove+scan), tools/scan-npcs.ps1, tools/wait-and-scan-npcs.ps1 (waits for simulation), tools/npc-pop-test.ps1 (teleport an NPC candidate next to the player and hold).
- IMPORTANT: the game PAUSES when it loses focus (any alt-tab) -> memory scans see a frozen world. Scans must wait for movement or run while the game is focused.
- PrintWindow screenshots of this game are unreliable (stale frames); use CopyFromScreen of the window rect or user reports.
- Pending: verify we can move an NPC (pop test); then drive an NPC body from network data = remote avatar.

## 2026-10-06 — AI CHARACTER MOVED (user-confirmed) + character/marker discriminator
- Burst test (tools/shove-edward-and-burst.ps1): captured Edward root via INT3 (0x460CF660 this session; matchDist 0.04 to camera-chain feet), shoved him (visible), then shifted 67 nearby class instances 5m sideways +2.5m up for 3s (all 67 held the write).
- USER CONFIRMED: both Edward and an AI moved. => We can puppet world characters by writing their matrix.
- Discriminator found: child count at +0x66 (== high 16 of flags at +0x64). Edward root = 27 children; other likely characters 18 / 11; markers/props = exactly 1 child (f74=0, f7c=-2.00). Use children>=10 to filter characters.
- Selected object ids are just allocation counters (Edward was 0x13457 earlier, 0x1430E now) - id families are NOT type markers.
- New tool: tools/puppet-test.ps1 - picks nearest character (children>=10, 3-30m) and glides it to 2m beside the player over ~9s, holding at the end.
- Next: confirm puppet looks right; then wire network positions to this drive path (remote avatar).

## 2026-10-06 — NPC PUPPETEERING CONFIRMED (user saw an enemy AI follow them)
- Group test (tools/group-test.ps1): of 76 objects 2.5-15m, only 2 match the "humanoid" signature (f7c == -0.50 + children>=8); 17 are f7c=-2.0 (mostly fight writes back -> engine/animation updates them every frame); 57 others (mostly static).
- Follower using a f7c=-0.50 object (id 0x0000D797, children=19): USER CONFIRMED an enemy AI followed them (teleporting/glitching at the 320ms script rate, AI fighting).
- Earlier failed follow used a f7c=-3.20 object (invisible marker) -> explains "not trailing" report.
- So: visible humanoid bodies = class vtable 0x01E4CE90 + marker 0x04DD5F8C + f7c==-0.50 + children>=8. Drive = write matrix translation (+0x40..0x48).
- Smoothness plan: plugin writes per frame (60Hz) after AI update + interpolation from network packets (10-20Hz).
- Next: plugin feature "GhostBody": find humanoid near player, drive from network position. Local test = simulate friend packets with a script; then real link over Radmin.

## 2026-10-06 — *** CO-OP GHOST CONFIRMED VISIBLE IN-GAME ***
- User: "yup hes circling" — the plugin-driven character circles the player, driven purely by UDP packets (fake peer on 127.0.0.1). Full loop verified: publish(feet) -> peer poll -> body pick -> per-frame drive -> VISIBLE -> release on timeout.
- Picker filter (final): class vtable 0x01E4CE90 + marker +0x68=0x04DD5F8C + f7c(+0x7C) == -0.50 + children(+0x66) >= 16 + dist 2.5..200 m. Real crowd bodies have children 18-19; inactive proxies have 8-14 and never render; the player is excluded by distance (<2.5 m).
- Body pulled in from ~45 m away (it teleports to the peer position - expected for v1; smooth-walk variant later).
- Plugin ini now has live tunables: BodyMinChildren, BodyMaxDist (reload without rebuild).
- GOTCHA: this machine leaves GHOST UDP endpoints when a game session exits (dead pid still owns the port; bind fails 10048). Workaround: use a fresh LocalPort each session (now 27731) or reboot. Port scheme for two machines: A: Local 27731 -> Remote 27700; B: Local 27700 -> Remote 27731.
- Next: friend package (asi + loader + ini + README) for the real Radmin test; then the Edward-model hunt for the ghost's appearance.

## 2026-10-06 — Edward-model quest: anatomy mapped (no swap yet)
- Puppet node class (vtable 0x01E4CE90): +0x00 vtable, +0x04 id, +0x08 player-only identity-matrix ptr (0 on all civs), +0x10 4x4 matrix, +0x60 child array (the RIG), +0x66 child count (player 27, civs 18-20, markers 1), +0x68 handle marker 0x04DD5F8C, +0x7C == -0.50 humanoid flag. Region 0x110..0x1C0 = per-entity VARIABLE data (inline bags; player carries "PuppetTextState1" strings) - not fixed fields.
- Rig (children) classes differ per model: player parts use 0x026CB120 / 0x01E4A1B0 / 0x01E65930 / 0x01E7F568(bones) / 0x01E5EA80 / 0x01E4C9F8 ...; civ parts use 0x01E65930 / 0x01E7F568 / 0x01E5EA80 / 0x01E41E58 / 0x01E6CC50 / 0x026EE050 ... The skeleton is built per model by the anim system - not hot-swappable piecemeal.
- Node +0xE8 = a "controller data" object; its class differs player vs civ (vtables 0x026FA898 vs 0x026E34D8). Graphically these are the "graphic instance" classes created by a factory (FUN_0085f9c0, kinds 0-7) from a definition object.
- SP has NO CharacterSkins/SwapSkin system (only outfits for the player + animation skinning + animal skins). The strings "CharacterSkinsComponent", "ActionSwapSkin", "HIJACK_SKIN", "HIJACK_CURRENTSKIN", "M2All_SwapSkinEventWithId", "D2M_RequestSwapSkin", "D2M_MorphCancelsBodyguardOrDecoy" are in AC4BFMP.exe => MP has the runtime model swap ("morph"/"hijack"/skin selection) on player puppets.
- NOTE for next session: MP project = C:\Users\Administrator\ghidra-bf (AC4BFMP). Key strings found: CharacterSkinsComponent 0x13857B0, ActionSwapSkin 0x13B762C, PLAYER_SKIN 0x13AC828, SkinChangedEvent 0x13A8168, SkinSelectionEvent 0x13A8154, D2M_RequestSwapSkin 0x139601C, M2All_SwapSkinEventWithId 0x1395B30. Next: find the code that APPLIES a skin to a puppet (not the event registrations) and the field it writes; then try the same write on an SP civ body.
- Saves: current AC4 (folder 437) is a fresh prologue; old July-Sept saves (folder 66088) do NOT appear in current install (different SKU); backed up all savegames to bf-coop/saverbak-*.
- Tools added: snapshot-puppet.ps1 + diff-snaps.ps1 (before/after memory diffs), compare-parts.ps1, probe-*.ps1, scan-edward-strings.ps1.

## 2026-10-06 — Edward quest: LAYOUT CORRECTION + verdict
- The puppet node is exactly 0x100 bytes: constructors allocate FUN_00a085b0(0x100,0x10,...) then call FUN_0052a4a0. => EVERYTHING at node offset >= 0x100 is a NEIGHBOURING heap object, not a field. This invalidates my earlier reads of "+0x110 vtable (player)" / "+0x170 vtable (crowd)" / "+0x168 PuppetTextState1" - those are adjacent objects (text/graphic objects allocated next to the node).
- Confirmed real node fields (0x00-0xFF): +0x00 vtable 0x01E4CE90, +0x04 id, +0x08 player-only identity-matrix ptr (0 on civs), +0x10 4x4 matrix, +0x50.. flags, +0x60 children array ptr (the RIG), +0x64 flags/count pair, +0x66 child count, +0x68 handle marker 0x04DD5F8C, +0x74 float, +0x7C == -0.50 humanoid flag, +0x98 self+0x10 ptr, +0xC8 per-character obj, +0xE8 behavior-controller obj (player vs civ classes).
- Graphic-instance factory: FUN_0085f9c0 (kinds 0-7 -> classes FUN_0085bf50/FUN_0085de20/FUN_00870e40/FUN_00924a60/FUN_0085a3b0/FUN_008e6250/FUN_008ea270), invoked via wrapper FUN_00900260 <- FUN_0084a050 <- registered in a .rdata callback table at 0x025934C0. Creation is table-registry driven (not static call-graph reachable).
- VERDICT: "ghost looks like Edward" requires porting the MP skin/spawn mechanism (MP has CharacterSkinsComponent / ActionSwapSkin / HIJACK_SKIN / morph events; SP has only player outfits). Not a memory-write hack. Next session: MP skin-apply path (MP project C:\Users\Administrator\ghidra-bf) + possibility of calling SP's graphic factory from the plugin.
- Practical fallback for now: keep civ bodies; improve motion + pick bodies near the peer position.

## 2026-10-06 - correction
- User confirms: AC4BFSP runs WITHOUT Ubisoft Connect on this install. README/checklist updated (upc optional; only start it if a launch silently exits).


## 2026-10-06 — Edward quest round 2: render parts are vtable-folded blobs (dead end)
- Render parts: class vtable 0x01E7F568 (ctor FUN_00876800; player has 11 render parts among 27 children, a civ 7 among ~19). Player parts embed objects of another graphics class (vtable 0x02596100, ctor FUN_0093F350); civ parts hold heap pointers there instead.
- The field-by-field diff is MEANINGLESS: MSVC COMDAT-folds identical vtables, so two subclasses with different data layouts can share one vtable address. Same vtable != same layout. That also explains earlier "same class, wildly different content" observations (nodes/parts are serialized, relocatable blobs with self-relative offsets and refcounted handles).
- Conclusion: SP graphic objects are data-driven instantiated blobs; there is no clean flat "model pointer" to swap. The model-swap routes remain: (1) MP skin system (CharacterSkinsComponent/ActionSwapSkin/morph/HIJACK_SKIN in AC4BFMP - find the apply-skin WRITE, not the reflection strings); (2) the crowd SPAWN path with a different definition (call/duplicate the spawner with the player's definition). Both are dedicated projects.
- Tools added: tools/probe-instances.ps1 (node+neighbour window + object-like offset scan), tools/compare-render-parts.ps1 (player vs civ render-part diff).

## 2026-10-06 — Outfit scope (user: "not his face, just his outfit") — findings
- Outfits are STORE ITEMS: item category enum 0x26 = "OUTFIT" (FUN_015d6340 resolves localized item names by category `+0x18`, sub-id `+0x1c`; categories: 2=weapons 6=upgrades 9=collectibles 0x33=ship upgrades 0x26=outfit, item id = u64 "0x%08llX").
- "PlayerOutfitEvent" (0x026BCFB0) and "OutfitItemDataMapping" (0x026A9EEC) and "ActionUnlockBonusSkin" (0x026BD2EC): NO code refs (reflection/data-only).
- REAL find: a "Skin" class exists in SP — class descriptor PTR_PTR_02915CFC; property hash 0x971a842e. Setter FUN_012b3d60 ("BonusEntityBuilderSkin" -> stores skin @builder+0x30, then FUN_00a4f9f0(0x971a842e, skin, PTR_PTR_02915cfc)). So mission/bonus-entity data CAN attach a Skin to a spawned entity => there is a spawn-with-skin path in SP. Route: find the getter/consumer of builder+0x30 and the Skin class methods (ctor + apply) in a focused session.
- Plan for outfit-only goal: (A) pragmatic: sample civ clothing variants in-game, user picks the closest "Edward look", bias the ghost picker to that variant; (B) proper: chase the Skin class + spawn-with-skin (BonusEntityBuilder) path so a character can wear a chosen skin.

## 2026-10-06 — graphics-class scan + shared-reference hunt (outfit attempt, read-only)
- Graphic-class scan result: class 0x02595BC8 = 2280 instances, 0x02595050 = 473 instances. NEITHER is a unique "player graphic"/"civ graphic" — they are common component classes. Component objects of 0x02595BC8 carry back-pointers to civ nodes at +0x58/+0x70/+0xC8/+0xD8; nothing in the scanned window referenced the player node. (The earlier "player graphic class / civ graphic class" labels referred to factory creation kinds, not runtime-unique objects.)
- New read-only tool: tools/find-graphics.ps1 (graphic class instance scan + node correlation + raw dumps).
- New read-only tool: tools/find-shared-refs.ps1 — the shared-pointer hunt: collect depth<=1 pointer paths from the character node; a path whose value is IDENTICAL across several same-variant civ bodies but DIFFERENT on the player is a candidate "model/clothes resource" slot. (Also cross-checks a second variant group.)

## 2026-10-06 late — outfit field-probe: definitive negative (field-poke family exhausted)
- Live write-and-revert probe on a civ body (tools/outfit-probe.ps1): TEST B node+0xB4, TEST C node+0x28/+0x30 (+mirrors in +0x98/+0xB0 targets), TEST D node+0x6C, TEST A node+0xD8..0xEC (16-byte variant table). User watched the body 4 m in front the whole time: "nothing happened" — zero visible change in all four.
- Key corrections from the probe log: values at +0xB4/+0x28/+0x30/+0x6C CHANGE between runs (0x229B5 -> 0x24D7F etc.) and are often EQUAL on civ vs player (TEST B/D wrote the identical value back) => they are DYNAMIC state (tick counters/rolling values), not model references. The shared-refs hunt's differential list must be read with this caveat (dynamic fields can accidentally appear "shared across same-variant civs").
- Only the +0xD8..0xEC byte table is STABLE and variant-specific (bone/appearance indices, +7 shift on player due to 7 extra bones); writing Edward's values does nothing at runtime.
- Final conclusion: the visual is built from serialized data at spawn/rebuild time; NO runtime field write changes the look. The outfit requires the engine graphic rebuild/skin path (MP skin port, or the SP spawn-with-definition path) — dedicated project, parked.
- Session net gain: whole field-write approach ruled out with evidence; node-graph semantics documented (controller class civ 0x026E34D8 vs player 0x026FA898; +0x64/+0x66 = children capacity/count); tools: sample-looks.ps1, calibrate-front.ps1, find-graphics.ps1, find-shared-refs.ps1, outfit-probe.ps1.

## 2026-10-06 late — two-machine kit v0.2 (test-day build)
- Ports finalized: A: Local 27800 / Remote 27801 / ClientId 1  |  B: Local 27801 / Remote 27800 / ClientId 2.
  A's live config switched to 27800/27801 (loopback until the friend's IP is set); plugin live-reloaded
  and re-bound instantly ("CoopNet: udp/27800 -> 127.0.0.1:27801 as client 1, 20 Hz"). Port 27731 is
  still held by dead PID 15952 (ghost port — reboot clears; noted for test day).
- Kit built: dist/AC4BF-Coop-v0.2.zip — dinput8.dll + AC.BlackFlag.PatchFix.asi (SHA256 hash-identical
  to the proven local install) + ini prefilled for B (RemoteIp1..4 = 26.113.208.88 = A's Radmin IP,
  LocalPort 27801, RemotePort 27800, ClientId 2) + ASCII README (exact expected log lines, peer/fresh
  semantics, troubleshooting, firewall notes). v0.1 moved to dist/archive/. A-side quick sheet:
  dist/README-FOR-A.txt. New tool: tools/set-remote-ip.ps1 (-Ip [-LocalPort -RemotePort -ClientId]).
- Log semantics documented (source-verified): PlayerTransform "peer=" prints the STICKY struct flag
  (1 forever after the first packet of the session; a config reload does NOT reset it), "fresh=" is the
  real liveness (peer timeout 2 s; ghost body stops being driven when stale, stays assigned). Guides
  say: fresh=1 is the live indicator. Future polish: make the log print liveness directly.
- fake_peer_send.ps1 defaults updated to the new port pair (27800/27801).

## 2026-10-06 17:46 — *** MILESTONE: two-machine co-op ghost LIVE over Radmin ***
- First real two-machine run (user A 26.113.208.88 <-> "Suhiro" B 26.45.65.81, ~105 ms ping, ping 3/3).
- Log proof: "GhostBody: picked body 0x3784D1B0 at 61.5 m from peer" then
  "PlayerTransform: ... peer=1 body=1@3784D1B0 fresh=1 d=13.8..18.9" (distance bouncing as the peer walked).
- User: "yesss i see him in game as an npc woman" — the driven crowd body is visible in-game from the other machine.
- Path to working ports (both sides hit the dead-port 10048 leak this session; live port swaps fixed both):
  final pair A: Local 27810 / Remote 27811  |  B: Local 27811 / Remote 27810. Hot reload while in-game confirmed again on both sides.
- Look = random crowd body (woman) as designed for v0.2; outfit swap remains the parked rebuild-path project.
- Firewall: A-side game has inbound allow rules on all profiles; Radmin adapter profile is "Public" but covered.

## 2026-10-06 17:5x — two-machine behavioral field report (user, live session)
- FACING: confirmed live — "he turns to match". The calibrate-front +Y convention is validated in the real world; one of the big correctness questions is closed.
- Tracking: "choppy a lil but i can track his movement" — expected (live crowd AI fights the driver + 20 Hz + ~105 ms latency + per-frame lerp). Easy candidates: SendHz 20->30, lerp tuning.
- Parkour: "he cant climb on my screen he teleports, some vault animations but glitchy" — expected for v0.2: no animation/custom-action replication; vertical moves snap; the vault-looking anims are the crowd body's own AI. Target for B4/C2.
- Body swap on loss observed by user ("changes npcs when i lose him") — release + repick as designed.
- SESSION RESULT: two-machine co-op ghost working bidirectionally; friend can log off; dev continues on this machine only.

## 2026-10-06 late — B4 recon: action-state fields (read side SOLVED; write-trigger invalid)
- Tool trace-actions.ps1 (focused 150ms sampler + CLIMB z-velocity marker) captured the user's scripted
  sequence (normal vaults, flashy vaults, climbs, wall hang, drops, full roof climb). Field map in the
  PLAYER controller (node+0xE8, class 0x026FA898):
    +0x0E0 = action phase byte: 0x2A while an action runs, 0x07 in the post-action stance
    +0x8D8 = hang/airborne: 0x3F sustained while hanging on the wall (brief pulse during vaults)
    +0x138 bit0 + +0x8D0 bit0 = "in custom action" flags (on at action start, off at end)
    +0x8D4 = 0xBC while running/actioning
    NODE+0x008 (identity-matrix ptr) toggles around actions; NODE+0x054 bit9 + CTL_E8+0x07C bit16
    pulse on landings. +0x0E0..0x0E8 = cached position while moving.
  => B4 read side SOLVED: plugin can publish these as anim_state (protocol field already exists).
- action-write-probe.ps1 (guarded write-and-revert into a CIV's controller at the same offsets):
  INVALID experiment - the civ controller is class 0x026E34D8 with a DIFFERENT layout
  (civ 8D8=0x1DC/138=0x20/8D0=0x01 vs player 0x00/0x37DDD000/0x02630000). Writes hit unrelated
  fields (reverted); no visible effect. Also: body not visible from the rooftop spot (placement off).
  => Play side = engine action API only. MP trail mapped: handler FUN_004d1bed -> FUN_004caa4a
  (processes action object vectors + invokes per-type callback). Next: decompile the callback
  registration + FUN_004c53a0 callers in MP, then map the same function into SP (byte/signature).
- MP message-name cluster catalogued (0x01395xxx): M2R_ReplicateEnter/ExitCustomActionState,
  S2C_SetMoveReplicationMode (writes avatar+0x398), S2C_Transition / S2C_TransitionToLedgeClimb /
  S2C_TransitFromLedgeOrClimbToDieRagdoll (animation transitions!), M2All_SwapSkinEventWithId
  (outfit project door). Message descriptors at 0x01A1C838+ carry {serializer ptr slot, handler,
  name ptr, id}.

## 2026-10-06 late-night — B4 writer hunt: watchpoint round 1 (correction)
- Watchpoint on ctl+0xE0 caught the writer: FUN_00495a70 (thiscall: writes 4 floats at +0xE0..0xEC =
  position cache: `pos - scale*other` or plain copy). So +0xE0 is a POSITION VECTOR, NOT the action
  phase (my earlier field-map label was wrong). Called from FUN_01db8130 (position-cache clear path).
- CORRECTION to the B4 field map: the action-phase values 0x2A/0x07 live at ctl+0x8E0 (not +0xE0);
  hang = +0x8D8, blend = +0x8D4, in-action flags = +0x138/+0x8D0. (The action-write-probe.ps1 also
  wrote the wrong offset for the phase field - civ layout differs anyway; invalid either way.)
- Debugger attach/detach works but the game crashed shortly after the session (known fragility).
- Next: re-run watch-writer.ps1 (now targeting +0x8E0) after the game relaunches.

## 2026-10-06 late-night — B4 desk grind (play-side static hunts + read-side wiring)
- Static writer hunts, exhaustive: all write encodings (C7/89/88/C6 word/dword/byte + movss/movaps/movups
  via displacement-byte search, 571 writes / 392 functions) + LEA [reg+0x8xx] forms (239 functions).
  Result: NO direct [reg+0x8E0]/[reg+0x8D8] writer on the player controller class exists - the action
  fields are written via a block copy or an indirect sub-object path. Top candidates were decoys
  (GPU shader registry FUN_008f0bd0, component-buffer swap fns 00d67d20/00d6f5e0/00d7e290).
  => The live hw-watchpoint on ctl+0x8E0 is the decisive tool (watch-writer.ps1 is patched + ready).
- Plugin read-side WIRED + BUILT (staged in build-x86\bin\Release, NOT deployed):
  player_transform.cpp now scans for the player node (vtable+marker+children>=24 near own pos, every
  10 s), caches node+0xE8 controller, reads phase(+0x8E0)/hang(+0x8D8)/flags(+0x138,+0x8D0 bit0) and
  packs anim_state = (phase<<16)|(flags<<8)|hang; publish() sends it; the PlayerTransform log line
  now prints act=0x%08X ph= hang= fl=. Deploy after the watchpoint session.
- Tools: watch-writer.ps1 (WOW64 hw-write watchpoint, all-thread arming, hit logging; debugged through
  C# warnings-as-errors, Thread32* export name, player-node race -> fresh position + retries).

## 2026-10-06 late-night — B4 WRITER CAUGHT + action machine decoded (play-side map)
- Watchpoint on ctl+0x8E0 (watch-writer.ps1, fixed): 8 hits @0x01AB537C, esi=ctl, all writes of 0
  (idle re-apply - the user never vaulted; the machine runs constantly). Game crashed post-detach
  (same detach fragility; data was out first).
- WRITER = FUN_01ab52c0 (thiscall): registers "BhvAssassin" (FUN_00a1c970 name registry), resolves
  the behavior component (FUN_013aec10(owner+4): component list at [obj+0x60]/count[obj+0x66]) and
  writes the live action struct in ONE BURST: +0x8D4=blend +0x8D8=hang +0x8DC +0x8E0=phase
  +0x8E4/+0x8E5=bytes. (Static sweeps missed it: 6-field struct write, no single-field signature.)
- MACHINE = FUN_01ac1ad0 (BhvAssassin per-frame update; dispatcher FUN_01af9f40): applies request
  slots [owner+0x2F50..0x2F60] (value -1 = unchanged) into the live fields; scripted actions
  override via FUN_00e0e5b0. The REQUEST SLOTS = the write interface for actions.
- Behavior family (name registry): BhvAssassin (player, 0x02697E4C), BhvGenericNPC (crowd,
  0x026E2820 - the GHOST's behavior = next play-side target), BhvAnimal (0x02686EF0),
  BhvForceNavigationSpeedEvent.
- B4: READ solved + plugin wired (build staged); PLAY = find BhvGenericNPC's action interface
  (same request-slot pattern expected) and command the ghost's behavior.

## 2026-10-06 late — B4 play-side fork (behavior census finding)
- Name-lookup census (refs to FUN_00a1c970): ALL code-registered behaviors are "BhvAssassin"
  (~150 functions, 0x01aa0000-0x01af0000 = the assassin behavior family incl. writer FUN_01ab52c0
  and machine FUN_01ac1ad0); world managers use the same lookup (InteriorManager, NavalManager...).
- "BhvGenericNPC" (0x026E2820) and "BhvAnimal" have NO code referents -> crowd/animals register
  data-side (hash-indexed registry), like the reflection strings.
- ARCHITECTURAL CONCLUSION: civ models cannot play assassin actions (no vault/climb animations on
  crowd rigs). B4 play side forks:
  (A) CROWD LOCOMOTION (partial, quick): replicate idle/walk/run and command the crowd behavior's
      navigation (walk-to-target) so the ghost animates walking/running instead of sliding.
  (B) ASSASSIN-BODY SPAWN (full S1): spawn a second assassin-class character (the parked engine
      spawn route - SP spawn path + MP "SpawnPlayerParams"/avatar oracle + graphic factory
      FUN_0085f9c0). Only an assassin body can truly vault/climb.
- Recommendation: A now (co-op feel, kills the slide), B as the next big project (S1 unlock).

## 2026-10-06 late — PROJECT B (assassin-body spawn) recon #1
- Spawn strings (SpawnPlayerParams/SpawnCharacterParams/PlayerSpawnEvent/PlayerSpawnActivatorComponent/
  g_MainPlayerPosition) = data-side only, no code refs (factory/data-driven spawn, as expected).
- NODE CLASS CLUSTER identified: vtable 0x01E4CE90 stored by only 2 functions: FUN_0052a4a0 (ctor)
  and FUN_00526d90; clone = FUN_0052a980 (class descriptor PTR_PTR_0275e670 via FUN_00a380e0,
  allocate via FUN_00a38120, shallow-copies the children array via FUN_00a27550 + flags). Real
  caller of clone: FUN_00503600 (+ 2 null-context refs incl. a vtable slot 0x1e4ce9c).
- => The engine can allocate new character nodes at runtime. Deep spawn (node + parts + graphic +
  behavior wiring) = the load-time player creation path - next: LIVE probe hooking the node ctor
  FUN_0052a4a0 to log callers during game load (the spawn recipe).
- MP: NetPlayer = registered factory (FUN_00c23e4e, named via FUN_00c18fb4) wired by FUN_004fd528;
  ~15 sibling class registrations (0x4fc3xx-0x4ff3xx stubs) = the MP object-class registry.

## 2026-10-06 late — B1 probe DEPLOYED (node-ctor logger)
- Plugin now hooks the character-node ctor FUN_0052a4a0 (RVA 0x12A4A0) and logs each construction:
  "SpawnProbe: node ctor this=.. ret=.. a1=.. a2=.." capped at 400 lines (g_spawn_logs).
  Next game launch -> load a save -> the log's SpawnProbe burst = the spawn recipe; the player's
  ctor caller (ret) = the player-spawn function (the B target).
- Build + deployed: AC.BlackFlag.PatchFix.asi (1,088,000 B) includes: B4 action-state read
  (anim_state packed + act= logging) + this probe.

## 2026-10-06 late — PROJECT B: B1 probe harvested (spawn chain ring 1)
- SpawnProbe census (from the 400-line burst): ret=0xA35A1E x325 (loader mass-spawn),
  0xA38111 x71 (clone path), 0x503338 x2 + 0x73C1D0 x2 (RARE = player-ish spawns).
- Decoded ring 1:
  - FUN_00a359c0 = generic class instantiation (allocate FUN_00a085b0/FUN_004061f0 + ctor call via
    class-descriptor slot +0x30). The loader's "new".
  - FUN_00a380e0 = per-class instantiate; its only caller = the node clone FUN_0052a980.
  - Node class hierarchy: vtable 0x01E4CE90 (ctor FUN_0052a4a0) -> 0x01E4A128 (ctor FUN_00503330,
    +4x4 matrix init from DAT_02abe5a0) -> 0x01E64680 (ctor FUN_006defa0 = FUN_00503330 + vtable).
  - FUN_0073c190 = a vtable-slot "create node + register" method (alloc 0x100 + ctor + FUN_005a8a80
    registration wrapper -> FUN_005a7f20).
- NEXT (B2): find the 0x01E64680 class DESCRIPTOR (scan .data for the ctor dword) - the descriptor's
  +0x30 ctor slot + neighbors = the class recipe; then identify the player-spawn caller chain above
  the x2 ctors.

## 2026-10-06 late — PROJECT B: B2 ring 2 (entity tree + hashes)
- Class descriptors FOUND: 0x0279A418 (class 0x01E64680, ctor FUN_006defa0) and 0x0275CD58
  (class 0x01E4A128, ctor FUN_00504880). Shape: {parent?, name-hashes 0x3F742D26 + unique,
  size 0x160, 0x20, 0x7FFF7FFF, ctor@+0x30}. Nothing points at them directly => HASH-indexed registry.
- Hash 0x3F742D26 = CONTAINER entity type hash: FUN_00865d90 / FUN_009174c0 / FUN_00976010 are
  IDENTICAL recursive tree-walkers: iterate children ([obj+0x140] list, count [obj+0x146]), get each
  child's type hash (FUN_00a1d0d0); if == 0x3f742d26 recurse, else call the per-type handler
  (FUN_00865c20 / FUN_00917420 / FUN_00975e00). FUN_00976010 also iterates a global list
  (FUN_00527210/FUN_00527220) of entities with +0x10 pointers.
  => The load-time creation pipeline: entity tree -> per-type handlers -> class instantiation.
- Hash 0x0984415E = serialization property hash (many FUN_009f55c0 getter sites; type descriptors
  PTR_PTR_02743c94/02744174/02744180/027433ac).
- NEXT: decompile the per-type handlers (FUN_00865c20 / FUN_00917420 / FUN_00975e00) - the player
  type handler = the top-level player spawner (calls the 0x01E64680 instantiation).

## 2026-10-06 late — PROJECT B: B2 ring 3 (creation inventory + player path pinned)
- Instantiation census (400-line new-probe; desc offset read bug - got zeros, ret addresses valid):
  391x FUN_00a201a0 (world-object mass creator) + 9x ONE-OFF creations = ENGINE MANAGER SINGLETONS:
  FireManager (027be478), ObjectBankManager (027502ec), ObjectPackManager (027b84bc),
  GuidanceSystemManager (0278a3ac), SoundManager ("::Sound::Engine::SoundManager", 0276f69c),
  + FUN_00647cf0/FUN_0042e030/FUN_004d7ce0/FUN_006975c0 (component/manager inits).
- => The PLAYER is NOT created via the generic new. Player node creation = the OTHER path:
  ctor census x2 via FUN_0073c190 (vtable-slot "create node + register" method @0x01E68AF4) and
  the 0x01E4A128-class descriptor (0x275CD28, ctor chain FUN_00504880->FUN_00503330->FUN_0052a4a0).
- NEXT (last mile): find the class whose vtable holds FUN_0073c190 (vtable base ~0x01E68A80) ->
  its descriptor + users = the top-level player spawner.
- Plugin state: new-probe hook = THUNK ENTRY hazard (1fps+crash) - DISABLED; action-read scan =
  every-frame-rescan-on-miss = 2fps - DISABLED (g_act_read_enabled=false; TODO incremental scan).
  Both probe builds staged; the deployed build = ctor-probe + scan-disabled (fast).

## 2026-10-06 late — PROJECT B: B2 COMPLETE (clone API) + B3 IMPLEMENTED
- B2 RECIPE FOUND: the character class (vtable 0x01E64680) has a CLONE method at vtable+0xC
  (FUN_006deff0): FUN_00a38120(class 0x2799098 desc, allocator) = new character object;
  FUN_00a2dae0(new, FUN_006dd8d0, &DAT_027f6a44, ..) = clone-setup callback (rig wiring);
  FUN_00503600(new, arg2) = deep copy (node via FUN_0052a980 + state +0x100..+0x148). The
  0x01E4A128 vtable also carries FUN_00503600 (slot 0x01E4A134). Spawn-manager class =
  vtable 0x01E68A30 (ctors FUN_00736600/FUN_00739e50/FUN_00739e90) with create/destroy node
  methods FUN_0073c190/FUN_0073c2c0 (slots 0x01E68AF4/0x01E68AF8). FUN_006dd8d0 =
  clone-customization callback (uses FUN_005034b0).
  => clone(obj, 0, 0) = the engine's own "make a double" (MP decoy feature).
- B3 IMPLEMENTED: plugin [Coop] CloneTest (default false). When enabled, a one-shot SEH-guarded
  scan finds 0x01E64680/0x01E4A128 instances and calls vtable+0xC on each, logging
  "CloneTest: obj=.. vt=.. -> clone=..". Build deployed (1,092,608 B). LIVE TEST NEXT.
- Also deployed: action-read scan DISABLED (g_act_read_enabled=false - was the 2fps culprit),
  new-probe hook removed (thunk-entry hazard). Ctor probe remains (harmless, capped 400).

## 2026-10-06 late — B3 first live attempt: clone(0,0) WEDGES the game
- Fresh session with CloneTest=true: ctor burst at load, then silence - no pos lines, no CloneTest
  lines. The clone call runs BEFORE the log section in the hook -> it deadlocked/blocked forever
  on the first in-world frame (engine clone with nullptr allocator args = lock/loop). Game wedge.
- Reverted CloneTest=false. NEXT: decompile the engine's OWN clone caller (the decoy system) to get
  the correct allocator/context args; retry with real args. The clone API itself (vtable+0xC on
  class 0x01E64680) is confirmed reachable.

## 2026-10-06 late — PROJECT B: B3 attempt #1 diagnosis + clone protocol decoded
- Sync clone (vtable+0xC, FUN_006deff0) called from the camera-hook thread = WEDGES (no crash; the
  hook thread deadlocks inside the clone's TLS job-context path FUN_00a2dae0 -> FUN_00a39360; the
  main loop keeps running - user could still walk). Wrong thread, not wrong args (FUN_00a38120
  handles allocator==0 by allocating+constructing via desc+0x30).
- Clone protocol decoded:
  - FUN_00503600 = the deep copy: FUN_00a27550 iterates children and calls EACH CHILD'S clone
    (child vtable+0xC) - recursive deep clone.
  - Async slot (vtable+0x8, FUN_006def40) posts a job (FUN_009ee1d0) + FUN_00505770:
    SERIALIZATION-based rebuild - reads a stream (cursor +0x14/cap +0x18), property hash 0x984415E
    via FUN_009fc0b0 (writer) / FUN_009f55c0 (reader), descriptor PTR_PTR_0275afb8.
- B3 remaining: invoke via the engine's job queue (FUN_00a39360/FUN_00a40bd0 post into the TLS
  job context) or the async slot with a proper stream - then one live test.
- CloneTest reverted to false; the deployed build is inert again (co-op + ctor probe only).

## 2026-10-06 late — B3 fix: clone moved to the MAIN thread
- Root cause confirmed: the clone must run on the engine's main-thread job context; the camera-hook
  thread deadlocks inside FUN_00a2dae0/FUN_00a39360 (the game keeps running - it was a thread-local
  deadlock, matching the log exactly).
- Fix implemented: a second hook on the game's MAIN window loop (FUN_004060a0, RVA 0x60A0 -
  the PeekMessage loop, main thread) triggers clone_test_tick() when CloneTest is armed + the
  world has been seen (g_world_seen set by the camera hook). Clone args unchanged (0,0 - they were
  fine; FUN_00a38120 handles null by allocating).
- Build staged (game running during deploy); deploy + CloneTest=true + relaunch = the retest.

## 2026-10-06 late — B3 definitive findings (invocation blocker pinned)
- Diagnostic build (heartbeat + clone-probe): NO main-loop heartbeat in gameplay => the boot window
  loop (FUN_004060a0/FUN_00407390) is BOOT-ONLY; the real gameplay loop is elsewhere.
- The engine NEVER calls the clone during normal play (no clone-probe hits in free-roam) - the clone
  = decoy/mission-only feature.
- Job helpers = intrusive list/alloc structures (FUN_00a5a130 = sorted insert; FUN_00a1c9d0 = stub;
  FUN_00a476b0 = wrapper). No global "post to main thread" API found.
- => B3 remaining options (next session): (1) CALL THE CLONE PIECES DIRECTLY from the camera thread,
  skipping the TLS job-context setup (FUN_00a2dae0 = the deadlock site): FUN_00a38120(desc,0) +
  FUN_0052a980 + FUN_00a27550 + state copy - all mapped; (2) find the real gameplay main loop with a
  multi-hook heartbeat probe kit, then run the clone there.
- CloneTest=false restored; deployed build = diagnostic probes only (inert in gameplay).

## 2026-10-06 late — OPTION 2 step 1 done: the thread census (92 threads mapped)
- ThreadCensus (plugin, NtQueryInformationThread start-address enumeration): 92 threads.
  KEY IDENTIFICATIONS:
  - MAIN THREAD = tid 3936, start 0xF199C6 = the CRT entry -> ___tmainCRTStartup -> main()
    (symbols stripped; main()'s loop = the next target - follow the CRT startup's call).
  - 0xF1DE71 x~24 (prio 7-9) = the generic worker pool (__threadstartex wrapper; incl. the camera
    thread 24308 - so the camera update = a pooled worker, NOT the main thread; explains the
    clone deadlock: worker TLS context vs the engine's job lock).
  - 0x6803C99E x~38 (prio 1) = low-priority background pool.
  - 0xD00750 (prio 8) = COMMAND-QUEUE executor (critical section + 9-dword command pop + switch
    dispatch: FUN_00cff6c0/FUN_00cfccf0/FUN_00d00310/...). Route C: post a clone command here.
  - 0xD44BB0 / 0xD08970 = event-driven dispatchers (WaitForMultipleObjectsEx / WaitForSingleObject
    + per-tick vtable calls).
  - 0x5364A670 x2 (prio 22) = high-priority pair (unanalyzed region).
- THREE ROUTES to run the clone safely: (A) find main()'s per-frame loop -> hook -> clone;
  (B) the command-queue thread -> post a clone command; (C) bypass the job-context (reimplement
  the clone pieces - fragile). Priority: A then B.
- Plugin now ships the ThreadCensus instrument (CloneTest flag triggers it; harmless).

## 2026-10-06 review (dead-end check) - the clone = a JOB-POSTING CHAIN, not a pure copy
- Decompiled the clone + the deadlock site (Action72/73SP):
  - FUN_006deff0 (sync clone) = FUN_00a38120(allocate) + FUN_00a2dbd0(init task desc) +
    FUN_00a2dae0(POST JOB: callback FUN_006dd8d0) + FUN_00503600(deep copy).
  - FUN_00503600 + FUN_0052a980 ALSO post jobs (callbacks FUN_005034b0 / FUN_00527270).
  - The "setup callbacks" = trivial one-liners (FUN_006dd8d0 = 9 bytes -> FUN_005034b0()).
  - FUN_00a2dae0 = lazy TLS job-context init (alloc 0x7f0 + FUN_00a2d4f0) + enqueue
    (FUN_00a39360 = pure append, no lock). So the hang = the job-post/TLS-init path,
    NOT the copy logic.
- VERDICT: the thread-hunt (sampler) solves the wrong problem - the clone can be made
  thread-agnostic by BYPASSING the job posts: hook FUN_00a2dae0 and, during the clone
  test, call the callback INLINE (param_2 = the callback) instead of enqueueing.
- Next move: inline-callback clone test (hook FUN_00a2dae0 = run-callback-inline mode).
  The sampler v2 = built + kept as fallback (deployed only if the inline test fails).

## 2026-10-06 evening - B3 clone LIVE-PROVEN (visibility pending)
- The clone (vtable+0xC = FUN_006deff0) = called from the camera thread:
  - Healthy mid-class object (vt 0x1E4A128) -> clone COMPLETED, returned 0x2AF96850 (no deadlock!).
  - The old "deadlock" = actually uncaught AVs (0xC0000005) on stale candidates - the camera
    thread's TLS job-context init (FUN_00a2d4f0) runs fine (JobCtxInit logged, no hang).
- The clone = a job-posting chain: allocate (FUN_00a38120) + post setup callbacks
  (FUN_006dd8d0/FUN_005034b0/FUN_00527270/FUN_006470d0 via FUN_00a2dae0) + deep copy
  (FUN_00503600/FUN_0052a980). The setup callbacks now run INLINE in the JobPost probe
  (runner convention: ecx=obj, 2 zero stack args; thunks forward ecx) - verified return 0x0.
- The world holds only 1-3 character-class objects (player + story NPCs; crowds = a different
  class). Static .rdata has exactly ONE character vtable with the clone slot (0x01E64680);
  the mid-class vtable is runtime-built. The scan now matches the clone-slot signature
  (vtable+0xC == FUN_006deff0) to catch every cloneable subclass.
- Remaining: clone a healthy candidate + verify a VISIBLE second body (each clone is offset
  +3 m on X across the four copied Vec3s).
- Gotcha: PC-level freeze at launch after repeated forced kills - the machine needed a
  log-out/log-in (driver state). Boot path = unchanged across 5 good boots.

## 2026-10-06 late - the ASYNC clone = the engine's complete spawn recipe (the render-safe route)
- Decompiled the spawn API (Action78-81SP):
  - Mass creator FUN_00a201a0(classId, keyLo, keyHi, 0) -> FUN_00a33f00(classId) resolves the
    class descriptor -> instantiate -> vtable[2](stream) deserializes -> FUN_00a0bb40 registers.
  - The player's class descriptor 0x275CD28: hash 0x0984415E (the classId), size 0x160,
    ctor FUN_00504880, setup FUN_005034b0.
  - The ASYNC clone (vtable+0x8 = FUN_006def40) = serialize the source + post the job with
    queue template 0x27F6A3C (vs the sync's 0x27F6A44) -> the engine deserializes = a
    complete renderable character. THIS is the render-safe path (the sync clone = a data
    copy the renderer rejects = the GPU freeze).
- Plugin now: offsets the candidate's live transform +3 m, calls the async clone, restores.
  If the 0x27F6A3C template = the main-thread queue, the engine spawns the copy +3 m away.

## 2026-10-06 final - session banked: the prologue is the blocker, not the code
- Chain-dump build (node -> +0xC8/+0xE8 character objects + async clone): the player node =
  NOT FOUND (finder returned 0). The B4 find_player_ctl chain was mapped on a FREE-ROAM save;
  the PROLOGUE puts the player in a scripted state (Duncan's outfit, scripted sequences) whose
  node signature doesn't match (vt 0x01E4CE90 + marker 0x04DD5F8C + children>=24).
- This also explains the earlier clone weirdness (the AVs on "stale" objects = scripted-state
  characters).
- NEXT SESSION (resume on a free-roam save): the chain dump + async clone = the first run;
  the complete character object (valid entity ptr at +4) = expected at node+0xC8/+0xE8.
- Desk knowledge banked this session: the clone protocol (sync = job-posting chain, setups =
  one-line callbacks, runner convention ecx=obj+2 zero args, enqueue = AV at 0xA393B2 on
  non-engine threads); the spawn API (FUN_00a201a0 + classId 0x0984415E + vtable[2](stream)
  deserialize + FUN_00a0bb40 register); the async clone = serialize + post via template
  0x27F6A3C = the engine's complete spawn recipe; the serializer reads [this+4] (entity ptr).

## 2026-10-07 - RTTI tip re-verified (friend's suggestion)
- Checked AC4BFSP.exe for MSVC RTTI name strings (.?AV...): 0 found - the names are stripped.
  The RTTI structures exist (the type-info/COL hierarchy we used early on), so an RTTI
  analyzer could rebuild the class graph but not the names. The hierarchy = already mapped
  via the ctor chain (0x01E4CE90 -> 0x01E4A128 -> 0x01E64680).
- Node ctor (FUN_0052a4a0) desk pass: +0xC8 = the marker constant again (self-ref), +0xE8 =
  the post-ctor character link (set by the character init) - confirms the chain-dump probe's
  +0xE8 hop as the right target for the resume on a free-roam save.

## 2026-10-07 - Route B progress + the freeze lesson
- The log shows the last run: world found instantly (candidate 0 = 0x31B4C040, vt 0x1E5C92C =
  the AI-world vtable!); spawn = SUCCESS (0x2B20AC20, vt 0x1E4A128, no AV); attach =
  FUN_0043a190(world, obj) = AV (SEH caught, returned 1) -> then the game/PC froze.
- LESSON (hard): engine calls that AV inside the game leave half-done state that kills the
  game slowly (the freeze). Each wrong-arg attach attempt = a freeze risk. NO more
  guess-and-launch attach attempts on the user's machine.
- The attach's call requirements (desk, next): FUN_0043a190 reads world+0x924 (the spawn
  manager) -> checks mgr+0x3b (spawning enabled) -> position provider FUN_0045be70 ->
  FUN_00692c70(register) + FUN_016a8f70. The AV is inside this chain - needs FUN_0045be70's
  context + FUN_00692c70's args desk-verified before any live attempt.
- Banked assets: the world object finder works (vt 0x1E5C92C); the unkeyed create is proven
  safe (twice); the runtime spawn system is fully mapped (SpawningManagerUpdate1/2 =
  FUN_00455240/FUN_00455310; request queue FUN_005a8700; record FUN_00463cb0; completion
  FUN_00449600 = find-by-key; attach FUN_00441ec0 -> FUN_0043a190).

## 2026-10-07 (day 2) - THE HASH IS CRC32 + THE SP WALKING SPAWN API
### The big cracks
- **name -> id hash = plain CRC32** (verified on three known pairs):
  SaveGame -> 0xBDBE3B52, MissionHistory -> 0x84A80CC2, ManagedObject -> 0xBB96607D.
  Also reversed: 0x0984415E = crc32("Entity"), 0x3F742D26 = crc32("EntityGroup").
  => every id in the engine = CRC32 of an English/simple name. Enables name->id generation.
- **The crowd/free-roam spawn API = FUN_005fd730(template_hash)** (RVA 0x1FD730):
  uint FUN_005fd730(hash) = get template slot (FUN_005fac60(manager, hash)) -> instantiate via the
  template's +0xC (node-copy FUN_00503600-family) -> FUN_00526590 (activate flags/speed) ->
  FUN_00a2e820 (job flush). Caller = the streaming code (ret 0x602CE0 x94, 0x602B34, 0x6060F3).
- **Live capture (read-only): 96 spawn calls, ALL with the same template hash 0x49BB47AC**
  (the area's crowd type). Node creations during gameplay go through FUN_00503600 (the same
  primitive the sync clone uses) from the spawn API callers.
- **Population manager** found live (vtable family 0x1E577E0-0x1E578A0, e.g. vt=0x1E57830);
  template catalog = 3584 entries; spawn manager global = *(world+0x924).
- The mission spawner (SpawningManagerUpdate1/2 = FUN_00455240/00455310 + request queue +
  FUN_0043a190 attach) is MISSION-GATED: in free-roam the slot list = empty and the spawn
  manager's +0x28 = null (the attach AVs -> my attach call left half-state -> game freezes, twice).
  => Not usable for free-roam spawning; the crowd path (FUN_005fd730) is the working free-roam one.
### Data assets + tooling (bf-coop/tools/)
- hashprobe.py (hash function identification), hashreverse.py/2 (exe-string reverse), hashbrute.py,
  forge_sweep.py/2, forge_full_sweep.py (running: all forges, all names x all hashes),
  save_names.py -> **forge_names.txt = 6.2M unique names from all forge TOCs (persistent corpus)**,
  multi_hash_sweep.py (corpus x 7 hash functions vs 0x49BB47AC - pending run).
- game h2: the crowd template 0x49BB47AC is NOT crc32 of any exe string nor any forge TOC
  name/part (30M+ tests) -> likely a deeper/compressed name or another namespace; the
  multi-hash + full-file sweeps are the open net.
### Direction (user decision)
- SP assassin NPC skins (Tulum assassins / story NPCs) - MP skins deferred. Plan: find the SP
  assassin character template NAME -> crc32 -> id -> spawn via FUN_005fd730 with the engine's own
  context. Correlated names visible in forge data: CM_DL_FT_CHR_Assassin_Edward_Cloth_And_Gear,
  10 - Assassin's Suit, ACGA_h_assassina_* (animations), ACGAMP_* (MP character assets).

## 2026-10-07 - template-id reverse-hash hunt = EXHAUSTED (negative result, definitive)
- Full sweep of ALL forge data files (worlds, DLC, MP, skins - every file byte-by-byte):
  63,080,151 unique names, 274,020,807 CRC32 tests (names, parts, joins with / \ . _ - space,
  case variants) against the captured ids (0x49BB47AC crowd, 0x462A56BC + 0x4718F87C Tulum,
  plus catalog keys) = ZERO matches.
- CONCLUSION: class names use CRC32 (Entity, EntityGroup, ManagedObject, SaveGame, MissionHistory
  all verify) but TEMPLATE/INSTANCE ids are NOT name hashes - they come from the engine's own
  allocation/data scheme. Ground truth = the ids captured from the engine's live spawn calls.
- The empirical route stands: capture (done) -> replay the engine's own spawn call with the
  Tulum id (0x462A56BC then 0x4718F87C) = the replay build (deployed; plugin now disabled while
  the user plays).
- Also: 5 minidumps found in the game plugins folder (19:20-21:24 yesterday) if crash
  archaeology is ever needed; plugin removal done via rename to .asi.disabled + ini flag off.

## 2026-10-07 - save swap (folder 437)
- Replaced current AC4 saves in 437 with the converted set from Downloads\1 (ACST 2.6.1; converted in GUI to current install key).
- Pre-swap saves, incoming originals and converted outputs: bf-coop/saverbak-20261007-200257/.

## 2026-10-07 - FORGE EXTRACTION WORKS (the data door opens)
- Tooling: QuickBMS (github.com/LittleBigBug/QuickBMS releases, quickbms_win.zip; the
  aluigi/quickbms site 403'd) + RetingencyPlan's compendium scripts:
  - scimitar_alt.bms = THE working AC4 forge extractor (handles the multi-tab/chunked
    "new" scimitar format; scimitar_new.bms = AC1-era, prints "more tabs are here").
  - Companion: scimitar_compressed_container.bms (LZO1X/LZO2A/xmemlzx containers, TOC+data).
- Pipeline: quickbms.exe -o scimitar_alt.bms <forge> <outdir> with newlines piped to
  auto-answer invalid-filename prompts. Verified on dlc_1\DataPC_1_dlc.forge (3 files:
  GlobalMetaFile + hashed-name files).
- Running: full extraction of DataPC_extra_chr.forge (1.4 GB, the character data) to
  D:\bf4_extract\extra_chr - payloads decompressed = the character assets/model files,
  searchable by name (partial naming) and by content (archetype ids as bytes).
- Purpose: find the assassin NPC model/outfit assets + the crowd/archetype specs by name,
  instead of hash-guessing. Complements the live capture ids (0x462A56BC / 0x4718F87C).

## 2026-10-07 late - THE SPAWN SYSTEM FULLY MAPPED (recipe census!)
- Hooked the engine's own mass-creator (FUN_00a201a0): 580 real calls captured at load with
  classId + keys. KEY FINDINGS:
  - The "Entity" class (classId = crc32("Entity") = 0x0984415E) is created with keys
    (keyLo = a 32-bit world hash, e.g. 0x4B8EBB55; keyHi = a small block index, 7/8).
  - The dominant class 0x9467F2BB (x246) uses key (0,0) = world statics (props).
  - FUN_00a359c0 (the instantiator) = ONLY calls the registration (FUN_00a20230/FUN_00a20f40)
    when the key pair is NON-ZERO. Our earlier direct spawns used (0,0) -> unregistered
    shells -> invisible + crash-prone. With a non-zero key: registered, stable, no crash
    (proven: Entity + key (0xACE00001,1) = created + game ran fine).
  - The entity CONTENT (model/parts) = filled from the world database BY THE KEY; a fake
    key = a valid but EMPTY body (children=0). Real keys (hash, block 7/8) = the loaded world
    entities (the 9 full bodies found by the scan = children 19-32, f7c=-0.50).
- FUN_005fd730 (the earlier "spawn api") = spawns PARTS (children 1-11, f7c random) - it is
  NOT the character spawner. The full bodies = "Entity" class instances.
- EXTRACTION TOOLING COMPLETE: all ~25 forges extracted (~90k files, ~15 GB, D:\bf4_extract)
  via QuickBMS + scimitar_alt.bms (RetingencyPlan compendium; quickbms from LittleBigBug
  GitHub mirror). The character forge = fully NAMED (CHR_U_AhTabai, CHR_P_Aveline, guards,
  crowds). 45M content strings + 63M TOC names CRC32-tested: the template ids are NOT
  name hashes - they are runtime keys. Hash-reverse hunt = CLOSED with certainty.
- NEXT SESSION (one clean experiment): spawn Entity with a real-style key (fresh keyLo, 
  keyHi=7/8) + apply an archetype; if the body stays empty, capture a live body's key and
  feed it to the deserialize path (the +4 data). The clone work, the parts, the registration,
  and the key system are all now understood.

## 2026-10-07 - FULL REVIEW (documents audited + rewritten)
### PROVEN (evidence-backed)
- Two-machine link live (Radmin): position/facing read, UDP, peer=1 fresh=1, ghosts seen both sides.
- B4 read side: anim_state packed + logged.
- Spawn system fully mapped (RE-NOTES CURRENT TRUTH): classes = CRC32 names (Entity=0x0984415E),
  mass creator + key system + keyed registration; census 580 calls; ids = runtime keys (hash hunt
  closed at 108M+ string tests).
- Tooling: QuickBMS + scimitar_alt (all forges extracted, D:\bf4_extract ~90k files); reimport
  pipeline proven (diff-verified, same-size swaps, backup D:\bf4_mod\backup).
### CLOSED (with certainty)
- Runtime entity creation: engine creates characters ONLY at world load; mid-game creation chokes
  the renderer (audio-continues freezes; ~6 approaches). DO NOT RETRY.
- Hash-reverse hunt. Mission-spawner route (gated). Field-poke outfit family (looks via mod instead).
### THE OPEN PROBLEM + THE AUDIT OF MY CLAIM
- The hijacked body = streamed away/re-picked ("a haunting" - user verdict = the real blocker).
- My persist-hijack claim (detach from streaming): SUPPORTED (scene-registration marker fields
  +0x68/+0xC8/+0xE8; bodies ARE lost on streaming) but the CULL MECHANISM IS UNPROVEN (registry by
  key? septum? refcount?). Documented as hypothesis; next live test = pin the mechanism (watch a
  body die across a cell unload).
### THE NEW LADDER (user spec, in order)
- P1 persistent body (persist-hijack) -> P2 unique look (mod) + HUD marker -> P3 parkour animations
  (B4 play) -> P4 host-authoritative kill sync -> P5 ships.
- True hosted world = OUT OF SCOPE (no netcode in the SP engine); host-authoritative two instances
  = the correct framing everywhere.
### Docs updated
- RE-NOTES.md CURRENT TRUTH box rewritten (big picture + spawn truths + tooling + open list).
- PLAN.md: status rewritten, Project B closed/carried into P1+P2, priority ladder added, risks
  rewritten (the haunting = CRITICAL row).
- PROJECT-PLAN.html: B3 row rewritten (persist-hijack path) + review timeline entry.

## 2026-10-08 — C1 session + event channel built (netcode); full-RE corpus started

### Netcode (the user's "build the netcode")
- `coop_proto.hpp` extended: `Hello`(40B)/`Welcome`(44B) + `EventPayload`(48B) — done earlier.
- `coop_net.cpp` now implements:
  - **Handshake:** guest sends Hello every 500 ms until Welcome; host answers each Hello with a
    Welcome carrying its session_id (throttled 250 ms); 5 s silence = peer timeout -> drop to
    re-handshake; guest re-hellos every 5 s even when established (survives a host restart).
  - **Event channel (reliable-ish):** outbox resends unacked events every 250 ms (max 8 sends),
    acked via `PlayerPayload.ack_seq` as a cumulative ack; inbox dedupes by `event_id` and tracks
    the cumulative received mark; inbox cap 256 with a warning.
  - `SessionInfo` (role/established/session_id/peer name+id); `send_event()`/`drain_events()`.
- Config: `PlayerName` (custom `bf_coop_string_field` — `std::atomic` cannot hold a string) +
  `IsHost`; `field_count` 14 -> 16; wired in `on_reload`; events drained + logged in `SampleCamera`.
- Release build clean; deployed to the live A-side plugins folder; `CloneTest=false` set (the
  spawn experiments stay off). **In-game verify pending** (game was closed; local loopback recipe
  in dist/README-FOR-A.txt).
- **Kit v0.3** shipped: `dist/AC4BF-Coop-v0.3(.zip)` — Player B preset (guest: `IsHost=false`,
  `PlayerName=PlayerB`); both READMEs updated with the new expected log lines
  ("session established (host|guest)").
- **Fake peer upgraded:** `tools/fake_peer_session.ps1` — host/guest modes; speaks the handshake,
  sends Events (incl. a deliberate duplicate) and verifies the plugin's cum-ack + dedupe.

### "RE all of Black Flag 4" — the full corpus
- Mass decompile launched (Ghidra headless, `ghidra_scripts/ExportAllDecomp.java`): every function
  of `AC4BFSP.exe` (**135,105 functions**) -> resumable C batch files in
  `C:\Users\Administrator\bf4_re\sp_src` (500 fns/file, state file resumes where it stopped).
  MP exe (106,900 fns) queued to follow (project `ghidra-bf`).
- `gamedb` built (`C:\Users\Administrator\gamedb`) + installed to `.local\bin` — once the corpus is
  indexed, function/string/call-graph queries are instant (`gamedb search/strings/read/graph`).
- Purpose: institutional knowledge at machine speed for P1-P5 (persist-hijack cull mechanism,
  HUD marker projection, animation state machine, kill detection) instead of ad-hoc Ghidra runs.

### Corpus COMPLETE (2026-10-08, same day) — both exes decompiled + indexed
- AC4BFSP.exe: 135,108 functions -> sp_src (272 files), indexed: 134,020 fns / 361,841 edges / 12,845 strings.
- AC4BFMP.exe: 106,900 functions -> mp_src (215 files), indexed: 106,269 fns / 283,506 edges / 15,463 strings.
- Total corpus: ~240k functions, ~645k call edges, ~28k strings — all queryable via gamedb in seconds.
- First probes: string->function join works (found `FUN_01c41480` = per-tile `unloadTile` walker, a P1 streaming-cull candidate; caller trace pending).
  MP skin events found (`D2M_RequestSwapSkin` @ FUN_004cdd2a, `M2All_SwapSkinEventWithId` @ FUN_004ce584) — P2 skin-apply path still to be traced from these.

## 2026-10-08 (2) - P1 RE: the Entity lifecycle + the cull-hunt map

Corpus-driven (gamedb over sp_src/mp_src). All addresses = SP exe.

### Entity class lifecycle (the full bodies, vt 0x01E4CE90)
- **ctor**: `FUN_0052a4a0` (RVA 0x12A4A0; sets vt 0x01E4CE90, init fields, allocates children array at +0x60 count +0x66).
- **base dtor**: `FUN_00526d90` - sets vt, destroys children array (+0x60/+0x66), refcount-dec on scene ref +0x68, frees arrays +0x78/+0xA0/+0xD4, calls module-unregister helpers `FUN_00a385c0(1)`, `FUN_00a2f220`, `FUN_01426100` x2, `FUN_0063c280`.
- **deleting wrapper**: `FUN_0052a950` (dtor + optional `FUN_00f177aa` free).
- **derived body classes**: dtor `FUN_004ffe70` (vt 0x01E4A128; direct callers `FUN_00503480`, `FUN_006defc0` - the create/clone family) and `FUN_008a0fc0` (vt 0x01E809A0). Both chain to the base dtor.
- **destruction is VIRTUAL** - the base dtor has no direct callers (vtable slot 0 dispatch) => static call-graphs are blind here; the live test must catch it.

### Entity registry (key -> instance)
- find-by-key `FUN_00a1f160` -> hash scan `FUN_00a1e8d0` (array at this+0x10, count u16 at +0x16, 16-byte entries {kLo,kHi,owner,entity}); instantiate `FUN_00a359c0` (alloc -> register `FUN_00a20230` -> descriptor ctor slot +0x30 -> promote `FUN_00a20f40`); class lookup by id `FUN_00a33f00`; create-by-id `FUN_00a201a0` (lookup + find + instantiate).
- class ids: Entity = 0x0984415E confirmed used in serializer metadata (`FUN_009f55c0(0x0984415E, obj+0x68, ...)` - the +0x68 field IS the entity-class reference).

### The cull test plan (P1 oracle)
- Live: hijack a body; at a zone crossing catch ONE of:
  (a) dtor fires with ECX = body        -> instrument `FUN_00526d90` / `FUN_004ffe70`
  (b) body detaches but survives        -> write-watch body+0x66/+0x68 / vt
  (c) body still alive but stops rendering -> scene-ref path (0x68/DAT_04dd5f8c no longer meaningful)
- Plugin build: **CullWatch DONE + deployed** (2026-10-08 00:42; `CullWatch=true` armed in the A-side ini; read-only, 10 Hz, logs only changes). Live test now = netcode session verify + ghost drive + ZONE CROSSING with CullWatch logging.

## 2026-10-08 (overnight) - FULL-RE PROGRAM: corpus + maps + plans

Data (all in C:\Users\Administrator\bf4_re\analysis, queries via gamedb in seconds):
- vtables: SP 15,201 / MP 10,269 (addr, slots, ctor/dtor refs per class)
- globals: SP 149,144 / MP 92,902 referenced data symbols (with reader/writer functions)
- strings with ADDRESSES + refs: SP 98,478 / MP 62,358 (hook anchors)
- features/callers/strings/propnames per function for both exes; 1,048 SP<->MP cross-matches;
  merged naming table (3,660 proposals); top_classes_{sp,mp}.tsv (most-referenced vtables).

RE findings (docs in bf-coop/):
- RE-NETCODE-ORACLE.md: MP event system decoded - registration hub FUN_004ce584, message
  descriptor layout {vtable, pack, 0, id, apply, name}, M2R custom-action chain
  (FUN_004d9140/FUN_004d1bed/FUN_004caa4a), S2C_NotifyDamageKill sender FUN_00567b52 +
  descriptor cluster FUN_01371b96/bdb/c20, speed events.
- RE-CANDIDATES.md: P2 marker candidates (PLAYER_MARKER_ADD FUN_01223790 etc.), P3 parkour family,
  P4 Action_Assassinate, P5 ship-type map FUN_01045cd0.
- RE-P3-PLAN.md / RE-P4-PLAN.md: concrete designs for the next live tests.
- entity lifecycle (P1): ctor FUN_0052a4a0 / dtor FUN_00526d90 (+ wrapper FUN_0052a950) /
  derived dtors FUN_004ffe70/FUN_008a0fc0; destruction virtual -> CullWatch live test armed.
- OVERNIGHT-REPORT.md: the full digest.

## 2026-10-08 (day) - P3 PLAY SIDE IMPLEMENTED (write-through) + built + deployed

- `ghost_body`: new `AnimDrive` mode ([Coop] AnimDrive, armed in the live A-side ini). Each frame,
  when the peer sample is fresh, the ghost body's controller (node+0xE8) gets the packed action
  state replayed: +0x8D8 hang (u8), +0x8E0 phase (u8), flag bit0 of +0x138 / bit1 of +0x8D0 -
  the exact B4 read-side layout, same class (vtable 0x1E4CE90 family).
- `coop_net`: RemotePlayer now carries `anim_state` (it was sent since v0.2 but never stored).
- Guards: controller pointer sanity + page readability before every write; 10 s diagnostic log
  ("GhostBody: anim drive ctl=... phase=... hang=... fl=...").
- Build clean; `.asi` deployed; `AnimDrive=true` + `CullWatch=true` armed for the next live run.
- UNVERIFIED in-game: whether the NPC's own AI fights the writes / whether the pose visibly
  changes - that is the next live test (solo with the fake peer works; no second machine needed).

## 2026-10-08 - SOLO P1 TEST (fake peer): body follows, crash at the boundary

Setup: plugin as host (udp/27820 -> 127.0.0.1:27821), fake peer (guest) circling the player,
AnimDrive + CullWatch on, crew-member body 0x37EB8060 picked near the ship.
- FAIL 1 (rig bug): the fake peer's menu gate (|x|+|y|>100) cut packets when the player walked
  to coords ~(26,-72) -> body froze -> user saw "detach + reattach when returning". Not the game.
- PASS: with the gate fixed, the crew body followed the player through the whole walk
  (x: 102 -> -24 = ~126 m) with err < 0.5 m; NO CullWatch events, NO body loss. The driven body
  survives being dragged across that whole stretch - the cull is not a simple distance leash.
- CRASH at ~135 m: AC4BFSP.exe AV (0xC0000005) at RVA 0x1FFE2A - inside FUN_005ffc60
  (crowd/parts release walker; only caller FUN_01440b80 = a registered release callback).
  Happened while sprinting along the same route, at the moment the engine released crowd state.
  Windows Event Log: faulting module AC4BFSP.exe, offset 0x005ffe2a. No plugin VEH line.
- Next: repro run (same walk) -> if repeatable, instrument the release callback (log args),
  then try the controlled-release mitigation (drop the driven body before ~90 m and re-pick).

## 2026-10-08 (day 2) - SOLO RUNS 2/3: crash isolated + THE OBJECT IS NEVER CULLED

- Run 2 (AnimDrive ON, same walk): crash at ~40-50 m, but a DIFFERENT signature: faulting module
  "unknown", fault offset 0x70014261 (wild jump) = memory corruption.
- Run 3 (AnimDrive OFF, everything else same): player crossed the WHOLE MAP (x 102 -> -240, 350+ m),
  body followed with err 0.02-0.43 m end to end. NO re-picks, NO losses, NO CullWatch events,
  NO crash. => (a) AnimDrive blind writes into NPC internals = crash cause (never again without
  type verification); (b) the driven body object is NEVER culled/killed by distance or streaming;
  memory-side following is solved. The "haunting" is not an engine kill.
- NEW MYSTERY (visual): after being dragged far, the user sees the body "teleport near me every
  ~10 m, no circling" while memory shows perfect 2.5 m circling. Near the ship (run 1) the body
  visibly circled and jogged. => the visible/scene presence layer desyncs from the transform we
  write; same subsystem as crash 1 (FUN_005ffc60 release walker / crowd parts). Next RE target:
  the crowd/scene presence layer (+0x68 refs; parts manager around FUN_005fxxxx).

## 2026-10-08 - SOLO SESSION VERDICT (final)

- The current build (BodyDrive + CullWatch, AnimDrive OFF) is SOLID: body picked locally follows
  smoothly with animations; across TWO full map traversals (ship -> far side, then across Havana)
  no cull, no losses, no re-pick drift. Occasional lag turned out to be a geometry snag
  (wall/crowd) - recovers to circling by itself. User verdict: "hes perfectly fine".
- Crashing was 100% the blind AnimDrive writes (isolation A/B) - P3 must type-verify any controller
  before writing (or apply actions via the engine's own request path).
- The visual "chunky/teleport" of a body dragged far from its pick area is a real but bounded
  effect, tied to the crowd/parts manager registration (class ctor FUN_005fe730 family, cell-aware
  update FUN_005ff770, release walkers FUN_005ff950/c60/580; crash #1 died in FUN_005ffc60).
  "Re-home the registration as we move" = the smooth-everywhere milestone; desk RE next.
- Engine does clean up abandoned dragged bodies once we stop guarding them (old body freed/reused).
- Rig note for future runs: crashed games zombie their UDP port (10048) - fresh port pair each
  relaunch (27810/20/22 all dead now); clean quits avoid this.

## 2026-10-08 - overlay crash RCA + v0.4 friend-test kit

- Overlay RCA: launch crashes were 0xC00000FD (stack overflow) in BOTH launches, right after the
  overlay's first Present draw. Cause: calling the saved vtable-slot-8 "original" re-entered the
  patched slot -> infinite recursion. Fix in source: hook the Present FUNCTION with a SafetyHook
  mid-hook (callback then original continues) instead of patching the vtable; overlay init is now
  gated on MarkerEnabled (default off). NOT yet live-tested; markers parked for later ("save for
  later" - user).
- v0.4 kit built for the friend test (bf-coop/dist/AC4BF-Coop-v0.4.zip): crash fixes in, AnimDrive
  OFF (the confirmed crash cause), markers OFF, C1 session + ghost on. Ports 27830/27831, friend =
  guest 'PlayerB' vs A's 26.113.208.88. A-side deployed + configured (RemoteIp pending his IP).

## 2026-10-08 - MILESTONE: two-machine session live (v0.4)

- Suhiro's side had the zombie-port issue too (bind udp/27831 failed 10048) - fixed by moving ports:
  A Local 27832 / Remote 27833, B mirrors. His clock runs ~1h behind ours (log timestamps read +1h).
- 10:16:36 - "CoopNet: session established (host), peer 'PlayerB' #2" on A; peer=1 est=1 fresh=1.
  First real two-machine run of the session layer (C1) + the v0.4 build. Ghost body picked near his
  reported position (he was still at the menu - wait for in-world coords).

### 2026-10-08 - two-machine session RECORD (v0.4, first friend test)
- A (host) at 10:16:34: session established (host), peer 'PlayerB' #2 | B (guest): "session
  established (guest), host 'PlayerA' #1, session 0x6D1A66D7" - both sides verified: handshake,
  identity, 20 Hz packet flow, ghost visible BOTH directions.
- Ghost body: glitchy/teleporty + no animations on BOTH sides (the body's own AI fights the
  teleport writes; real human movement exposes what the smooth solo robot masked). B-side also
  churned through 6 body picks in 22 s near the menu-position window.
- Logs archived: bf-coop/logs/2026-10-08-two-machine/{A-playerA.log,B-suhiro.log}.
- Session-port notes: B had the zombie-port issue too (27831) - fixed via 27833/27832. B clock
  ~1h behind A (log timestamps must be offset when comparing).
- NEXT BUILD (P1/P3 fix): drive the NPC's own locomotion (walk destination) instead of teleport
  writes - hunt for the movement code was started (watch-writer-addr + find-walker tools prepped).

## 2026-10-08 (day 3) - THE MOVEMENT APIS FOUND (SetWorldMatrix) + alignment root cause

- Live hardware-watchpoint hunt (find-walker.ps1 + watch-writer-addr.ps1) on a naturally walking
  crowd NPC: ALL 24 caught writes came from EIP 0x0063C2F9 inside FUN_0063c2d0, running on JOB
  WORKER THREADS (many tids) - confirmation that character transforms are updated by parallel AI jobs.
- FUN_0063c2d0 = the character's canonical transform setter: copies a 4x4 matrix into the body
  (this+0x10..0x4F, ECX=body, matrix as a STACK arg) then calls the notify FUN_00512fd0 which
  PROPAGATES the matrix into the render/transform component (FUN_00423260(this)). RVAs:
  setter 0x23C2D0, notify 0x112FD0. Exact call convention verified from the exe prologue bytes
  (55 8B EC; mov edx,[ebp+8]; movaps...). NOTE: it uses MOVAPS -> the matrix buffer passed must be
  16-byte aligned.
- First ApiMove attempt failed (rc=1 every call): our local matrix was not 16-aligned. Fixed with
  alignas(16) (build 10:42:04).
- Also hardened coop_net::configure(): identical endpoint now KEEPS the socket (the close->bind
  race on this machine intermittently fails with 10048 - that was the "zombie port" gremlin all along).
- ApiMove test result (pre-fix): the API path couldn't win as a pure transform set - the AI job
  recomputes transforms; the real walk-drive (set the NPC's own movement state) remains the target.

## 2026-10-08 (day 3) - THE APIMOVE FIX WORKS (smooth + turning + long cross, no crash)

- Root causes found and fixed in sequence: (1) matrix buffer needed alignas(16) (movaps);
  (2) FUN_0063c2d0 ends with `ret 8` - it takes TWO stack args (a dummy second arg must exist).
  After both fixes the engine setter accepts our matrix: readback err 0.04-0.07 m, no failures,
  no crashes. The notify chain (FUN_00512fd0 -> render/transform component) now runs on every move.
- LIVE VERDICT (solo, robot peer): "its smooth, walks in a circle with turning" - and after two
  early body switches the THIRD body survived the full long cross-map run: 245+ m, 1.5+ min, zero
  releases, zero crashes. Best sustained ghost so far. (User: "i did the long cross, no crash,
  all is well.")
- Remaining P1 item: the first two bodies were released by OUR rescan path within ~6-54 s (release
  fields looked intact; cause between engine-free vs our valid_body criterion - instrument the
  failing check next build: log vt/marker/f7c/children/readable/bounds at the loss instant).
- Also shipped: coop_net configure() keeps the socket on identical endpoints (kills the 10048
  rebind race); port-leak note: dead game processes hold their UDP port transiently (minutes), so
  a bind-retry in the plugin is the next robustness item.

## 2026-10-08 (afternoon) - GHOST = DUNCAN WALPOLE, SUSTAINED (pin success)

### Outcome
- Ghost body now (a) renders as Duncan Walpole (robed hooded male) and (b) SURVIVES area
  streaming - walks the whole map with the player, zero vanish/teleport. User confirmed:
  "it stayed duncan and followed no teleports".

### The forge mod pipeline (def redirect with identity patch)
- forge_toc.py (tools/): full TOC parser/validator/editor for scimitar VER 0x1b forges
  (validate against extract, list, redirect, redirect_eof).
- SAFE swap recipe: append the source def as a PRIVATE copy at EOF; repoint the target
  entry OFFSET/SIZE; patch the copy's SELF-IDENTITY hash dwords (2 per def: one in the
  header index, one in the name record - signature: name string, 00 01, u32 hash, then
  06/07 00 00 00). Identity hash = TOC hash32 of the def's own name.
- mod2 (16 entries merged in place) CRASHED: shared data + full name-record copy ->
  loader fault (jump to 0). Root cause class: rewriting entry identity fields + aliasing.
- mod4..mod7 (crew -> assassin, then crew+sailors -> Duncan) via private copies: safe.
- mod8 (Spanish civilians -> Duncan) BUILT BUT SCRAPPED: user veto - world must stay
  normal, only the ghost is Duncan. Keep swaps ship-side only (crew + generic sailors).

### Despawn pin (the sustain fix)
- Body vtable 0x1E4CE90 slot[0] = FUN_0052a950 = scalar deleting dtor (base dtor
  FUN_00526d90 + free). On adoption, give the body a PRIVATE vtable: copy 64 slots from
  the original, replace slot[0] with a 5-byte stub (8B C1 C2 04 00 = mov eax,ecx; ret 4)
  at +0x400; engine "delete" then returns harmlessly -> body survives streaming.
- v1 bug: only copied 6 slots (export said slots=6) -> engine called deeper slots ->
  call through zero -> crash at VA 0 within 1s. Fixed: copy 64 slots (dense .rdata, so
  any deeper call matches original targets). valid_body now accepts either vtable.
- Unpin restores the real vtable whenever we release/drop the body.

### Picker upgrades (same build)
- Full-sweep scan: adopt the GLOBALLY NEAREST valid body (was: first found -> 43 m pops).
- Skip-list (8) for bodies we dropped; warp/divergence detector: if the body sits >7 m
  from our parked target for ~1.5 s (schedule warps/post anchors), drop + blacklist it.
- k_scan_step 4->8 MB.

### Tooling added
- forge_toc.py, make_mod5/6/7/8.py, dump_exc.py (minidump exception -> fault VA),
  probe_exc.py, scan_hoods.py, hood_refs.py, hood_deep.py, def_selfid.py,
  dump-body.ps1, scan-body-ids.ps1, identify-body-def.ps1 (body->def id probe:
  not found within 2 pointer hops - deferred).
- fake_peer_session.ps1: peer now stands 1.6 m beside the player (no circle); ports
  moved per session (zombie rebind issue - see TODO).

### TODO next
- Bind-retry in coop_net configure() (kill the per-restart port hop dance).
- Marker overlay (parked by user).
- Friend kit v0.5 (ship the current .asi + forge + README; Suhiro done v0.4).
- Longer stability runs; watch pin side-effects (leaked bodies accumulate - acceptable).

## 2026-10-08 � COMBAT INTERNALS CRACKED (live)

### Class identity = CRC32(name) � CONFIRMED
- crc32("CSrvNPCHealth") = 0x57EEEEC7 matches the in-binary class-id constant.
- Runtime resolver (no code exec): obj -> vt=U32(obj) -> fn=U32(vt+0x14) -> stub A1<global>C3
  (mov eax,[global]; ret) or B8<imm>C3 -> desc=U32(global) -> id=U32(desc+0x14),
  name string at desc+0xC. Works on any object. (classres.ps1)
- Descriptor layout: +0x0 self/global, +0xC name ptr, +0x10 parent-class id, +0x14 class id,
  +0x18 size (CSrvNPCHealth=0x74), then property/component tables (entries carry crc32 ids
  e.g. CSrvAbstract/CSrvPindownInteraction, fn ptrs 0x014E52F0/0x00A27040, small u16 pairs).

### Service objects + layout (PC)
- Service vec on "AI data" object: base@+0x70 size@+0x76 (alt size@+0x74; vec A base@+0x68 size@+0x6E).
- SPC pattern (PS3-verified, PC equivalents exist): AIDataBuilderHelper +0xC -> GetService<CSrvNPCHealth>,
  result cached at helper+0x58; calls SetLife/MaxLife/IncapLimit internals.
- CSrvNPCHealth flags u32@+0x60: IsIncapacitated bit (rlwinm 0x1c mask), IsKO bit (0x1d) [PS3 pattern].
- PS3 instantiations: SetPropertyComponents_..Life_Fn @0x122d3d0, MaxLife @0x122d460,
  IncapLimit @0x122d418, IsIncapacitated @0x1220554 (flag write), GetService @0x12204f0.

### Live: health instances found
- CSrvNPCHealth vtable on PC = 0x02712F60; scanned: 34 instances (0x30000000..0x56000000).
- Fields: instance+0x20 and +0x28 often = services-container P (owner back-link!);
  +0x4/+0x18 point into HIGH HEAP (0xF0000000+ � include in pointer ranges!).
- Body chain found: body 45858120 +0x114 -> P 4A238E00 -> vec@+0x70[55] elem[14] = CSrvNPCHealth 43358620.
  (Only combat-type NPC linked this way; crowd bodies have no direct link so far.)
- NPC services list (28) resolved by name: CSrvNPCHealth, CSDamage, CSrvNPCDeath, CSDeath,
  CSPushInteraction, CSHumanFightInteractions, CSFightPerception, CSLineOfSight, CSDanger,
  CSrvTargeting, CSrvNavigation, CSrvLoot, CSrvPickpocketBump, ESrvInventoryAccess, ESVisual,
  ESPlayerProximity, ReactionHandler, DeathHandler, PerceptionHandler, AbstractCharacterAILogic, ...

### New tools (bf-coop\tools)
- crc_all.py (166k names), hash_crack.py, classres.ps1 (objlist/vtmap/scanvt/dumpobj/dumpaddr/desc),
  health-find.ps1 (list/diff/chains/fulldump/fulldiff), watch-health.ps1 (live byte-diff watcher),
  ai-chain.ps1, probe-body-services.ps1, ps3_disasm.py (multi-target).

### Next
- Live hit test running (watcher) -> identify true Life offset on PC (0x5A suspected but PC may differ).
- Then: write-test (apply damage via memory), then wire TX/RX in plugin.

### 2026-10-08 (3) � health semantics + full class map
- vtmap re-run with fixed resolver: 15201 vtables -> 3246 resolved (vt_class_map.txt). Key vtables:
  CSrvNPCHealth 0x02712F60, CSrvHealth 0x02727088 (base), CSrvPlayerHealth 0x0269BBF8,
  CSDamage 0x026979F0, BhvGenericNPC 0x026E34D8, AbstractEntityAI 0x01E72108, EntityAIProcess 0x01E65540,
  DamageEvent 0x027214B8, FightDamageResponse(Event), HealthBarComponent 0x0270D790, PlayerTakeDamageCondition,
  ShipHealthData, GcLNavalHealth, ActionHealth, etc.
- CSrvNPCHealth instance (PC) live semantics:
  * +0x5C u16 = LIFE (starts == MAX), +0x5E u16 = MAX (24 basic, 36 tougher),
  * +0x60 u32 flags (byte patterns 04/05/06 live; 0x100 bit seen on some),
  * +0x20/+0x28 = owner services-container P back-link (while NPC active/streamed),
  * +0x4/+0x18 -> high heap 0xF0000000+; +0x2C = shared 0x027B5C90 (global?).
- Live hit tests (two different NPCs): hit -> +0x5C decrements by exactly 1 (36->35 both times; looked
  like chip/blocked hits). Third test not captured (target service likely recycled/one-shot or moved area).
- Services recycle on stream-out (vt changes) -> watcher marks RECYCLED; boxed via v2 watcher.
- Reverse link instance->body: use inst+0x20 P then search bodies for pointer to P (works while live;
  zeroed/recycled instances have +0x20=0).
- New tools: set-health.ps1 (u16 write + readback), link-instance.ps1, watch-health.ps1 v2.

### Next
- Confirm LIFE drain with clean hits (user test running); then WRITE test: reduce LIFE on a linked NPC and
  watch engine reaction; then build TX poll (LIFE deltas on tracked services) + RX write in plugin.

### 2026-10-08 (4) � live hit/kill experiments
- CONFIRMED: sword hit = LIFE -1. Three hits 36->33 on instance 47756720; earlier two hits 36->35->33 on 44E0F2D0.
- CONFIRMED: external write of LIFE works + persists (writes 33->1 and 33->0, readback matched; watcher logged).
- Kill captures still elusive: killed guards either spawned after the watch-base scan (services invisible to us),
  or finishers may bypass LIFE. Need clean start-to-finish capture (watcher v4 running).
- Despawn behavior: services destruct+recycle on stream-out; player death/respawn causes mass recycle waves.
  Death->service fate still unconfirmed.
- Instance coverage: all CSrvNPCHealth live in game heap 0x32-0x4B (+ high-heap pointers 0xF0+).
  Full-space scans (0x00400000-0xFFFF0000) find no extras. GclHealthCN=0; ActionHealth=1 junk hit.
- Session note: old plugin build (12:28) loses player tracking after player death (pos reads 0).
  Restart + redeploy staged 12:49:49 build before further live plugin work.
- Tools added: scan-classes.ps1, body-health-near.ps1, watch-one.ps1; watch-health v2/v3 wide ranges + RECYCLED detection.

### Pending tests
- Clean kill capture (watcher v4): which meter drains, what happens at death (LIFE->0? flags? destruct?).
- LIFE=1 + one hit = one-hit-kill test (blocked on correct target capture).
- Then: RX path (apply damage/kill from plugin), TX path (detect LIFE deltas or DamageEvent hook).

### 2026-10-08 (5) � END-TO-END KILL LOOP PROVEN + death signature confirmed
- CORRECTED TIMELINE: prepared guard (47756720) set to LIFE=1 (~14:29). User's single sword hit at 14:31:14.035
  flipped LIFE 01->FF (u16 0xFFFF) and flags byte +0x63 00->01 (bit 0x01000000). watch-one caught it live.
  => The engine's damage pipeline READ our written LIFE, applied damage, and killed him. One hit on 1 HP = death.
  FULL LOOP: read HP ok, write HP ok, engine honors value ok. (User's "he died" was RIGHT; earlier confusion was
  a read taken before the killing blow.)
- Death signature (3 guards): u16 +0x5C = 0xFFFF; u32 +0x60 |= 0x01000000. Kill flips it directly (no 0 intermediate).
- Writing the signature alone does NOT kill (tested: 46FE4B20 stuck with sentinel, engine no-op) =>
  the trigger lives in the engine's damage pipeline (write + notify); RX must call that path (or send the same message).
- FOUND: CSrvHealth interface vtable 0x027270A0 (class CSrvHealth 0x02727088): [09]=0x017b7df0, [10]=0x011484b0
  (SetLife, writes +0x5C), [11]=0x011484c0 (writes +0x5E), [12]=0x0115acb0 (writes +0x60).
- CSrvNPCHealth interfaces: 0x02712F60, 0x02712F88, 0x02712FB8, 0x02712FD0, 0x0271301C.
- Health methods in corpus: FUN_019fb4c0 = +0x5C setter with clamp/notify; FUN_019fb280/FUN_019fb2a0 =
  message send (FUN_009f6210/6230 at obj+0x70, class id 0x43986147 = AbstractEntityAI) => damage notifications
  to the AI go through this generic messenger; excellent hook/call candidates for the mod.
- So: proof = done for read/write/engine-death; remaining = locate/call the damage-apply notification (RX),
  and detect deltas or hook for TX; then plugin work (deploy staged 12:49:49 build on next restart).

### 2026-10-08 (6) � damage amounts captured (fight, pre-death)
- Pistol shots: -17 each (two shots: 50->33->16 on a 50-HP guard).
- Counter/instant kill: 36 -> death flip (no intermediate) � kill moves go straight to the death signature.
- Chip/light sword hits: -1 (as before).
- => Damage values are explicit ints per attack; the relay can carry the exact delta (or final state).
- Still hunting the damage-apply function: ruled out 017b7df0 ("is set" check), 01a03680 (dtor helper),
  00678550 (trivial wrapper); found factory FUN_01a036b0 creating an object with vt=0x02712FF8 (health-family, 0x20 bytes).
- Next session plan: deploy staged 12:49:49 plugin build on game restart; continue damage-fn identification
  (candidates + runtime trace), then implement TX (LIFE delta watch) + RX (apply/kill) in plugin.

### 2026-10-08 � plugin build deployed
- Old build (12:28:06, sha 8014307E...) backed up as AC.BlackFlag.PatchFix.asi.bak-143845.
- NEW build (12:49:49, sha 0BFDFDA4...) deployed to game plugins (includes review fixes, path replay,
  StateProbe, bind-retry). Game closed at deploy time; next launch runs the new build.

### 2026-10-08 (7) � service destruction pattern (from v3 watcher full log)
- On NPC service destroy/despawn: +0x0A 02->00, +0x20..0x2F pointers cleared, +0x3A 10->FF,
  +0x4C..0x4F pointer rewritten, +0x54..0x57 pointer cleared, +0x62 01->00 (the 0x00010000
  "active/in-world" flag cleared), then vt swapped (RECYCLED).
- The +0x62 byte = the 0x00010000 flag bit (50-HP guards had it set: fl 0x00010007).
- Observed flags layout byte-wise: +0x60 = type bits (4/5/6/7), +0x62 = active bit, +0x63 = dead bit.

### 2026-10-08 � WRAP-UP (session)
- COMBAT CORE SOLVED (proven live): class ids = CRC32(name) + runtime class resolver (3,246 vtables named);
  NPC health = LIFE u16 @+0x5C, MAX @+0x5E, flags @+0x60; external write honored by the engine (set 1 HP -> one hit -> death);
  death signature = HP->65535 + flag bit 0x01000000 (caught on 3 guards); damage amounts: pistol 17, chip 1, counters instant-kill.
- Partner: despawn pin v2 proven (360 m, zero switches); look = Duncan robes via def-swap mod7 (crew+sailors); staged build
  12:49:49 deployed + boots clean; player tracking live in new build.
- Next: DamageProbe + damage relay (P4), StateProbe movement tour (P3), friend kit v0.5.

### 2026-10-08 (8) � CombatSync v1 built + deployed (our own implementation)
- User directive: stop waiting on the engine function hunt � build what we need with the knowledge we have.
- NEW module coop/combat_sync.cpp (+hpp), wired into the PlayerTransform main hook:
  * TX: incremental heap scan (0x2E000000-0x56000000, 8 MB/tick slice) finds live CSrvNPCHealth
    instances (vt 0x02712F60), tracks up to 256; 5 Hz poll logs DAMAGE / DEATH / recycle events.
  * RX primitive: calls the engine's own clamped setter FUN_019fb4c0 (RVA 0x15FB4C0) - thiscall
    (ecx=obj, arg=int); -1 triggers the engine's negative-value notify (the death path).
  * Dev kill test: [Coop] CombatKillTest=true (hot-reloadable) -> one-shot setter(-1) on the first
    tracked instance; for the live "kill one" demo.
- Config: [Coop] CombatSync=true, CombatKillTest=false deployed; ProbeDamage=true still armed.
- Build v3 deployed (sha 3D2BD04A..., 1,216,512 B); previous probe build backed up (.bak-145556).
- Next after the user session: wire TX events into coop_net (NPC_DAMAGE payload = {pos xyz, delta,
  maxHp}) and add RX matching (health obj -> owner services container P via +0x20/+0x28 -> body
  pointer search -> body pos at +0x40; match nearest body by position + maxHp).

### 2026-10-08 (9) � RX KILL PROVEN VISUALLY (the combat loop closes)
- Targeted test: user hit a soldier (CombatSync caught DAMAGE 0x485B2190 36->35). From PowerShell we then wrote
  the full death state to THAT object: LIFE (u16 +0x5C) = 65535 + flags (u32 +0x60) |= 0x01000000.
  => The guard DROPPED DEAD (user-verified visually). RX-kill = two raw writes, no engine function needed.
- Also learned: the engine setter call FUN_019fb4c0(obj,-1) writes life=65535 but does NOT set the death flag
  (setter-only kill = zombie state 65535/no-flag, no visual death). The REAL kill sets value+flag together.
- TX layer (CombatSync) proven live all session: caught 4 DEATH + 2+DAMAGE events with exact values;
  StateProbe captured 159 locomotion samples; no crashes; no errors.
- NEXT: wire TX -> net event -> RX (write value/flag) with NPC position matching; add kill/damage writes
  (value+flag) into the plugin; two-machine relay test.

### 2026-10-08 (10) � crash cascade diagnosis (session end)
- Three consecutive launch crashes: AC4BFSP.exe faulting in nvwgf2um.dll (NVIDIA driver), same offset each time,
  both before AND after the AV-storm fix, and with our activity gated to in-world only (last session: 2 plugin
  log lines total at the menu, zero scanning -> mod exonerated).
- First crash coincided with the (now fixed) body-sweep AV storm; the cascade since = classic degraded GPU
  driver state. Recommended: reboot, then relaunch.
- Deployed and parked: gated relay build 85AC2924 (CombatSync relay TX/RX + kill test off, probe off).
- Session logs preserved under bf-coop/logs/sessions/.
- QUEUED for next session: reboot -> launch -> in-world -> start robot peer -> TX test (hit guard ->
  robot logs NpcCombat) -> RX test (robot kills a guard we stand at) -> labeled parkour tour -> friend kit v0.5.

### 2026-10-08 (11) � PARKOUR CODE SHIPPED (B4 play side v2)
- READ: player locomotion capture extended to blend(+0x8D4) + hang(+0x8D8) + phase(+0x8E0) + 3 flag bits
  (+0x138 b0, +0x8D0 b0, +0x8D0 b8); packing = blend<<24 | phase<<16 | flags<<8 | hang; publishing RE-ENABLED
  (g_act_read_enabled=true; refresh_act_ctl now caches + 10s backoff). PlayerTransform log now prints "bl=".
- WRITE: ghost anim replay v2 in ghost_body.cpp: same packing unpacked onto the crowd controller
  (node+0xE8 -> ctl; +0x8D4/+0x8D8/+0x8E0 + flag bits), CHANGE-GATED (write only when packed state changes),
  readability-checked before stores; config [Coop] AnimDrive gates it (default off).
- Field map from the live signatures (2026-10-08): walk b8=84/b10=83 � jog b10=2a � run b4=48/62 b10=2a �
  climb b8=00 b10=00 + big vz � ascend b8=3f b10=2a � fall vz<-3 � special b4=b6.
- Build 94D95371 deployed (game closed). Next live: reboot -> launch -> robot peer -> AnimDrive=true (hot
  reload) -> verify no crash + visible walk/run on the ghost -> labeled tour to lock the names.

### 2026-10-08 (12) � *** MILESTONE: COMBAT LOOP CLOSED OVER UDP (user-verified) ***
- TX: player hits detected live -> NpcCombat events out over UDP (multiple guards, exact pos + HP deltas; robot log confirms).
- RX: robot-fired kill received ("CoopNet: received event kind=5") -> matched local NPC at d=0.4 m -> raw-write kill applied
  ("CombatSync: RX KILL 0x458C5120 ok=true") -> target state LIFE=65535/FLAGS=01000004 -> guard dropped (user: "yup hes dead").
- Found+fixed: UDP port zombie (dead pid held 27853; SO_REUSEADDR co-bind made delivery ambiguous) -> moved to 27953/27954 pair;
  robot now has bind-retry. Note for later: audit SO_REUSEADDR co-bind behaviour.
- Known gap: instant assassinations (back-hit kills) can clean up their health object faster than the 5 Hz poll -> no TX.
  Fix options: raise poll rate near the player / hook the death-flag write (probe) / relay "object vanished near player" heuristics.
- NEXT: parkour mirror test (AnimDrive + robot echoing the live player anim state).

### 2026-10-08 (13) � AnimDrive crash RCA: wrong write target on crowd bodies
- Session 16:05:41: ghost driven + anim drive active. First write 16:10:48 (ctl=0x45AD9030 read from body+0xE8),
  game crashed 16:10:51 in an unmapped/wild-jump address (WER module "unknown"), zero VEH in our module.
- CONCLUSION: for crowd bodies, body+0xE8 is NOT the player-style controller; writing phase/hang/blend there
  corrupts an unrelated object -> crash. The player-node chain (node+0xE8 -> ctl at +0x8D4..) is player-specific.
- AnimDrive set to false in the ini (game safe). The crowd body's real animation interface must be FOUND, not assumed:
  next RE = probe the crowd body: dump body+0xE8's class (resolver), watch ITS fields while the NPC walks
  (StateProbe-style sampler on the ghost body), find the actual locomotion/anim write surface.
- Everything else unaffected: ghost follow/drive works (err=0.00), combat relay proven, TX/RX fine.

### 2026-10-08 (14) � GhostAnimProbe built (route-2: crowd anim interface hunt, read-only)
- New ini switch [Coop] AnimProbe (default false, hot-reloadable). When on, the ghost tick samples
  the ghost body's +0xE8 object at ~3 Hz:
  * one-shot per object: vtable + 0x00..0x3F head dump + 0x8A0..0x91F dump (covers the fatal
    write area +0x8D4/8D8/8E0 � if pointers live there, that explains the wild-jump crash).
  * continuous: 4-byte diff of +0x000..0x0FF and +0x880..0x97F vs previous sample, with the
    ghost's world position attached � movement-active fields show up as changes.
  * cap 2500 lines; zero writes anywhere.
- Companion logger: refresh_act_ctl now logs the PLAYER controller (ActCtl lines: ctl, vt, head)
  once per object � direct class comparison vs the ghost object (same vt = same class ? the
  crash was field misuse; different vt = wrong-object assumption confirmed).
- Build D9B310E1EF70BDE77BE45A48C35E295C deployed (game closed). Test flow: launch -> load save,
  robot on 27964->27963 drives ghost, set AnimProbe=true (hot reload), walk/run ~30 s, read log.
  Offline: resolve ghost obj vt via bf-coop/logs/ai/vt_class_map.txt; correlate diff offsets.

### 2026-10-08 (15) � FREEZE ROOT CAUSE: act-controller full-memory rescan every 10 s (game-thread stall)
- Log gap analysis of the 16:16-16:21 session: log stops for ~2.5-3.6 s on a strict ~10.0 s cadence
  (16:17:02.8, :12.9, :23.1, :33.0, :42.98, :53.06, ...). PlayerTransform logs at 2 Hz, so the game
  thread itself was stalled ~3 s every ~10 s. This matches the user report "freezes every few seconds".
- Mechanism: refresh_act_ctl() had `rescan = dt > freq * 10` where dt is measured since the LAST SCAN
  and the early-return path never updates the timestamp -> a full-address-space rescan every 10 s by
  design. When no controller is known (menus!) there was NO rate limit at all -> back-to-back scans.
  find_player_ctl walks 0x10000..0x7FFF0000 byte-by-byte; the 90 ms budget only checks per memory
  REGION, so one big heap region scans for seconds.
- This is also the prime suspect for the recurring nvwgf2um.dll+0xcb0e47 crashes (6 today, including
  before any probe existed): multi-second submission stalls at menus (already ~0.1 FPS) or mid-game
  (16:21:53->:57 freeze immediately preceded the crash).
- FIX (build D9B310E1 replaced):
  * refresh_act_ctl: fast path = cached ctl + live node -> never scan. Otherwise rate-limited rescans:
    3 s base, x1..x6 backoff to 20 s on consecutive misses (protects menus/loading).
  * find_player_ctl: two-pass (character heap 0x30000000-0x54000000 first, full range only as fallback).
- User relaunch planned to verify: no more periodic freezes; then re-test menus/appearance.

### 2026-10-08 (16) � NAVIGATION DECODED: CSrvNavigation::NavigateTo (natural walking route)
- The ghost is a crowd NPC (BhvGenericNPC) driven by transform teleports -> slides, no walk anims.
  The engine's own NPC locomotion = per-NPC CSrvNavigation service + NavigationTarget commands.
- Full research banked in logs/ai/NAV_RESEARCH.md. Highlights:
  * PC class id: crc32("CSrvNavigation") = 0x6328D910 (scheme verified vs CSrvNPCHealth).
  * PS3 gold map gives the API: NavigateTo(target, speed, bool, bool, contextID); vtable slot 54
    (NavigateToNavTarget thunk) = same signature; NavigateCancel slot 20; IsTargetReached slot 76.
  * NavigationTarget layout from PS3 accessor disasm: +0x00 type (1=Position), +0x10 Vector4 pos,
    +0x20 reach float, ctor-set defaults at +0x24/+0x50../+0xC0/+0xD8; size ~0xE0.
  * Enums: NavigationSpeed (4=Regular, 6=Fast), NavigationContextID (0=Casual, 1=FOLLOW,
    -1=NOT_DEFINED), MovementType (-1/0/1).
- Node service chain for instance finding: body+0x114 -> P, services base@P+0x70 size@P+0x76.
- Next: find ghost's instance at runtime, verify PC slot 54, build target (copy-from-live preferred),
  test call on a plain villager first, then wire NavDrive (walk-to-peer) with teleport fallback.
- Tools added: tools/dwarf_query.py (targeted DWARF query), logs/dwarf_query_nav.txt (raw dump).
- Also this session: freeze bug fixed+verified ("game feels fine"), probe session proved ghost
  behaviour object = BhvGenericNPC (vs player BhvAssassin) - different class killed the earlier
  anim write (crash), plan pivoted to navigation-based movement.

### 2026-10-08 (17) � NAVIGATION: PC addresses VERIFIED live (NavigateTo callable)
- Found a live CSrvNavigation instance on PC (health-anchor chain: CSrvNPCHealth vt 0x02712F60 ->
  owner +0x20 -> P -> vec@P+0x70 -> resolve -> id 0x6328D910). Instance vt = 0x026F4B70,
  service example 0x4B00D1B0.
- Dumped the full PC vtable + disassembled:
  * PC NavigateTo = 0x01785ED0 (thiscall+stdcall, 5 args, ret 0x14). NavigateToNavTarget = thunk
    @0x01785FF0 (PC slot 51). PC slots shifted -3 vs PS3 in the accessor region (verified via
    GetSpeed/GetDesiredSpeed float getters at slots 20/21 -> [+0x3C0]/[+0x3C4]).
  * PC NavigationTarget::Validate = 0x512160; layout confirmed IDENTICAL to PS3 (type@+0,
    Vector4 pos@+0x10, handle@+0x24) � Validate checks x/y/z finiteness per component.
  * PC NavigateCancel = slot 17 (uses pattern@+0x84, flag @+0x8C, +0x160);
    GetNavigationCommands = slot 18 (lea eax,[ecx+0x160]); pattern NPCNavigation called via
    0x61F180 (ctx=-1) / 0x624410 (ctx given); speed applied via vtable [+0xE0].
- Call plan banked in logs/ai/NAV_RESEARCH.md (target struct build, game-thread-only caution,
  first test = navigate a guard 10 m, then ghost NavDrive). Harness = plugin dev flag + build
  (needs game closed to deploy).
- Crowd-body caveat: 40 scanned crowd bodies had no CSrvNavigation via the +0x114 chain ->
  next probe: sniff BhvGenericNPC (body+0xE8) for its service vector.
- Nothing deployed this round (game running, all read-only). Freeze fix holding; user: "game feels fine".

### 2026-10-08 (18) � NavTest build deployed (first NavigateTo call test)
- New module coop/nav_drive.cpp + [Coop] NavTest (one-shot dev, default false, hot-reloadable).
  Flow when armed: incremental CSrvNPCHealth scan (8 MB/frame) -> +0x20/+0x28 -> P ->
  vec@+0x70/+0x68 -> class-id resolve -> first CSrvNavigation (0x6328D910) -> build NavigationTarget
  {type=1, pos=player, reach=0.5, +0x40 sentinel} in our own 16-aligned scratch buffer ->
  SEH-guarded __thiscall call NavigateTo @RVA 0x1385ED0 (speed=4 Regular, boolA=0, boolB=0, ctx=-1).
  Game-thread only (called from the PlayerTransform hook, inside the guarded callback).
- Logs: "NavTest: health=... P=... nav=..." then "NavigateTo rc=..." (0=accepted, 7=invalid, -1=fault).
- Deploy md5 (see log line). Test: launch -> in world -> NavTest=true -> watch the NPC walking.

### 2026-10-08 (19) � NavTest v2: multi-anchor resolve + diagnostics (deployed)
- First live run: plugin found 1 health anchor and gave up when it didn't resolve ("1 candidates,
  none resolved"). External tool confirmed the chain itself works (found nav=0x3444A5E0 live).
- v2: scan keeps growing a 64-candidate pool (8 MB/frame) while trying every not-yet-tried anchor;
  per-fail diagnostics for the first 6 ("anchor no-nav P20/P28/vec/resolved=N"); readable() guard
  added on the 0xA1 descriptor read. Deployed while game closed; NavTest parked false.

### 2026-10-08 (20) � NavTest v3 + NavWatch deployed (fault forensics + real-target templates)
- v2 result: anchor resolution worked (nav=0x380CA280 found), but the NavigateTo call FAULTED
  (rc=-1; SEH caught it; game survived). No crash, no VEH storm.
- v3 adds:
  * exception capture: logs fault code + faulting address as exe+RVA (nav_exc_filter).
  * Validate precheck: calls PC NavigationTarget::Validate @RVA 0x112160 on our built target
    before NavigateTo (1/0/-1), isolating target-shape problems from deeper path-engine faults.
  * template mode: [Coop] NavWatch (boot-gated read-only MidHooks) captures real engine calls:
    CSrvNavigation::NavigateTo @0x1785ED0 and NPCNavigation::NavigateTo @0x61F180 / @0x624410,
    logging args (target/speed/bools/ctx) + caller RVA; position-type targets are saved as a
    byte-exact template (0xE0) that NavTest copies and patches (type=1/pos/reach) - so every
    unknown field is engine-correct.
- ini parked: NavTest=false, NavWatch=true. Deploy md5 in log line. Flow: relaunch -> play ~30 s
  (captures) -> flip NavTest live -> read rc/validate/fault-addr.

### 2026-10-08 (21) � NavTest: the ENGAGE fix (boolB=1) + type-1 templates
- Fire #1 rc=0 accepted; the NPC (health 0x34245120, nav 0x342430E0, body 0x470CD960) later
  wandered on its own but did NOT move on fire #2 (target=player, 9 m away) for 40 s.
  Command accepted but never engaged.
- NavWatch analysis of the engine's own 60 NavigateTo calls: ALWAYS A=0 B=1
  (speed 4 x48 / 3 x9 / 5 x3; ctx -1 or 0). Our calls used B=0 -> skipped the can-navigate
  precheck + command-activation branch ([vt+0xB8] + call 0x40b560). Fix: call with B=1.
- Template capture now type-1 only (walk targets); previous template was a type-2 capture.
- Verification tooling proven: NPC body found via pointer scan (0x470CD960); nav object +0x10C
  tracks the entity's live position; +0x230/+0x5A0/+0x5C0 hold targets/waypoints; slot20/21
  getters read [+0x3C0]/[+0x3C4] (1.778 constant for idle - not a movement indicator).

### 2026-10-08 (22) � NavTest v4: closest-NPC pick + per-nav templates + command hold
- v3 (B=1, type-1 template) result: rc=0 accepted, still no movement (NPC nav +0x10C static
  50 s; second NPC 45 m away). The engine's own calls come from CSrvNavigation wrappers
  (caller +0x139376C / +0x186F647), not from raw NavigateTo.
- v4 changes: (1) resolve ALL candidate navs (up to 8), pick the one whose nav+0x10C entity
  position is CLOSEST to the player (visible + most likely streamed/simulated); (2) per-nav
  target templates (captures keyed by the calling nav instance; a nav's own call carries its
  spatial frame) with global type-1 fallback; (3) command hold: re-issue every ~1.5 s x5 with
  alternating boolA (0/1), logging rc + entity position each attempt, so movement (or its
  absence) is visible directly in the log.

### 2026-10-08 (23) � NavTest: rc=3 clue + moving-NPC pick (v5)
- v4 result: chosen closest nav (35 m) - attempts alternate: A=0 -> rc=3 (can-navigate precheck
  REJECTS; the service statechart is in a CantNavigate state for idle NPCs), A=1 -> rc=0
  (accepted, precheck skipped). Entity never moved across 6 attempts/8 s.
- Conclusion: the nav service only passes/engages when the entity is already in a
  navigation-capable state (its AI drives that state). Idle/standing NPCs refuse.
- v5: pick the MOVING NPC - sample all resolved navs' entity positions (+0x10C), wait 0.7 s,
  compute speed via displacement, choose the fastest mover (fallback: closest if none > 0.3 m/s),
  then command-hold on him (6 attempts, A alternating). A moving NPC's statechart is in a
  navigable state; our command should hijack its walk.

### 2026-10-08 (24) � PS3 spawn review + CloneLive build (the never-run visibility test)
- PS3 gold review: `CloneObject<Object>(Object*,bool)` = the clone primitive; `Entity::CloneEntity(Entity*&)`
  = CloneObject + u64 flags@+0x50 += (0x2000|0x1000|0x100)<<32 + `Entity::UpdateLODLevel(new,0,f^2)`.
  Callers prove runtime duplication is routine gameplay: BhvTools::InstantiateMusket/Pistol/Dagger/
  SmokeBomb, ProjectileFactory, FX entities, Human::EnableAppleProp, weapon-inventory adds.
  => "entities can only be made at load" was wrong for copies; a full character copy stays unproven.
- PS3 also has the decoy stack in the SP build: CLDecoyed statechart (triggers Start/Stop/Follow,
  state Started_Running_Gameplay_Follow) + DecoyParams; PC anchors: name-table ref 0x0166F410,
  registry records .data 0x029C5154 / 0x02A0AF04.
- NEW BUILD: [Coop] CloneLive (dev one-shot, game thread): scans 0x30000000-0x50000000 for
  character-class objects (vt 0x01E4A128 / 0x01E64680 = player + story NPCs; crowd bodies use the
  base-node vt 0x01E4CE90 and must NOT be cloned through +0xC), picks the one nearest the player,
  calls the proven clone slot (vtable+0xC), logs src vs clone field diff (flags +0x50/54/58/5C,
  +0x60, +0x7C), rechecks the clone at +10 s. User test: walk 5 m and look back - does a second
  body stand where you were? (First time this visual test is actually run.)

### 2026-10-08 (25) � CloneLive v2: multi-candidate attempts (healthy first)
- v1 result: scan found ~20+ class objects (vt 0x1E4A128); picked a stale one (ch=0, f7c=-3.00);
  clone call AV'd - SEH caught (rc=0xC0000005), game ran on. Same trap as the old "stale candidates".
- v2: collect up to 32 candidates (skip (0,0) unplaced proxies); order healthy-first (children>0)
  then by distance; try clone one-by-one, max 12, one attempt per 0.5 s; log every attempt
  (cand/ch/f7c/rc/out); on success log the src/obj field diff and prompt walk-away check (+10 s
  recheck). Also logs the player node chain (+0xC8/+0xE8) as an alternative anchor.
- Deployed md5 (see log line).

### 2026-10-08 (26) � THE CLASS MAP + CloneLive v3 (clone the player's own body node)
- Ground truth established by full-memory class-id resolution (2-pass vt scan + crc):
  * vt 0x1E4CE90 = class "Entity" (0x984415E) - 2788 instances = THE BODIES (crowd + player).
    Slot +0xC = FUN_0052A980 = the NODE CLONE (disasm: self-instantiate via desc 0x275E670,
    child-recursive deep copy FUN_00a27550, job post template 0x27F6A44). This is the mechanism
    the crowd streamer itself uses to create bodies at runtime.
  * vt 0x1E4A128 = "EntityGroup" (0x3F742D26) - the earlier "candidates" were EntityGroups; their
    +0xC = FUN_00503600 (deep copy) - calling it as a clone = the 12 AVs explained.
  * vt 0x1E64680 (clone slot 0x6DEFF0) = class 0x2F4222CA - has NO live instances
    (decoy/mission-only) - the old "1-3 character objects" premise retired.
  * The player's own node (find_player_ctl / g_act_node) IS an Entity instance.
- CloneLive v3: PRIMARY = clone g_act_node (the player's body) via vt+0xC; fallback = scan a
  nearby body (vt 0x01E4CE90, ch>=16, not the ghost) if the primary fails. Walk-away visual test.

### 2026-10-08 (27) � CloneLive v4: the streamer's completion steps (activate + flush)
- v3 result: the node clone SUCCEEDED (rc=0, obj 0x4B9F9B40, vt 0x1E4CE90, ch=20) on a crowd body
  (try#4; player node AV'd - special; 3 earlier bodies AV'd). Clone stable +10 s. But INVISIBLE
  (user looked, nothing) - flag diff: clone f50=0x1FD2227C vs live src 0x5F9A227C, f54 missing
  0x03000071 bits, f5C pointer = 0.
- Found + disassembled the streamer's own completion calls (crowd spawn recipe):
  * FUN_00526590(node) = activate: [+0x50] |= 4|8|0x800000 then call FUN_00522610(node,0,r^2)
    (spatial/LOD registration; handles null f5C with a default radius).
  * FUN_00a2e820() = job flush (process the posted clone job on this thread).
- v4: clone -> MOVE the copy 3 m east of the player -> activate -> job flush -> +10 s recheck.
  (Modify-before-activate so registration sees the new spot.)

### 2026-10-08 (28) � SpawnTest: call the streamer's own spawn (FUN_005FD730)
- Decoded FUN_005FD730 fully: stdcall(hash); template = FUN_005fac60(hash) -> new =
  template->vt[+0xC](template,0,0) -> FUN_00526590 activate -> FUN_00a2e820 flush; returns new.
  So the engine's own NPC creation = clone-a-template + activate + flush (our pipeline, but
  sourced from a template object instead of a live body).
- New build: [Coop] SpawnTest (one-shot): calls FUN_005FD730(0x49BB47AC crowd template captured
  live), logs the returned node + fields, moves it 2.5 m east of the player for the visual test.
  [Coop] SpawnWatch: read-only boot hook on FUN_005FD730 capturing every streamer spawn hash
  (harvest templates for other NPC types, e.g. guards, in other areas).
- CloneLive invisible even after full field sync (flags, f5C/fC0 world-structure refs, scalars).
  Remaining unsynced: +0xAC/+0xB0/+0xD4/+0xE8 per-node world links (likely linked-list slots that
  aliasing would not fix anyway). The streamer-spawn path sidesteps all of it.

### 2026-10-08 (29) � SESSION WRITE-UP: the clone/spawn arc (for the assassin partner)
Goal of the arc: get a SECOND full character (player-class) into the world = the "proper assassin
for co-op" the user wants. Everything below is evidence-backed.

**1. What the night established (in order):**
- The freeze fix (act rescan) shipped + user-verified; drivers stable since.
- Body+0xE8 = the BEHAVIOR object (BhvAssassin player / BhvGenericNPC crowd) - the earlier anim
  write crash fully explained.
- Navigation stack fully decoded + PC-verified (NavigateTo 0x1785ED0, slots, targets, contexts);
  NavTest calls rc=0 accepted but the engine REFUSES to move idle NPCs (precheck rc=3;
  commands for idle entities don't engage). Moving-NPC hijack = untested variant.
- **Class map nailed (full-memory class-id resolution, 2-pass scan):**
  * vt 0x1E4CE90 = class "Entity" (0x0984415E), 2788 instances = ALL BODIES incl. the player's.
  * vt 0x1E4A128 = "EntityGroup" (0x3F742D26) - the old fake "character candidates".
  * vt 0x1E64680 = class 0x2F4222CA (complete sync+async clone slots) - NO live instances.
- **Entity node clone (vt+0xC = FUN_0052A980) live-proven:** crowd-body copies succeed (rc=0,
  real node, stable 10 s+); stale bodies + the PLAYER's node AV (SEH-caught).
- **The copy is INVISIBLE (root cause):** a raw node copy has NO GRAPHICS - the visual is built
  at spawn by the graphic factory (the parked outfit path); field syncs (flags, f5C/fC0 shared
  structure, scalars) do not fix it. Unregistered copies also get FREED by the engine after a
  while (pin tech exists).
- **Streamer spawn FUN_005FD730 decoded:** fast path = template-handle poll; slow path =
  clone-template(vt+0xC) -> activate (FUN_00526590: +0x50 |= 4|8|0x800000 + FUN_00522610
  spatial/LOD) -> flush (FUN_00a2e820). Our calls returned 0 (template-handle validity fails at
  call time) with both the old hash (0x49BB47AC) and the live one (0x479DB35C).
  SpawnWatch (read-only hook) captures per-area template hashes live - HARVESTABLE for other
  NPC types.
- **The decoy stack exists in SP:** CLDecoyed statechart (triggers Start/Stop/Follow; state
  Started_Running_Gameplay_Follow) + DecoyParams; PC name-table ref at 0x0166F410; registry
  records .data 0x029C5154 (CLDecoyed) / 0x02A0AF04 (DecoyParams). Activation path unmapped.

**2. THE QUEUED TEST (built, deployed NOT yet - build sitting in build-x86):**
CloneLive v5 = the ASYNC clone (`Entity vt+0x8` = serialize + engine-side deserialize = the
notes' documented "complete renderable character" path; NEVER yet run on a free-roam save).
v5: async-clone the player node (or a crowd body with a +3 m source-offset spot trick) -> find
the copy -> move to player -> activate -> flush -> look. procedure: close game -> copy the
fresh build -> in-world -> CloneLive=true -> walk/look.

**3. Build/deploy state:** deployed asi = 208344A7 (SpawnTest/hash build). Newest built (NOT
deployed): CloneLive v5 async build (build-x86). Ini: SpawnTest=false, SpawnWatch=true,
SpawnHash=47CD5ECC (update per area from SpawnWatch), NavWatch=true, NavTest=false,
CloneLive=false, CombatSync=true, AnimDrive/AnimProbe=false.

**4. The wall(s), honestly:**
- VISIBLE second character: (a) async clone (untested, the best shot), (b) the graphic
  factory/rebuild path (parked outfit project - heavy), (c) the decoy activation (unmapped).
- WALKING on command: AI state gate (commands don't engage idle NPCs; moving-NPC hijack untested).
- Keep-alive: pin tech exists (ghost).

**5. Options ladder (next sessions):**
1. Run the async clone test (minutes; highest-value single test).
2. Harvest SpawnWatch hashes in interesting areas (hideout = assassin NPCs!) and try
   FUN_005FD730 there (the spawn path may work when the template is actually loaded).
3. The decoy deep-dive (PC CLDecoyed activation via the 0x0166F410 anchor + registry records).
4. Friend kit v0.5 for the two-machine test with Suhiro (the practical co-op deliverable:
   follower + combat + freeze-fixed build).
5. Cleanups: SO_REUSEADDR audit, port hygiene, DamageProbe bisect.

### 2026-10-08 (30) � 30-MINUTE AUTONOMOUS DIG: decoy closed (SP), spawn-call bug root-caused + fixed build
Clock: window 17:59-18:29. Deliverables, evidence-backed:

**1. THE DECOY DOOR IS CLOSED FOR SP (definitive, two ways):**
- PS3 SP map: 324 CLDecoy* symbols = ONLY the CLDecoyed statechart + ICLDecoyed internals. ZERO `CLDecoyNpc*`, zero `SpawnDecoy`, zero `AbilityDecoy`.
- MP exe HAS the full family: `AbilityDecoy`, `CLDecoy`, `CLDecoyNpcRun`, `CLDecoyNpcAttack`, net messages
  (OnSendDecoyToEntity, C2S/S2C), `DecoyLure`, HUD icons. The decoy-NPC spawn machinery is MP-linked-out
  of the SP binary. The SP CLDecoyed = a vestigial shell (its driver classes do not exist).
- Decoded anyway (for the record): CLDecoyed ctor @0x1686B30 -> vtable 0x26E0800; class id =
  crc32("CLDecoyed") = 0x23FBB0F9 (registry record @0x25C5154: name ptr + crc32 at +0x28);
  DecoyParams ctor @0x18070E0, id 0x16AD245D, size 0x6C. Statechart/trigger registration at 0x167F580.

**2. THE SPAWN-CALL BUG, ROOT-CAUSED AND FIXED (the reason every SpawnTest returned 0):**
- FUN_005FD730 is **__thiscall**: ECX = the spawn MANAGER, stack arg = a POINTER to a template key struct
  (the "hash" values we logged, e.g. 0x479DB35C, are HEAP POINTERS to key structs, not hashes!).
- Our helper passed garbage ECX (stdcall) + later a stale key -> FUN_005fac60 walked a garbage manager ->
  not-found -> 0. Every spawn attempt so far was structurally wrong (both this session and earlier eras' "hash" interpretation).
- FUN_005fac60 (slot getter) walks the manager: array at [mgr+0x94], count u16 at [mgr+0x9a], entries = 8 bytes
  {e0=object/?, e4=key-ish}; compares via FUN_00656110 against key+0x1C. Not-found returns mgr+0x80 (empty slot).
- NEW BUILD (compiled, ready to deploy): SpawnWatch now captures the manager (ECX) AND the key pointer of the
  game's own live spawn calls; SpawnTest v2 replays FUN_005FD730(mgr, key) with those exact live args via
  __thiscall. The failures should turn into the game's own behavior with the game's own args.

**3. Battery results (deployed build):** 6x SpawnTest ret=0 (explained by #2); NavTest 6 re-arms all "no mover"
  (the health-anchor candidate chain resolves GUARDS - stationary! movers need a different candidate source).

**4. Refined clone-renderer insight:** the game's visible runtime spawns (pistols/muskets etc., BhvTools
  Instantiate*) clone REGISTERED TEMPLATE entities from manager slots - not live objects. The crowd streamer
  uses the same shape (template -> vt+0xC clone -> FUN_00526590 activate -> FUN_00a2e820 flush). Our invisible
  clones cloned LIVE bodies. The corrected next target: clone a TEMPLATE object (the manager+key capture in
  build #2 finds the live manager by construction).

**NEXT WINDOW (one deploy away):** close game -> deploy latest build -> walk (SpawnWatch captures live
mgr+key) -> SpawnTest=true -> replay. If ret != 0: the node is MOVED to the player + logged (the test does
it automatically). This is now a structurally correct call.

**CORRECTION to #1:** the SP build DOES have an ability system (3799 "Ability*" symbols, e.g. AbilitySetClip)
- but the DECOY family specifically is absent: 0x `AbilityDecoy` and 0x `DecoyNpc*` symbols in the PS3 SP
map (the MP exe has both). The closure stands: SP cannot spawn the decoy NPC; it has only CLDecoyed+DecoyParams.

### 2026-10-08 (31) � WINDOW BUILD (ready, not deployed): spawn replay + nav direct scan
Single build contains BOTH fixes (compiled 18:07, `build-x86`):
1. **SpawnTest v2 (structurally correct)**: SpawnWatch captures the manager (ECX) + key pointer of the
   game's OWN live FUN_005FD730 calls; SpawnTest replays FUN_005FD730(mgr, key) as __thiscall with the
   captured args. Every previous attempt passed garbage ECX / stale keys - all spawn ret=0s explained.
2. **NavTest direct scan**: the candidate scan now matches the CSrvNavigation vtable (0x26F4B70) directly
   - finds ALL navigating NPCs including walking civilians (the health-anchor chain only found guards,
   which stand still, so the moving-NPC hijack test never actually sampled a mover). Collects up to
   4096 nav instances, keeps 16 within 60 m, samples twice, picks the fastest; fires NavigateTo(player)
   with the existing command-hold.
TEST RECIPE (next window, ~2 min): close game -> copy the asi -> launch -> in-world ->
  a) wait ~30 s (SpawnWatch needs live calls; it logs "mgr=0x.. key=0x..") ->
  b) SpawnTest=true  -> read the log: "REPLAY mgr=.. key=.. ret=.." (ret!=0 = the engine spawned;
     the node is auto-moved 2.5 m east + the user watches)
  c) NavTest=true    -> read "chosen MOVING nav=.. spd=.."; if a mover is found the NPC may walk over.

### 2026-10-08 (32) � live mover-check (read-only, pre-deploy validation)
- Direct scan for CSrvNavigation instances (vt 0x26F4B70) in 0x2E0-0x560: only 44 instances, 37 within 60 m
  of the player (docks area) - and ZERO movers across two samples. NPCNavigation (vt 0x268AFA8) = also 44
  (likely the same NPCs' pattern objects). CONCLUSION: the current spot is a quiet area (few NPCs, all
  stationary) - the walk-hijack test needs the player in a busy street; otherwise "no mover" is expected.
  The deployed build's nav log (d= distances) will show this per session.
- Window summary 17:59-18:08: decoy closed (SP lacks the decoy-NPC family; MP-only), spawn-call root cause
  + replay build, nav direct-scan build, TEST-CHECKLIST.txt written. Both new experiments are one deploy away.

### 2026-10-08 (33) � window continued (18:08-18:13): manager family, factory decode, deploy package
- Strong manager family located (high-heap 0xFE5D7xxx-0xFE5DAxxx, counts 159-201, entries {e0=obj, e4=key
  struct ptr}): the top manager's class = vt 0x1E5F808 (id 0x406089A4); key structs carry {vt, flags
  0x10000000, id fields, +0x1C ptr}. Not conclusively the crowd catalog - the ECX-capture build resolves
  the real manager by construction (game's own ECX).
- **GRAPHIC FACTORY DECODED** (the clone-visibility wall's door): FUN_0085F9C0(definition) = create the
  graphic instance for a definition object: kinds via FUN_00a1d0d0 (definition type hash switch:
  0x66f41a81/0x212dd44a/0x536e963b/0x6e877b3a/0x7d324092 use [def+0x10]; 0x59c7cc7f uses [def+0x20]),
  then FUN_00927CB0 -> kind 0-7 -> per-kind 0x20-byte alloc + ctor (FUN_0085BF50/0x85A3B0/...).
  Wrapper FUN_00900260(def). => A cloned node gets graphics by running the factory per part-definition
  and attaching. Signature + routing documented for the next phase.
- Deploy package: tools\deploy-next-window.ps1 (backup + deploy + ini preset for the test window).

### 2026-10-08 (34) � factory attach chain (window close-out)
- Graphic creation dispatch: a kind-switch dispatcher at 0x91F6xx routes type cases to create-variants
  FUN_0084A040/050/060/080/0F0 (each takes the definition; allocator/device global = [0x4DD0210];
  result stored into the caller's output slot, e.g. [esi] = the part's graphic field). FUN_0084A050's
  caller case: ecx=def -> call -> store. The chain: dispatcher -> FUN_0084A0x0(def) -> FUN_00900260(def)
  -> FUN_0085F9C0(def) -> kind-routed 0x20-byte ctor. No direct callers of the wrapper (callback-table
  dispatched, table refs only via relocations). ATTACH RECIPE (for the parked graphic/outfit phase):
  per part definition: graphic = variantFactory(def); store into the part's graphic slot (the dispatcher
  pattern shows the slot is the caller's output dword). Concrete next step for making clones visible.

### 2026-10-08 (35) � WINDOW HEADLINE: the deep copy = node clone + STATE BLOCK (why clones were invisible)
- Decoded FUN_00503600 end-to-end: FUN_00503600(this=SOURCE, arg1, arg2) = allocate via desc 0x275AFD0
  + FUN_0052A980(SOURCE, new, arg2) [the node clone we called before] + THE STATE COPY of
  0x100..0x148 (four xmmwords + byte) + child-container re-init +0x140 (FUN_00616640/FUN_004F9870).
- => Our clone calls (vt+0xC = FUN_0052A980 node-only) skipped the state block AND the container
  re-init. The crowd streamer clones templates through the deep-copy family ("template->vt+0xC =
  node-copy FUN_00503600-family") and those RENDER. This is the best-evidenced fix for clone
  visibility so far.
- Build 7EDF5037 (18:13, deployed=NO): contains THREE corrected experiments:
  A) CloneLive v6: deep_copy(source,0,0) PRIMARY (+ move/activate/flush; async fallback).
  B) SpawnTest v2: replay the game's own live (manager=ECX, key) args via __thiscall.
  C) NavTest v2: direct CSrvNavigation-vtable scan (walking civilians, not guards only).
- Deploy: tools\deploy-next-window.ps1 (game closed); TEST-CHECKLIST.txt updated (A/B/C order).
- Window accounting: 17:59-18:14 spent on: decoy closure, spawn-call root-cause+fix, nav-scan fix,
  deep-copy decode+fix, graphics-factory chain decode. Everything deploy-ready; the remaining
  window time is deploy-only (requires the game closed by the user).

### 2026-10-08 (36) � v7 build: the engine's OWN sync clone as primary (3B713A6D)
- FUN_006deff0 disasm (its call site to the deep copy): FUN_00503600(source, NEW, arg2) where NEW was
  allocated by FUN_006deff0 itself via desc [0x2799098]. FUN_00503600 with null first arg allocates
  internally via desc [0x275AFD0] - valid, but the engine's own sequence uses the [0x2799098] desc.
- => v7 CloneLive: SYNCCLONE first (FUN_006deff0(source,0,0) = the engine's complete clone entry incl.
  setup post), then DEEPCOPY (FUN_00503600(source,0,0)), then the async path. All share place_clone
  (move 2.5 m east + activate FUN_00526590 + flush FUN_00a2e820 + field logs + 10 s recheck).
- FINAL BUILD: 3B713A6D9B34E3257495FBD88DF6A3FD (18:20). Contains, all SEH-guarded, game-thread:
  A) CloneLive v7 (sync clone -> deep copy -> async), B) SpawnTest v2 (live mgr+key replay),
  C) NavTest v2 (direct nav scan). Deploy: tools\deploy-next-window.ps1.

### 2026-10-08 (37) - Skyrim Together repo study + LIVE tests A/B/C on build 3B713A6D
- Studied github.com/tiltedphoques/TiltedEvolution (Skyrim Together Reborn). Full findings:
  bf-coop\logs\ai\SKYRIM-TOGETHER-LESSONS.md. Key: they spawn the partner via the ENGINE'S OWN spawn
  function (Actor::Create + ModManager::Spawn/SpawnNewREFR) and NEVER memory-copy a live entity; gate all
  setup on materialization (WaitingFor3D: poll GetNiNode); drive per-tick (ForcePosition/SetRotation +
  interpolation); transport animation as per-class animation-graph VARIABLES (descriptor tables + word-index
  guard; wrong-class writes = the exact Havok crash family as our node+0xE8 anim crash).
- LIVE tests (user in-game, busy street, 103 streamer spawn captures this session; build 3B713A6D):
  B) SpawnTest v2 replay (mgr=0x43359930 key=0x3937DAAC captured 18:59:00) -> call entered the real
     function (SpawnWatch logged our own call) -> ret=0x0. Stale-key hypothesis: capture the key's CONTENTS
     (and all args + caller RVA), not just the pointer.
  A) CloneLive v7: player's own body = all 3 rungs fail (SEH). 32 candidates scanned; try#0-8: SYNCCLONE
     rc=1, DEEPCOPY rc=1, ASYNC AV (0xC0000005); try#9 SYNCCLONE rc=0 -> object 0x45220110, vt=0x1E64680
     (WorldEntityGroup), placed + persisted (still alive 105 s later). Live memory dump vs source body vs
     player: node fields copied (position, marker 0x04DD5F8C, self-link +098, own children array), but
     graphic/scene link slots +0xAC/+0xB0/+0xD4 = 0x0, controller +0xE8 = 0x0, +0x50 = static default
     definition -> INVISIBLE SHELL, not a body. VERDICT (live-proven): no memory-copy route yields a rendered
     Entity; renderable bodies must come from the engine's spawn/streamer pipeline (as ST does).
  C) NavTest v2: scan/pick/command path work; the "MOVING" filter misreads a garbage speed field (picked
     navs at 211 m/s); attempts alternate rc=3 (idle state gate) -> rc=0 (accept, no movement) on a
     stationary instance. Needs position-delta mover detection.
- Config restored after tests: CloneLive/SpawnTest/NavTest=false; SpawnWatch/NavWatch=true.
- Next build list: SpawnTest v3 (key content snapshot), materialization logging (graphic slots), nav fix.

### 2026-10-08 (38) - SpawnTest v3: capture the spawn TEMPLATE (build 2E92C596)
- Root-caused the ret=0: FUN_005FD730's manager is a TRANSIENT pass object - its slot table
  (mgr+0x94 / u16 count at mgr+0x9a) and the mode global [0x2AC1E68] die with the spawn pass
  (live-read 19:07: all captured managers +0x94=0, count=0; mode ptr NULL). A stale replay can
  never work -> the replay must clone the captured TEMPLATE directly.
- Fully decoded the engine spawn recipe: FUN_005fac60(mgr,key) = walk the mgr's pass table, find
  the slot whose value at +4 is IN the key's id-array (ptr at key+0x1C, u16 count at key+0x22;
  live sample had 17 ids), slot[0]=P (validity P[+8] must be negative), P[0]=Q=the TEMPLATE
  object; the spawn = [[Q]+0xC](Q,0,0) + activate FUN_00526590 + flush FUN_00a2e820. So the
  engine's own spawn IS an object clone - but of the TEMPLATE class, not of a live body.
- v3 (build 2E92C596, 19:09:07): SpawnWatch v3 captures per live call: key id-array, first slot
  match (FUN_00656110 replication), P validity, Q / Q-vt / clone-fn, caller RVA; prefers an
  Entity-class (vt 0x1E4CE90) template. SpawnTest v3: stale-replay + lookup diagnostics, then
  CLONE the captured template directly (engine slow path) + activate + flush + move 2.5 m east
  + materialization watch at 1s/4s/10s with the graphics/controller slots (fAC/fB0/fD4/fE8).
- Deploy pending (game running at build time); TEST-CHECKLIST.txt updated with the new procedure.

### 2026-10-08 (39) - SpawnWatch capture bug root-caused + v3.1 (build BD947E10)
- The v3 capture never matched because it walked ONLY the mgr+0x94 table - but the streamer
  managers' tables are EMPTY (n=0, live-read). FUN_005fac60's FALLBACK path (slot at mgr+0x80)
  is what these calls actually use. Live-read of 24 burst managers: every fallback record holds
  P[+8]=0x80000001 (valid), Q = a PERSISTENT Entity-class template (vt 0x1E4CE90), cloneFn =
  0x0052A980 (the node clone), static archetype def at Q+0x50 (two distinct defs seen:
  0x1ED82078 / 0x1CD82078), position in +0x40.., P<->Q backlink (P[0]=Q, Q[+0xC8]=P).
  Templates read fine MINUTES after the pass -> they persist; the capture can fire any time.
- Note: the templates themselves have fAC/fB0/fD4 = 0 (no graphic links) - same as our invisible
  clone. So graphics are attached AFTER the spawn call (the caller's follow-up). The caller RVA
  (now logged) identifies that code = the next lever.
- v3.1 (BD947E1024C1C3D1ECDBED26BC736175, 19:14): capture mirrors FUN_005fac60 exactly (table
  match OR fallback), logs the first 12 calls in full (caller RVA, tab/n, fb, q/vt/fn/matches),
  keeps the best body-class capture (g_spawn_v3) + last-call record (g_spawn_v3_last). Test
  unchanged (clone template -> activate -> flush -> move -> 1s/4s/10s materialization watch).
- Deploy pending (game running); checklist updated.

### 2026-10-08 (40) - LIVE SpawnTest v3 run: capture works; clone faulted; v3.2 adds fault pinpoint
- v3.1 capture (build BD947E10) WORKED live: 18 "call#" lines, every call fb=1 found=1, arr_cnt=17,
  tab=0x0 n=0 (fallback path), pv=0x80000001, caller=+0x202CE0 (the streaming caller), templates =
  Entity (vt 0x1E4CE90 fn 0x52A980) AND EntityGroup (vt 0x1E4A128 fn 0x503600) - both engine paths.
- SpawnTest v3 fired (19:17:47): TEMPLATE q=0x46AA53D0 (Entity, ch=1, f50=0x1ED82078 static
  archetype, kids=1 x class 0x1E4C9F8); stale replay ret=0; lookup rc=0 slot=mgr+0x80 (fallback
  confirmed); CLONE rc=1 = SEH fault in FUN_0052A980 on the template (worked on live bodies v4/v5).
- Live diagnostics: all descs valid ([0x275E670]=0x2760EF0, [0x275AFD0]=0x275CD28,
  [0x2799098]=0x279A3E8); jobenq 0x639360 NOT patched (normal code); mode ptr null post-pass;
  template record healthy (P valid, Q[+0xC8]=P, children ok).
- v3.2 (578CA55DC9DB418C4BB8A6BE72B06D82, 19:19): template_clone_helper now records the SEH code
  + faulting instruction address (logged as "CLONE rc=.. seh=0x.. at+0x.."); capture + TEMPLATE
  logs now include the mode byte (*[0x2AC1E68] at call time) = fast/lookup vs slow/clone per call.
  Deploy on next close; re-run: walk for a capture, SpawnTest=true, read the fault address.

### 2026-10-08 (41) - BREAKTHROUGH: the in-hook spawn WORKS (v4, build C304FAFE)
- Root-caused the cold-call fault (seh=0xC0000005 at+0xD1539): an 8-byte-entry container GROWTH
  copy inside the job/queue family - a context problem, not the object. The engine only ever runs
  the clone path ON THE STREAMING THREAD inside a pass; cold calls from the camera/main thread
  fault there.
- v4 = run the spawn INSIDE the live spawn hook (streaming thread, in-pass): re-invoke
  FUN_005FD730(mgr,key) with the call's own args, capture the return, move 2.5 m east, watch.
- LIVE RESULT (19:26:47, Havana load): triggered on call#1 (mgr=0x39DA11A0 key=0x39DF0C9C,
  caller=+0x2060F3, EntityGroup template vt 0x1E4A128 fn 0x503600 deep copy) ->
  "LIVESPAWN rc=0 obj=0x489C4070 seh=0x0" = THE ENGINE'S OWN CALL SUCCEEDED.
  obj: vt=0x1E4A128 (EntityGroup) ch=19 f50=0x1CD0207C.
  Materialization: @1s fD4=0xFC7A6E94 (stream link) + fE8=0x471FD3E0 (controller) appeared,
  f50 -> 0x1CD8207C (def swap); stable @4s/@10s. NOTE: cold clones never got these links.
  Children = a composite (controller, 0x26xxxx behavior-class objs, stream handles) - an
  engine-built live entity group.
- Miss: it was placed at (2.5,0) - fired during the load before g_last_pos was valid. The
  test is RE-ARMED for the next burst (fires 2.5 m east of the player's live position).
- Also confirmed: mode=0 on every streaming call (the load pass IS the clone path); templates
  come in both Entity (fn 0x52A980) and EntityGroup (fn 0x503600) flavours; caller +0x202CE0
  (streaming loop) and +0x2060F3 (a second spawner).

### 2026-10-08 (42) - *** BREAKTHROUGH: THE EDWARD CLONE (v6) ***
- v6 "Edward substitution": point the streamer record (mgr+0x80 -> P) at the LIVE PLAYER BODY for
  one invocation, run the engine's own slow path ourselves (SEH-guarded), restore the record
  immediately (the engine's own call then sees the original Q again). Our call's return = the
  engine-made clone of a FULL CHARACTER.
- LIVE (19:38:38, build 40571E0B): SUBSTITUTE P=0x46388768 Q=0x443AB790 -> Edward 0x3B47F320 (ch=32)
  -> EDWARD CLONE rc=0 obj=0x48A3D200 seh=0x0 (restore=0) -> ch=32 f7c=-0.50.
  Materialization: @1s fD4=0xFC8B166C (stream link) + fE8=0x494EEE00 (controller) + f50=0x5FDA027C
  (= Edward's own definition) appeared; stable @4s/@10s. Deferred placement -> (106.3,-73.8) =
  2.5 m east of the player.
- CONTROLLER CHECK: clone fE8 vt = 0x026FA898 = *** BhvAssassin *** - the assassin behavior class!
  (crowd NPCs = BhvGenericNPC 0x26E34D8). Clone alive + stationary with the assassin controller.
- VISUAL = the open question (fAC/fB0 still 0 at 10s; the user was asked to look east).
- Repeatable: flip SpawnTest off/on + fast travel (fires during the destination load; defers
  placement until the position is known).
- Builds tonight: v3 BD947E10 -> v3.2 578CA55D -> v4 C304FAFE (in-hook spawn works) -> v5 851509FD
  (body-only + deferred placement) -> v6 40571E0B (Edward substitution). ALL verified live.

### 2026-10-08 (43) - late arc: v8/v9, the render wall, and the spawn-trace results
- v8 (C17AD011): record child counts captured: records run ch=1..19 (Entity + EntityGroup),
  callers +0x202CE0 (streaming loop) and +0x2060F3 (second spawner); ch>=16 records exist
  (EntityGroup ch=19 via +0x2060F3). Trigger fires -> spawn_live_do -> clone gets fD4/fE8 only.
- THE RENDER WALL (evidence): runtime-created objects (records, groups, EDWARD clones, record
  clones) NEVER receive the graphics slots fAC/fB0; every VISIBLE body has them (fAC~0xFC7x/0xFCBF,
  fB0~0x38A2) + the shared world link (+0x5C/+0xC0=0x38B10260) + +0xD0=1. Pointer-wiring ALL of
  those onto clones -> still invisible (user-verified). Citizens CHURN (a "citizen" source was
  recycled within minutes - do not wire from stale reads).
- The engine's own load spawn (trace at 19:59:03): spawnApi arg=0x362A1D8C (one key) x102 calls
  from BOTH callers; created ch=1..19 objects (Entity/EntityGroup, f7c varying) = the RECORD
  population - NOT the citizens. Records do not grow (checked 1 min later). Deep copies
  (FUN_00503600) run from both callers at load (sources = EntityGroup records).
- v9 (6D3D4000): clone_test_thread repurposed = pure trace arming (2s -> g_spawn_capture); old
  census/route-B/keyed experiments removed. Probes (node-ctor 0x52A4A0, alloc 0xA38120 filtered to
  4 ctors, copy 0x503600, spawnapi 0x5FD730, spawnret 0x602CE0) log callers during the window.
  Deployed + ran: the trace showed the record+deep-copy flows but NOT the citizen creation
  (citizen ctor is elsewhere / outside the window).
- CONCLUSION for the next session: the rendered characters come from an untraced creation path.
  Next: broaden the alloc probe to log ALL descriptor allocations + callers during a load ONCE,
  grep for the Entity-class (desc from [0x275E670]) creations whose results have fAC/fB0 set;
  that caller chain = the citizen builder -> replicate for the partner. Alternative (works today):
  hijack a rendered body (ghost route).

### 2026-10-08 (44) - the decisive render-provenance result
- The engine's own load-created records MATURE: eng4..eng10 (created 19:59:03 via the spawn API)
  showed fAC=0xFCA4A2xx + fB0=0x390C/0x43BA + the world link +0x5C=0x38FFE070 by 20:01 - i.e.
  stream-owned objects DO get graphics slots, minutes after creation.
- BUT: moving eng4 (a ship-rigging object, originally at z=23.8) -> the engine SNAPPED IT BACK
  (114.4,-62.5,23.8) within seconds. Stream-owned NON-character objects = transform-managed (moves
  do not stick).
- Contrast: streamed CHARACTER bodies DO accept transform writes (that is why the ghost drive
  works - user-verified earlier). So: visible+drivable = hijack a character body; runtime-created
  characters = never drawn (all pointer-wiring exhausted + user-verified invisible).
- => The remaining untraced piece = the creation path that yields STREAM-OWNED CHARACTER bodies
  (the citizens). The trace harness is deployed (v9, CloneTest arms it); next: broaden the alloc
  probe to log ALL descriptor allocations + callers during one load, find the Entity/character
  creations whose results carry fAC/fB0, and replicate that call chain.

### 2026-10-08 (45) - NIGHT FINALE: the 1772-key entity creation + the registry signature fix
- v12 trace (build 09A39098): the world load = **1772 Entity mass-creates** (classId 0x984415E)
  with REAL 32-bit world-hash keys + block indices (1,2,6,7,8,9,A,B,C,D,E) - e.g.
  (0xA534890C,0), (0x532E4E53,A), (0x81540F2D,7), (0x14E01872,8), (0x4C8...)... => **the game's own
  character/world-entity creation recipe = MassCreate(Entity, worldHash, block)**.
- FUN_00a1f160 (find-by-key) and FUN_00a201a0 (find-or-create) decoded from disasm: **THISCALL with
  the REGISTRY in ECX** (mass-create = 4 stack args + ret 0x10; find = 2 stack args + ret 8; the
  world's callers pass the registry in ECX - captured live in the masscreate probe as r.ecx).
  => ALL earlier "spawn by key" attempts (the old EntitySpawn v3 etc.) passed NO ECX = wrong
  registry = the documented "empty/unregistered body" failures. FIXED in v14 (registry_find2 /
  spawn_keyed2 helpers + g_last_registry captured from the probe).
- v14 (0D0D560324262338F0B8D63A170A7688) DEPLOYED: the clone_test_thread experiment now:
  1) fetches the first body-like entity (f7c=-0.5, ch>=16) among the captured keys via the
     CORRECT registry call -> moves it to player+2.5m east (~3 s of writes) -> "LOOK 2.5 m EAST";
  2) creates+fetches (key+1) as the neighbor-spawn probe -> moves to player-2.5m west -> "LOOK".
- LAUNCHER HICCUP at the end: after ~20 kill/deploy/relaunch cycles tonight, Ubisoft Connect got
  stuck (windowless hung starts; a killed session blocks the next immediate launch). NOT code.
  Next clean launch (wait a few minutes for Uplay, or launch from the user side) runs the v14 test.
- Builds tonight: BD947E10 -> 578CA55D -> C304FAFE -> 851509FD -> 40571E0B -> C17AD011 -> 6D3D4000
  -> A8AD43EC -> 09A39098 -> DF0A4A86 (entctor hook reverted: hung init once, later verified safe)
  -> F26C04CE -> 0D0D5603 (v14, deployed).

### 2026-10-08 (46) - v15/v16/v16.1: spawn test closed; Edward graphics attempt result
- v15: the corrected create (fake key 0x7A3C9E01,7) DOES create a registered entity (0x48B142C0,
  vt 0x1E4CE90) - but it is an EMPTY SHELL: ch=0, f50=0x1ED02078 (default), all links 0; unchanged
  at +30 s. The old register recipe (FUN_0051d290) faults (rc=1). => entity CONTENT comes from the
  world data by key; fake keys never fill = cannot render. Pure spawn = closed with evidence.
- 1772 Entity mass-creates at load = the world's own data-backed creation (blocks 1..F keys).
  Guards = these records materialized + filled by the stream; new guards appear when new blocks
  stream (new keys -> new shells -> filled). Adoption loophole (pre-create at an unloaded block's
  key, reload) = untested idea.
- v16/v16.1: Edward clone (v6 recipe) re-ran clean (obj ch=32, f50 0x5FDA027C after the fill,
  +BhvAssassin +stream link). Graphics attach attempt (decoded recipe: variantFactory(def) ->
  store into +0xAC/+0xB0): v16 ran pre-fill with the static default def (0x1FD2027C) -> 0;
  v16.1 deferred to +4 s (correct def 0x5FDA027C) -> STILL 0. The factory (FUN_0084A050,
  thiscall(def)) returns nothing - the real invocation shape (callback-table dispatched) is still
  unknown. fAC/fB0 stay 0. => The Edward clone exists as data but remains unrenderable for now.
- Builds: v15 E1B8BEA0 -> v16 C8194DD6 -> v16.1 25EBF660 (deployed). MODLOG/RE-NOTES current.

### 2026-10-08 (47) - THE GRAPHICS BINDER: cracked to its real layer
- The variant "factories" are NO-ARG THUNKS (mov ecx,0x27E1CF0; jmp wrapper). The dispatcher
  case (0x91F68A) shows the REAL call shape: **push def (cdecl, on the stack); call thunk;
  store eax into the slot**. My earlier calls passed the def in ECX and nothing on the stack ->
  the function read stack garbage -> always 0. THAT was the bug.
- With the corrected shape (v16.2/16.3, call sites 0x91F694 & 0x92E38A as reference):
  * REAL graphics created: part defs -> non-zero results (first success!)
  * v16.5 run: body def -> graphic 0x576AE490 (vt 0x259504C) bound into fAC/fB0; part[53] ->
    0x37DB14E0. Slots held at @10s.
  * STILL INVISIBLE: the factory product = a DEFINITION-level graphic object; real bodies carry
    per-INSTANCE scene/stream objects in fAC (stream-region 0xFC.. pointers) created by the
    stream/scene system. The clone never gets those (no stream record; no controller/stream links
    either - fD4/fE8 stayed 0).
- Also: the trigger's source guard (v16.5) works but the finder offered a ch=54/f7c=0 non-body
  entity that passed the part-def check (the entity at 0x3B115A40) -> cloned that instead of Edward.
  The finder/source selection needs refinement (require f7c=-0.5 && ch 16-40 && part defs).
- VERDICT: the graphics binder chain is fully understood up to the definition level. The last layer
  = per-instance scene registration (flag-routed creators 0x84A0F0-family / the 0xE0-size allocator
  wrappers 0x901700/0x901790) + stream ownership. That is a deep engine project with unbounded risk;
  NOT a one-more-cycle fix. Practical Edward = forge def-swap look on a driven body (proven path).
- Build v16.5 = 7F4A3245143159F2C69736051A73478D (deployed). Builds reviewed: 25EBF660 (v16.1),
  3DF5A007 (v16.3), 3B676323 (v16.4), 7F4A3245 (v16.5).

### 2026-10-08 (48) - v17 MATURATION TEST: the fill is world-membership-gated (definitive)
- Experiment: create an Entity at a fake key (0x7A3C9E01,7) via the corrected mass-create, register
  it (FUN_0051d290), then poll its slots every 15 s for 5 minutes.
- RESULT: 20/20 polls identical: ch=0 f50=0x1ED02078 (default) +0x5C=0 fAC=0 fB0=0 fD4=0 fE8=0.
  The shell is NEVER touched. Meanwhile the engine's own mass-created entities gain
  +0x5C=world-mgr + fAC(stream ptr) + fB0(instance) ~2 minutes after creation.
- => The world/scene fill pass walks only the world's own (data-backed) entity population; no
  registry-created or faked entity ever enters it. Combined with (47): the renderer layer is
  bounded by world membership end-to-end.
- Remaining concrete lead for a future session: find the FILL PASS itself - the code that writes
  the world-manager pointer into entity+0x5C ~2 min after load (a distinctive store of a global
  value to +0x5C on many entities). Static hunt + call it manually on the clone, or find the list
  it iterates and add the clone to it.
- Tooling state (all working, deployed): v14 registry fix (find/create thiscall), graphics factory
  call shape cracked (def on stack, cdecl; thunks), Edward clone pipeline (v6 recipe), part/body
  slot writes. The ONLY missing link = the fill pass entry. Build v17 = 4A854B443D1FF9B8A1CDB350FE140354.
- Ini left at CloneTest=false / SpawnTest=false / watches on (clean preset for a fresh session).

### 2026-10-08 (49) - THE FILL HUNT (deep road, session 1)
- Whole-.text scan for fill fingerprints (stores to +0x5C/+0x58 near +0xAC/+0xB0): 50 clusters.
  Inspection: they are CONSTRUCTORS/inits (node ctor 0x52A4A0 zeroing 0x50..0xD4; a 0x1E4E2DC-class
  ctor; reset paths; a marker-init at +0xD8=0x04DD5F8C). Not the fill.
- Decoded the JOB CALLBACK chain (the "late" work at ~2 min = the job queue draining):
  * FUN_005034B0 (deep-copy callback): chains into FUN_00527270, then copies the matrix into the
    state block 0x100..0x140 and iterates the +0x140 children via the FS-TLS context + [0x4DDF92C].
  * FUN_00527270 (node-clone callback): calls FUN_006470D0 (copy/transform), FUN_005130E0
    (swap the +0xC8 pointer with a freshly allocated REFCOUNTED handle from the 0x4DD5FA0 pool),
    FUN_005134F0 (per-class fixup: switches on [handle+0xC] class hashes 0x4DE70D45/4DE70D1C/
    4DE70D46/0x520FF28F/0x4DE71615/0xF9A83FD0 + [handle+0x10] type 0xB, masks bits in the +0x40 row).
- KEY FINDING: entity+0xC8 = a REFCOUNTED RECORD HANDLE (class hash + type at +0xC/+0x10) = the
  entity's world-record identity. The graphics/scene attach is apparently RECORD/STREAM-keyed, not
  in the callback chain.
- The v16.5 clone was freed by the engine within ~15 min (unregistered objects don't persist).
- NEXT EXPERIMENTS (candidates):
  A. THE RECORD-HANDLE SHARING TEST: clone a body, then copy a REAL body's +0xC8 handle into the
     clone (refcounted - increment the refcount!) - if the record-driven passes attach to "the
     entity of record X", the clone may receive the same treatment (graphics/scene).
  B. TRACE THE HANDLE CREATION: hook the 0x4DD5FA0-pool allocator / FUN_005130E0 callers to see
     WHERE real entities get their records (vs clones) - the record's creation flow may include the
     missing attach.

### 2026-10-08 (50) - Experiment A (record-handle share): NEGATIVE, clean
- v18.2 (B8D36E7A): plain record clone (0x46EA6AD0, ch=1 stub) + HShare: found a RENDERED citizen
  (0x3837FEC0, fAC set), took its +0xC8 record handle (0x30009D0C), incremented the refcount
  (28 -> 29) and wrote it into the clone. Watches at 4/10/30/60 s: clone UNCHANGED (ch=1, no
  fAC/fB0/fD4/fE8). => the record layer does NOT drive entity visuals. Falsified cleanly.
- Remaining definitive tool for the fill hunt: a software watchpoint - patch an INT3 over the store
  instruction candidates or use a write-watch on a REAL entity's fAC slot at maturity time, with a
  VEH handler in the plugin logging the writer's PC/registers. That answers "who writes fAC/fB0"
  once and for all. Queued as the next session's opener (needs a small plugin add: VEH +
  INT3 probes + auto re-arm).
- Builds tonight final: v18.1 B477F55E, v18.2 B8D36E7A (deployed).

### 2026-10-09 (51) - Adoption attempt, the resident-entities discovery, and the v19.1 fix
- v19 (73810D5A): world-key recorder (per load burst, RAM) + plant at the last completed burst's keys + shell watcher + LOAD HIT detector + 0-60s field watches. The user fast-traveled Tulum -> Havana; both regions' keys recorded (Tulum set = 1787).
- Plant run (in Havana, 23:20): 32 shells "placed" - but the log shows most returned ALREADY FILLED (ch 1..9, +0x5C=0x388AD0C0 world-mgr, real-ish f50, fB0 set): the world keeps its entity records RESIDENT in memory even after leaving a region. find-or-create FOUND the world's own entities; only ~3 slots were genuinely empty.
- Return travel Havana->Tulum WEDGED: "loading" screen 8+ min, game alive (render + hook ticking), ZERO LOAD HITs (the creation pass never touched our 32 keys before the hang). Killed. Cause unknown - could be unrelated, could be one of the 3 fresh shells (no evidence either way).
- STRUCTURAL FINDING: world entities are not destroyed on region unload within a session - they stay resident (world link kept; fAC/fB0 cleared out of region). The "fill" is a streaming act for resident regions. Hence: (a) every placement into a "fresh" region actually found existing records; (b) adoption can only be tested ACROSS a process restart (fresh session = truly empty slots for unvisited regions).
- v19.1 (1B45F963): all keys dumped to plugins\AC.BlackFlag.PatchFix.keys.txt (survives restarts); plant targets ONLY slots with no current entity (per-key registry find check) = genuinely fresh; plant waits for registry + valid world pos; watcher/LOAD HIT/deliver unchanged. Game closed at ~23:54 with the user in Tulum; keys file = 4644 lines (both regions recorded). FINAL STEP STAGED: launch with AdoptTest=true -> plant at boot -> one fast-travel -> the first VALID adoption test.

### 2026-10-09 - HEADLESS ATK PIPELINE: FULL EXTRACTION + BYTE-PERFECT ROUNDTRIP (AC4)
- Built `bf-coop/tools/atkbf` (.NET 9 console, references ATK 1.3.6 AnvilToolkit.dll) - headless ATK for AC4 Black Flag.
- Fixes needed to run ATK solo (all found in decompiled source, see D:\ac4work\atk-decomp):
  * cwd must be the ATK folder (Libs/*.dll loads are relative),
  * DataStorage.GlobalScimitarClassReader = new ScimitarClassReader() (MainWindow ctor normally does this; without it every nested read NREs),
  * DataStorage.ActiveGame = Game.BlackFlag + GameFileList.CheckStrings() + download Lists/BlackFlag.gfl (84k entries) or FileReference XML export dies on a WPF dialog,
  * HashedData.CheckStrings(), DirectXTexPath, TempPath, invariant culture.
- Proven headlessly on AC4 (game data, not Rogue):
  * `atkbf dump (<file>.raw) (<out>.xml) --game BlackFlag` -> XML for: EntityBuilder (Edward default, 20 KB), Material (11 KB), Skeleton (162 KB), BuildTable.
  * `atkbf compile <xml> <bin> --game BlackFlag` -> binary; **roundtrip byte-identical** (1552/1552 bytes, 0 diffs) for CHR_P_EdwardKenway_Default.
  * File references resolve to REAL PATHS via BlackFlag.gfl, e.g. `DataPC_CaribbeanSea\Leather Armor Parts\CHR_P_EdwardKenway_Leather_Set.3608045168`.
- Extraction chain (Python, proven): forge.py reads AC4 v27 forges identical to Rogue; anvil.py decodes .data containers (LZO); extract_resource.py pulls individual resources; edw bundle = 758 resources incl. CHR_P_BaseEntity_Male (Entity class 0x0984415E, no ATK XML support), visual masters (BuildTable), FX, ragdoll, sounds, nav.
- Key insight for the partner problem: EntityBuilder/BuildTable/Skeleton/Material are all XML-editable + recompilable; these are the character-definition tables. Next: repack containers (DataFile.Serialize) + forge, then study CharacterDefinition/spawn tables to make a data-backed Edward.
- REA/Ghidra note: function query failed with Java heap OOM (default headless maxmem 2G) - bump GHIDRA_HEADLESS_MAXMEM (e.g. 8G) and retry.

### 2026-10-09 (52) - v19.1 adoption test EXECUTED: first LOAD HIT + first world-links, then crash (dump archived)
- Plant at boot (10:50:57): 29 shells created (fresh-key scan over first ~861 file lines, stride 9). User in Tulum 10:52-11:28; resident Tulum load did NOT touch shells (no calls made for existing keys).
- FAST TRAVEL Tulum -> Havana: **LOAD HIT shell[3] key=(0x15C05910,0x7) at 11:28:35** - first ever; the Havana load's find-or-create reached a planted key.
- **World-link writes at 11:28:48.058**: shells 9-13 (0x30601EF0..0x30602330) got +0x5C=0x4626FD00 (this session's world-mgr) - first time planted shells got a world link -> the REGION load does adopt pre-placed shells (unlike the boot loader, which skips existing keys). No fAC/fB0/fD4/fE8, no RENDERED/delivered/freed.
- **CRASH ~0.5 s later**: AV 0xC0000005 at AC4BFSP.exe+0x4C10BA (VA 0x8C10BA) = FUN_008c10b0+0xA `movzx edx,[edi+0x26]`, edi=NULL. Chain: FUN_008af3e0 -> FUN_008ad750 (GraphicWorld::Entity::Components) -> FUN_008c11d0 -> FUN_008c10b0 (list append). Root: FUN_005200c0(PTR_PTR_027da8d0) returned NULL (registrar lookup unchecked). Crash entity = 0x44B2B650 (heap, NOT a shell); main-thread load-completion job chain (0xF1DE71 callback; frames FUN_00925xxx / FUN_00a326d0 / FUN_00a1daa0 / FUN_00816560). Shell17 ptr found as stale value on that stack (inconclusive). Dump: %LOCALAPPDATA%\CrashDumps\AC4BFSP.exe.25324.dmp (98 MB); decode tools: bf-coop\tools\analyze_crash_dump.py, dumpwalk.py.
- VERDICT: adoption path is ALIVE (region load touches planted keys; boot loader skips). Crash attribution OPEN (shell-destabilized load vs game fast-travel/job flakiness). NEXT: (1) repeat run for reproducibility; (2) if it crashes again -> control run with AdoptTest=false; (3) write-watch build (VEH) to ID the +0x5C writer.

### 2026-10-09 (53) - CRASHES ROOT-CAUSED: our act-ctl rescan froze the game ~3.2 s mid-travel -> v19.2 disables rescans
- Run 2 (11:48:55 plant, 29 fresh shells): same travel; LOAD HIT shell[3] again (11:50:36); crash 11:50:45 in nvwgf2um.dll+0xCB0E47 - the KNOWN recurring driver crash (see (15)). Dump: all 29 shell pointers appear ONLY in the plugin's own array; no shell memory in the crash path. Shell[3]'s block was already recycled before the load (11:50:32, raw heap values).
- SMOKING GUN: both run-1 and run-2 logs show an IDENTICAL ~3.1-3.2 s zero-line gap immediately before the crash (run1 11:28:40.847->44.036; run2 11:50:41.624->44.756). Duration matches find_player_ctl's documented "~3 s per pass" byte-wise walk (0x30000000-0x54000000, then 0x10000-0x7FFF0000). Mechanism: during fast travel the cached player node dies -> refresh_act_ctl fires a rescan on the game thread mid-load -> multi-second submission stall -> crash (game-code null deref in run 1, driver AV in run 2). The shells are NOT the crash cause.
- FIX v19.2 (MD5 17C0CA1831D3C813E1FE37A54E3DD622): new [PlayerTransform] ActScan (default false) gates rescans; when enabled the scan logs "ActScan: took N ms found=" for attribution; stale ctl/node are cleared when scanning is off. Rebuilt (cmake --build build-x86 --config Release), deployed via deploy-next-window.ps1 (NOTE: must run as `powershell -NoProfile -ExecutionPolicy Bypass -File ...` - a plain & call fails on this box).
- NEXT: rerun the same travel on v19.2 - expect no ~3.2 s stall, no crash; if it still crashes with NO stall -> investigate non-stall causes and consider the no-shell control run.

### 2026-10-09 (54) - RUN 3 (v19.2, scans off): freeze GONE, same game-code crash at +0x4C10BA -> shells/plant now prime suspect; control run staged
- v19.2 deployed (MD5 17C0CA1831D3C813E1FE37A54E3DD622), ActScan=false verified (0 ActCtl/ActScan lines). Plant re-ran (29 shells, 11:58:46). Travel Tulum->Havana: NO multi-second gap anywhere (max 1.1 s at boot) - the act-rescan stall fix works.
- Crash at 12:17:03: AC4BFSP.exe+0x4C10BA (VA 0x8C10BA), same as run 1: FUN_008c10b0+0xA `movzx edx,[edi+0x26]`, edi=NULL; byte-identical chain/args to run 1 (FUN_008af3e0 -> FUN_008ad750 -> FUN_008c11d0 -> FUN_008c10b0; frame2 args C086DF29/3F800000; frame1 arg2 0x1090DB28). Crash 13.2 s after LOAD HIT (run 1: 13.6 s) - same load-end phase, right after the "dumped 35 keys" burst (same last line as run 1). Only shell[3]'s key touched (LOAD HIT; its block already recycled). Dump AC4BFSP.exe.13860.dmp: shells appear only in the plugin's array; shell[17] again sits as stack residue at 0x0C57FC1C (same slot as run 1 - plugin tick residue, not causal).
- CONCLUSION: run 2's driver crash was stall-induced (fixed), but runs 1/3's game-code crash is a SEPARATE deterministic event at the end of the Havana travel load. Correlation: 3/3 shell-planted travels crashed; v19's shell-free Havana arrival (10/8) succeeded.
- NEXT: control run, AdoptTest=false (plugin on, NO shells) - if the travel completes, the shells/plant are implicated; if it still crashes at +0x4C10BA, go plugin-off (asi renamed) next to separate plugin from game.

### 2026-10-09 (56) - v19.3 knobs built; E1 crash was a HAVANA-SAVE load (29 shells); E2 sniper (1 shell) SURVIVED - crash scales with shell count
- v19.3 built+deployed (MD5 D5DAF4ABB47428F3491EDB992421958F): new [Coop] knobs AdoptOnly (plant only this key), AdoptSkip (never this key), AdoptMax (cap count); plant log prints only/skip. (Also learned: the user's save is now a HAVANA save - the control run's arrival autosaved there; "continue" loads into the Havana area directly.)
- E1 crash reinterpreted: 29 shells, Havana-side load (menu -> (0,0,0) -> crash +4.5 s, no Tulum stage). So the +0x4C10BA crash hits Havana-side loads with many shells, both save-loads and travel-loads.
- E2 (sniper): AdoptOnly=15C05910:7 -> exactly 1 shell. Havana save-load sequence SURVIVED; player walking in Havana 2+ min (no crash, no freeze, no LOAD HIT - the save-load path does not call find-or-create for the key; the travel-streaming path does). The shell block WAS written during the load: w5C=0x1E43694 fAC=fB0=0x273F09FC fD4=0x1B0496A5 f50=0x0; live-read vt=0x01E5EE48 (adopt-vs-reuse still ambiguous).
- PATTERN: crash scales with planted-shell count (0 and 1 OK, 29 crash). NEXT: round-trip travel test in the LIVE session (Havana->Tulum, then Tulum->Havana) with the 1 shell - the return is the exact streaming load that crashed with 29 shells; watch for LOAD HIT + adoption on the single shell.

### 2026-10-09 (57) - ROUND TRIP SURVIVED with 1 shell; LOAD HIT x2 (both legs); the load processes our key but the block ends up repurposed
- User did Havana->Tulum->Havana (12:42:03-12:42:32): all loads completed, game stable. **LOAD HIT shell[0] key=(0x15C05910,0x7) at 12:42:02 (Havana-exit leg) and 12:42:18 (Tulum-exit leg)** - the destination loads asked for our key on BOTH legs (the key is in both regions' sets).
- Shell block writes during the legs (12:42:09: f50=0x40004 w5C=0xA000A fAC=0xFC6C36B0 fE8=0xFC6C00A0 ch=64620; 12:42:25: f50=0x32010A fB0=0x32028A). LIVE READ (12:43, game alive): the block now holds NON-ENTITY structured data - repeating records tagged 0x02000401 with hash-like ids and fields 0x000A0000/0x0032000A, plus a tail list of (0xFC7A7xxx arena ptr, 0x00070007) pairs. So: the load found/processed our key, but the block is repurposed data (not a clean adopted entity). NOTE: 0xFC6C/0xFC7A/0xFC7D arena = same family as the crash-context 'this' pointers (0xFC739B30/0xFC7D9B64).
- CONFIRMED: crash scales with planted count (29 -> crash; 1 -> survives; 0 -> survives). NEXT: ramp at AdoptMax=8 (same flow: continue + round trip); if OK keep raising, if crash bisect down.

### 2026-10-09 (58) - 8-shell run SURVIVED; shell[4] ADOPTED (dock piece); teleport + graft experiments; scene identified
- AdoptMax=8 run (plant 12:48:19): LOAD HITs x8 across loads (shell[3] x4 + shells 4-7 on the last leg); round trip survived, no crash/freeze.
- **shell[4] (0x3370DDA0, key 0xF1EF333E:7) got ADOPTED**: def 0x1ED82058, ch=1, f7c=-1.0, w5C=0x46AA5370 (world link that toggles with region load/unload), real transform at +0x40, registration at +0xC8 (replaced the "unset" static marker 0x04DD5F8C). It is a member of the DOCK-STRUCTURE family (same def as planks/pilings at the player's feet) - a structural type: fAC/fB0=0 -> invisible by design.
- Teleport test: external write of +0x40 to the player - accepted, STUCK (entity not transform-driven); user confirms nothing visible (structural). fB0 graft (sibling's transform-cache pointer) - accepted, logged, no crash, no visual change. fAC graft not fired.
- Scene scan: 2,161 Entity-class objects in heap, 1,684 WITH visuals. The big object next to the player = the dock-worker NPC (ch=18, f7c=-0.5, full graphics; visible in user screenshot); the ch=32 entity at 0.0m = likely Edward's own body.

### 2026-10-09 (59) - KEY-FINDING BREAKTHROUGH: entities carry world keys; first AIMED plant (visible-prop key)
- Entity structures carry world-key pairs that match our recorded keys file. SHALLOW offsets (+0x0C..+0x5C) = the entity's OWN key; DEEP offsets (+0x14C..+0x584) = referenced/spawner keys. Calibrated on the adopted shell (own key) and the dock worker (deep key (0xB9F6CBD7,7)).
- Scanned the 37 visual entities within 30m: 33 carry keys. Clean shallow-key props (f7c=0.0, ch=3-4, fAC set) e.g. 0x44F3B620 (pos 114.4,-76.2,5.0) key=(0x2821090F,0xB).
- AIMING without rebuild: prepend 3 lines to keys.txt (plant scan reads every 3rd line) -> target becomes candidate[0]; AdoptOnly selects it. (1st attempt failed: guard skipped because the key already existed deeper in the file; fixed with unconditional prepend.)
- SNIPER PLANTED: shell[0] 0x2B3DCC10 key=(0x2821090F,0xB) - key of the visible 3-component prop. Session pid 22296. PENDING: load Havana save -> watch LOAD HIT + visual fill (fAC) on our shell -> if OK, first adopted VISIBLE object; next aim at character keys (dock worker (0xB9F6CBD7,7)).

### 2026-10-09 (55) - CONTROL RUN (AdoptTest=false): travel SURVIVED -> planted shells implicated
- Session pid 22992 (launched 12:21:49; AdoptTest=false VERIFIED: no plant markers, no LOAD HIT, no shells). Save loaded to Tulum (179.2,56.8,0.3) at 12:22:17; fast travel started ~12:22:19 (loading pose 6.3,-15.5,-13.0 at 12:22:21-23); arrived 12:22:31.9; settled (102.4,-73.8,2.3) at 12:22:36; NO crash, NO freeze; stable 6+ min (log to 12:29+). No new dumps, no new app errors.
- Contrast: 3/3 travels WITH shells crashed (runs 1-3: two identical game-code crashes at AC4BFSP.exe+0x4C10BA, one stall/driver crash); the shell-free travel completed cleanly. => the planted shells trigger the game-code crash at the END of the destination load.
- NEXT: E1 = re-enable plant (AdoptTest=true), rerun the travel to confirm the crash returns. E2 = build with new ini switch [Coop] AdoptSkip="LLLLLLLL:HHHHHHHH" to SKIP the one key the destination load always requests (0x15C05910,0x7): if the crash is that single interaction, a 28-shell plant should survive.

### 2026-10-09 (60) - SHELL ROUTE CLOSED; keyed dock characters found; **mod9 forge build (Edward) BUILT + DEPLOYED** + big-scope directive

- **Shell/adopt route FALSIFIED conclusively:** the sniper shell at the visible-prop key (0x2821090F,0xB) got NO LOAD HIT across a save load + round trip — the engine only find-or-creates keys that are MISSING at load time (a live shell makes the load skip the key entirely). Earlier "adoptions" = heap block reuse (shell[4] ended up serving a different key). Also: crash scales with plant count (29 -> deterministic load-end crash at +0x4C10BA; <=8 -> survive) = planted shells destabilize the load-end job chain. Route closed; do not re-plant. (ini now AdoptTest=false.)
- **World-key registry walk decoded:** scan memory for the entity's 8-byte (keyLo,keyHi) pair; registry entry base = pair_addr-0xC = {ptr, rc, flags(0x8000000x), keyLo, keyHi}, stride 0x14 (found near 0x3808D3xx/0x3809DExx). Entity (vt 0x01E4CE90) fields: +0x40 pos, +0x50 (def-slot; for CHARACTERS/player this points into code/module range — NOT a plain def; runtime def-chain for chars unresolved), +0x5C world link, +0x66 ch, +0x7C f7c (-0.5 = body), +0xAC fAC, +0xC8 registration (carries keys), +0xE8 controller.
- **KEYED PERSISTENT characters found (the partner frame):** key=(0xF00056E0,0) -> entity 0x45B497A0 @ (111,-66); key=(0xF000570A,0) -> entity 0x460F4610 @ (109,-73) (Havana docks). ch=21, f7c=-0.5, controller +0xE8, shared world-link 0x45C914A0; rebuilt every load = persistent BY DESIGN. Player's own body: 0x4414E6A0 (ch=32).
- **USER DIRECTIVE:** treat as a big AC4 Black Flag addition — co-op on the level of Skyrim Together; write freely ("if we can write, we write"), no tiptoeing. (Standing: SP/offline, own game, no rehosting game files.)
- **mod9 BUILT (forge def-redirect, data-side, on top of mod7):** source = `CHR_P_EdwardKenway_Walpole` (Edward in the Walpole-disguise robes; hash32 0x3652BE80, 369189 B, 2 internal identity occurrences @0x43a/0x175c) -> for each target: private EOF copy + identity dwords patched to the target hash + TOC offset/size repointed. Targets = `CHR_C_M_Spanish_Medium`, `CHR_C_M_Spanish_Poors`, `CHR_C_M_Spanish_Rich` (Havana street/dock folk). File: **D:\bf4_mod\DataPC_extra_chr_mod9.forge** (1532058490 B). VERIFY pass green (all three -> copy@EOF size 369189). Script: bf-coop\tools\make_mod9.py.
- **DEPLOYED:** game closed (killed pid 22296), game `DataPC_extra_chr.forge` <- mod9, MD5 src==dst = C641619371A42C160E69C391C7F7E82F; ini AdoptTest=false for a clean visual test. Relaunch at 13:23: one phantom post-kill ntdll crash appeared (pid 9944, ntdll+0x50862 — SAME family as 10:47/10:50/12:31 events = the known kill->relaunch launcher hiccup, NOT our code) -> then clean session pid 11796; plugin journal init_complete; key recorder live.
- **Fallbacks on disk:** mod8 (same targets, Duncan source), mod7 (previous live), pristine original — all in D:\bf4_mod. Instant swap if the Edward variant misbehaves.
- **NEXT:** user loads Havana -> check the docks: dock/street folk should render as Edward (Walpole robes + Edward head/face). Then: DRIVE one keyed character via the proven engine setter FUN_0063c2d0 (alignas(16) matrix + dummy 2nd stack arg, `ret 8`) and wire it into the net relay. (The old live f50-probe idea for the dock worker is superseded.)

## 2026-10-09 - FIRST CONFIRMED DEF-SWAP RENDER: world NPC as exact Edward
- mod12 (pristine + 4 probes: CHR_C_F_Poor<-Duncan, CHR_C_F_Rich<-EdwardStd, CHR_G_Spanish_Soldier<-EdwardStd, CHR_C_M_Slaves<-EdwardStd): FIRST successful render of a swapped look on a non-player character. User: "exactly like my edward, outfit and face and all", walks normally (hands behind back), "not a single other edward" after searching.
- The rendered NPC: entity 0x47F2BE30, key F00030AE; member of the keyed dock-worker gang (co-keyed F0003090/307B/3E42, dock key block F0002xxx-F0003xxx). Signature: ch=29 cnt=32 (player ch=32 cnt=34; normal NPCs cnt 17-23). Full-world census at the time: exactly 2 bodies with cnt>=26 = player + him.
- Render count = 1 despite def-level swap -> his source def has ~1 instance in the loaded world (rare/unique-use class) or other instances unloaded.
- f50 (+0x50) on characters = pointer into module code (x86 bytes) = current-behavior tick; changes with state (0x5FCA227C -> 0x5FDA227C -> 0x5F8A2264). NOT a class/def id. entity->def mapping still unsolved (inline hash scan 0x800B: 0 hits; 3-hop pointer chase 400 blocks: 0 hits).
- ATK cannot parse these defs: "ScimitarClass Failed=True, not XML-supported" -> offline XML route dead; engine is the only reader.
- hash32s (extra_chr): EdwardStd 0x9A958CF0 | Duncan 0x51BAB7D4 | F_Poor 0xC1BB9618 | F_Rich 0x64D5F55C | Soldier 0x12CECF74 | Slaves 0xB3DE056C | M_Spanish_Medium 0x12CECF30 | Generic_Sailors 0x8FB6DABC | Jackdaw_Sailors 0xE78D9C36 | Player_Default 0xC0A3FCE0.
- mod13 DEPLOYED (isolation build, one variable vs mod12): CHR_C_M_Slaves target now carries Duncan content. Decode when user finds the walker: robed/vanished => def pinned = CHR_C_M_Slaves; unchanged => def in {CHR_C_F_Rich, CHR_G_Spanish_Soldier} -> one more single-change test (mod14).
- Tools added (bf-coop/tools): dump_f50.py, dump_fac.py, dump_ent.py, dump_ent2.py, lookup_hash.py; scene_scan.py updated (full-char filter + cnt>=26 body census).
- mod13 result (user): the walker was STILL EDWARD -> CHR_C_M_Slaves eliminated (and F_Poor was already out via the Duncan look). Remaining candidates: CHR_C_F_Rich | CHR_G_Spanish_Soldier.
- mod14 DEPLOYED (one variable vs mod13): CHR_C_F_Rich target now carries Duncan content; only CHR_G_Spanish_Soldier keeps EdwardStd content. Decode: walker turns robed/vanishes => pinned = CHR_C_F_Rich; walker unchanged (Edward) => pinned = CHR_G_Spanish_Soldier.
- Walker continuity across loads: new entity address/key per load (mod13 session: 0x44CCFCE0, key F0002094, at (32.0,-92.8)); invariant signature = ch=29 cnt=32.
- mod14 result: after F_Rich->Duncan, NO Edward-shaped (ch29/cnt32) body exists anywhere in the loaded world across repeated full sweeps; user searched: "perhaps he's plain gone". USER CLUE: the walker "walked like a woman" (female anim set) -> CHR_C_F_Rich (F_Poor excluded: he was Edward in mod12/13 while F_Poor wore Duncan; Slaves/Soldier excluded by mod13). CONCLUSION: walker def = CHR_C_F_Rich.
- 2821090F clarified: NOT a character - it is the key of a visible 3-component prop at (114.4,-76.2) from the closed sniper-shell experiment; AdoptOnly=2821090F:B is a leftover, not a targeting lever. AdoptTest stays false.
- mod15 (THE KEEPER) DEPLOYED: pristine world + ONE swap only (CHR_C_F_Rich <- EdwardStd content, id-patched). If the walker returns as Edward -> final partner-look build / F_Rich confirmed. If he appears as a normal soldier -> he was the soldier def (then one more single-swap build).
- tp tool ready: tools/tp_entity.py (burst-writes feet +0x40 to target xyz; entity found by ch29/cnt32 scan).
- mod15 KEEPER LIVE RESULT: the walker came back as Edward - and there are FOUR Edward-bodied NPCs in the world (ch29/cnt32 x4, not one): the F_Rich class has >=4 members. User found 2 at the harbour; memory census found 4 (0.7m/14m/31m/46m from the player). DEF CONFIRMED = CHR_C_F_Rich (the "walks like a woman" female anim set now explained).
- TELEPORT WORKS: tools/tp_multi.py held 3 of them at the player's position for 40s (burst-writes feet +0x40, 1197 writes). All four Edwards delivered around the player. Write path = proven again on crowd/keyed bodies.
- mod15 = final look build if confirmed: pristine world + ONLY CHR_C_F_Rich <- EdwardStd content.
## 2026-10-09 (evening) - CO-OP PIPELINE LIVE END-TO-END + nav/anim dig opened
- THE FULL DRIVE PIPELINE RAN LIVE, AUTOMATIC: fake remote (UDP) -> handshake -> live position stream -> targeted body pick (children>=24; the four Edwards have 29) -> despawn-pin armed automatically (private vt 0x48AF0000) -> per-frame drive to the peer position (err=0.00m). No external scripts. Verified: playerTransform body=1@39CED530 (Edward, ch29/cnt32) driven at the player's side.
- CRASH FIX LIVE: the body-pick scan (0x30000000-0x50000000 sweep) got SEH guards in ghost_body.cpp (scan inner loop + valid_body) - survived the full pick+drive cycle. (The 15:24 crash = an unprotected sweep read during a racing page decommit; hook died permanently.)
- HAND SHAKE SAGA SOLVED (two causes): (1) the old port pair 27973/27974 was jinxed by stale socket state from crashed sessions - fresh ports work; (2) startup binds race with Ubisoft overlay process spawns that inherit the plugin's UDP socket. WORKING RITUAL: live-rebind the plugin's port (edit ini LocalPort/RemotePort; the ini watcher reconfigures live) + connect the fake/real peer right after. Also: multiple overlapping fake-peer processes silently fail to bind - check Get-NetUDPEndpoint before blaming the net.
- NAV WALL UNDERSTOOD (deep dive tonight): FUN_01785ed0 = NavigateTo; it validates the target, runs the vtable+A8/BC "can-navigate" precheck, clears a flag at nav+0x23/0x20, ENQUEUES the target (FUN_0061f180 = pos-target / FUN_00624410 = with-ctx; these are the watch hook sites (abs 0x61F180/0x624410)), then calls vtable+0xE0(speed,0) as activation. rc=0 = fully accepted - but the NPC never moves => the actual walking is done by the BEHAVIOR system consuming the nav queue, not by NavigateTo. Nav and animation = the same subsystem (the crowd behavior).
- NavTest live: fires (template=1 validate=1, rc=0 x6 reissues), chosen nav 0x39024510, ent=(29.3,-165.7,4.2) frozen => confirmed no consumption. Note: speed readout still garbage (240 m/s) - the mover-detection field needs a fix.
- NEXT DIG (nav+anim): anchor the crowd behavior (BhvGenericNPC) at RUNTIME via the ghost's controller (entity+0xE8; the plugin already logs ActCtl for the player); find what consumes nav targets + starts movement + plays the walk anim; then a "walk request" write; then wire: nav-walk when far / raw-drive when close. Static anchors: BhvAssassin strings in part_00158/00160 region; gamedb index at bf4_re\sp_src\.gamedb\index.sqlite (schema: files/functions/strings/symbols/edges; function names carry absolute addresses; file_id+shifted names e.g. file_id 202 = part_00200.c).
- Tools added: sprint_drive.py/sprint_drive2.py (multi-entity sprint + yaw basis writes - rotation math copied from ghost_body.cpp: for dir (dx,dy) row0=[dy,-dx,0,0] row1=[dx,dy,0,0]), tp_multi.py, follow_drive2.py, test_hello.py, probe_welcome.py, listen27973.py/listen_reuse.py, gamedb_probe.py/gamedb_nav.py/gamedb_find.py/gamedb_bhv.py/gamedb_str.py, scan via scan_compact.py.
## 2026-10-09 (late) - nav/anim dig night 1: the mechanism is found
- Player vs crowd behavior classes: player ctl/behavior vt = 0x026FA898, crowd = 0x026E34D8 (all Edwards + crowd NPCs; the pinned ghost keeps a private copy 0x48AF0000). 18 vtable slots differ (the class-specific methods; both sides interesting: +0xB0 = player FUN_0076c900 vs crowd FUN_0076bf10 - same 0x76xxxx subsystem).
- The behavior/ctl object = a CHILD COMPONENT of the entity (entity+0x60 list, +0x66 count; the Edward had 29 children; the crowd behavior = child[28] = the +0xE8 ctl object; +0x00 vt, +0x08 = owner entity backref).
- The action/anim update = FUN_01ac1ad0 (part_00235.c:17331+): reads REQUEST slots on the behavior (in_ECX+0x2F50, +0x2F54, +0x2F58, +0x2F64 ...) and, when != -1, applies them over LIVE fields on a second object (iVar6: +0x8D4 blend, +0x8D8, +0x8DC, +0x8E0 phase, +0x8E4/+0x8E5 bytes) -> that pair (request -> live) IS the animation control surface. Writers of +0x2F50: part_00235.c:35058/35066 (the request setters).
- Component resolver FUN_013aec10 = walking the entity+0x60 list (cursor in the passed ctx).
- NEXT (live experiment queue): (1) identify the crowd behavior's own update (the FUN_01ac1ad0 analog; find its slot in the 0x026E34D8 vtable via the player-side slot index once the player behavior object is located live); (2) find the walk-state request values (what the AI writes at +0x2F50.. to make an NPC walk); (3) live write-test: request a walk state on a free Edward + watch the anim fields + position; (4) nav tie-in: why the enqueued nav target isn't consumed.
- Live inspector tools: inspect_live.py (Edwards+ctl), inspect2.py (player ctl + vt diff), vt_dump.py, vt_slot.py, read_slots.py, children_dump.py, gamedb_*.py (index queries).

## 2026-10-09 (late night) - CRASH POST-MORTEM: raw +0x8D0 writes are dead; engine request channel only from here
- WHAT HAPPENED: two direct-write probes (tools/anim_write_test.py, then tools/anim_act_test.py - 24B rows at beh+0x8D0, 20Hz, one Edward + two live crowd NPCs, user mid-play) AV'd the game ~1s into the second run. Dump AC4BFSP.exe.16084.dmp: exception 0xc0000005 READ of 0x7B; fault RVA 0x3437A9 `mov eax,[edx+8]`, edx = *(this+0x2C) = 0x73 - a small integer consumed as a pointer. The row we were writing had 0x00000073 at +0x0C of the payload: exact match. Full analysis: bf-coop/crash_dump_analysis.txt. Chain (gamedb): per-entity child update FUN_00513360 -> child vt+0x94 -> FUN_00625D70 -> FUN_00750440 -> FUN_007437A0 (refcounted state-object swap; virtual calls +0x130/+0x300). The corrupted slot maps to an embedded controller subobject around beh+0x8B0 whose +0x2C (absolute beh+0x8DC) is the 'current state object' pointer the tick swaps - our payload put 0x73 there and the next tick dereferenced it.
- RE-INTERPRETATION: the beh+0x8D0 region is heterogeneous per object (floats 1.0/0.6 on one, heap pointers on another, u16 'families' on a third) - the small-sample 'state family' story is suspect and direct replay is banned forever. Also observed: during the final live seconds the three write targets drifted 0.7-2.4m - could be corruption side-effects; unverifiable (crash), not claimable.
- WHY: +0x8D0 is NOT a uniform state table across objects. Pre-write live rows: floats (1.5708=pi/2, 0.4, 1.0), pointer table (0x04DD5F8C, 0x01E546E8), Edward = mixed; even a single object transiently holds pointer fragments during stream-in/out (visible in the state_map capture t=10.4). Writing small values over pointer slots -> engine deref'd 0x73. The night-1 note ("Edwards' +0x8D0 = pointer tables, not scalars") is confirmed the hard way.
- STATE: saves backed up (bf-coop/saves_backup_20261009, 54 files); forge md5 75C44733769120EB97326F592C7E0F25 and asi md5 F8CED2592721CA6269E8C5A1FA397289 both unchanged; game relaunched clean (pid 10884, in-world, plugin live, NavTest/NavWatch off).
- GUARDRAILS: anim_write_test.py + anim_act_test.py marked DO-NOT-RUN. EXTERNAL memory writes on live objects: banned. All state changes only in-plugin, only via the engine's own request path.
- NEXT (safe plan): (1) hook the applier FUN_01ac1ad0 + setter FUN_01ad9190; drive the ghost's anim via the request slots (behavior+0x2F50..+0x2F64, -1 = leave untouched) so the engine validates its own inputs; (2) read-only: find the walk-state writer on a moving NPC; (3) mirror player anim -> request slots -> ghost; live test only after (1).

## 2026-10-09 (evening, post-crash) - v21 read-only anim observers: player vocabulary captured; crowd class divergence; walk-state regions + the state machine found
- v21 observers DEPLOYED (asi md5 CC6815DFBAF6CFED66B0E95194933649): AnimApply probe @ FUN_01ac1ad0 (RVA 0x16C1AD0) + AnimWrite probe @ FUN_01ab52c0 (RVA 0x16B52C0); read-only, capped logs, heartbeat every 4096 calls; zero writes this session.
- PLAYER VOCABULARY (user parkour run ~17:24-17:26): idle c=0x3F d=0x2A (pulsing on/off); run/free-run a=0x48 e=1 with c settling 0x57; climb/descent d=0x83 then d=0x07; one c=0xB0 blip. Writer param map confirmed per-event: a->+0x8D4 (blend), c->+0x8D8 (hang), b->+0x8DC, d->+0x8E0 (phase), e->+0x8E4, f->+0x8E5.
- REQUEST SLOTS stayed all -1 for the whole session => normal locomotion does NOT use the request path; the live 6-tuple write is the authoritative surface.
- CLASS DIVERGENCE (explains the crash; kills the naive value-copy mirror): player ctl (vt 0x026FA898) +0x8D0 region = scalar anim fields; crowd/Edward ctl (vt 0x026E34D8) +0x8D0 region = pointer tables + scalar mix (live dumps: heap pointers, 0xAAAAAAAA fill, u16 ID families). The ghost is a crowd body: drive must go through ITS OWN machine.
- WALK-STATE HUNT (read-only): full-tree diff, walk 16s vs stand 10s on a walking crowd NPC: 349 offsets changed walking / 0 standing. Candidates: ctl+0x26E0..+0x26EA (u8 counters/bits), ctl+0x28F0..+0x28FA (16-bit-ish accumulators, ~0x1E step), ent+0x74..+0x76 (float bytes), ent+0xB4 (~+6/step), ent+0xB8, ent+0x10..+0x26 (matrix rows), ent+0x38..+0x3A.
- CAVEAT: a short recheck (1.5s x 5 subjects) saw no changes in the ctl counters - the regions appear tied to actively-walking subjects; watch_states.py is ready for a verified live walker (children list + ctl regions + ent).
- STATIC (gamedb, part_00093.c): ctl+0x26E0 and +0x28F0 are the far side of double-buffer SWAPs in FUN_00d7e290 (swap +0xEC4<->+0x26E0, +0xE34<->+0x28F0, +0x16D4<->+0x26D8) => staging<->live state commit pattern.
- THE STATE MACHINE (crash chain decoded): FUN_00513360 -> child vt+0x94 -> FUN_00625D70 -> FUN_00750440 -> FUN_007437A0 = REFCOUNTED STATE-OBJECT SWAP: *(controller+0x2C) = new refcounted object (FUN_00a0bde0 alloc; LOCK refcount inc/dec; virtuals +0x130 old / +0x300 new). The controller is the embedded subobject around beh+0x8B0; +0x2C = abs beh+0x8DC = the exact field the raw write clobbered (0x73 -> deref 0x7B). The crowd behavior/anim state lives on this machine.
- NEXT (safe plan): (1) read-only hooks on the swap chain + the +0x26E0/+0x28F0 staging writers while a verified NPC walks; identify idle/walk/run state objects and who stages them; (2) design the drive through the engine's own state path (never raw +0x8D0); (3) keep the raw-write ban (RCA: crash_dump_analysis.txt).
- Tools added: parse_animlog.py, walk_tree_diff.py, crowd_counter_check.py, edw_tree_watch.py, watch_states.py, vt_diff.py, resolve_diff.py, ctl_layout_check.py, gamedb_*.py helpers.

## 2026-10-09 (night) - crowd-anim dig: the +0x2000 arena caught live; watchpoint v2; one self-inflicted crash (fixed)
- **PLAYER WRITER FULLY MAPPED (v21 hooks + static):** `FUN_01ab52c0` = resolve target via `FUN_013aec10(behavior+4)` then write +0x8D4=p1, +0x8D8=p3, +0x8DC=p2, +0x8E0=p4, +0x8E4/+0x8E5=bytes. `FUN_01ac1ad0` (applier, called per-frame from `FUN_01af9f40`) first calls it with pending-action values, then re-calls with override values from behavior slots +0x2F50/+0x2F54/+0x2F58/+0x2F5C/+0x2F60/+0x2F64 (all `-1` = inactive on the player; engine uses the action path). Player behavior object 0x48161620 live: +0x4=entity 0x44E3FE10, +0xC=ctl 0x3C3407C0 (vt 0x026FA898), +0x10=0x484B0000, +0x14=0x04DD5F8C. AnimWrite probe fires ONLY for this=0x48161620 (~27/s even idle) -> **crowd NPCs never call the player writer; the crowd anim writer is a different engine function.**
- **CROWD CTL ARENA (the real live zone):** ctl+0x2000..0x3000 (vt 0x026E34D8 bodies) is a per-frame-updated arena; walk-diff #2 (same NPC, 20s walk vs 12s stand) shows walk-only churn at **ctl+0x2F00..0x2F1E (~183 changes), +0x2DBC..+0x2E80 block writes, +0x344C..+0x3464**, ent+0x74 float, ent+0xB4 counter. `tick_hunt` (14s, all NPCs): ctl+0x2600-type blocks update continuously on many NPCs AND on the standing player (5696 changes) -> arenas tick with the state machine, not only with locomotion. FUN_00d7e290 remains the staging<->live swap (pairs like +0x8D4<->+0x2630, +0xEC4<->+0x26E0, +0xE34<->+0x28F0).
- **ARENA PRODUCER CAUGHT (live):** hardware write watchpoint on ctl+0x20C0 (NPC ctl 0x48D32C70): 24/24 hits at **EIP=0x016D453B (AC4BFSP.exe+0x12D453B, inside FUN_016D4170+0x3CB)** writing `[esi+0x250]` (esi=ctl+0x1E70), edx stepping ~+0x1D0/hit, from ~10 different worker threads = a parallel engine job. Candidate anchor for the walk/anim commit. Log: bf-coop/logs/watch-writer-20261009-185223.log.
- **SELF-INFLICTED CRASH (our tool, NOT the game):** watch-writer-addr.ps1 v1 crashed the game right after detach: dump AC4BFSP.exe.24272.dmp -> exception **0x80000004 STATUS_SINGLE_STEP** at 0x016D453E on tid=14448 with esi/edx exactly matching HIT#24. Mechanism: v1 tracked a single pending stepTid; 24 hits from many threads orphaned trap flags; at DebugActiveProcessStop an unhandled single-step fired. No raw writes involved; distinct from the 0xc0000005 raw-write crash.
- **FIX (v2, validated):** `watch-writer-addr.ps1` now manages per-thread pending single-steps (HashSet), drains them before detach, and DISARMS (DR0-3/DR6/DR7 + TF clears) on every thread before DebugActiveProcessStop. PS parse + C# compile checks pass. Game relaunched clean (pid 21660, plugin live, PlayerTransform heartbeats OK).
- **CHILD CLASS SURVEY (for the record, no literals):** 026CB120 player-only child w/5 subobjects; 026EE050 controller w/4-entry handler table (also 2x on player); 01E6CC50 render-node/display-list; 01E41E58 big NPC controller; 01E410F0 scene/render-node wrapper; 01E47480 container of 0xc-byte entries; 01E5CD10 component w/8-byte entry array; 01E61938 location/pose (floats ±1.0f); 026E34D8 = minimal attr/flag child = the crowd ctl; 026FA898 = player ctl class. Crowd ctl = last valid child ([N-1]); children arrays are sparse.
- **NEGATIVES THIS NIGHT:** 90s snapshot of a verified walker: ctl+0x8B0/+0x26C8..0x2700/+0x28E0..0x2918/+0xEB8/+0xE20/+0x2F40..0x2F80 byte-static while walking (ent fields changed continuously) -> those ranges are NOT the walk live-writers. +0x2F00 family was missed by that capture (captured from +0x2F40).
- Tools added (bf-coop/tools): anim_snap_parse.py, child_watch.py, find_c14.py, find_walker_ctl.py, tick_hunt.py, scan_hot2.py, hot_dwords.py, wf_candidate.py, rd_multi.py, gamedb_fn.py, gamedb_rel.py, gamedb_lookup.py; children_dump.py extended (speed + m26E0/m28F0 markers); watch-writer-addr.ps1 rewritten v2.
- **NEXT (safe):** (1) identify FUN_016D4170 in the corpus (arena producer) and what drives it; (2) re-run walk-diff with the v2 watchpoint on ctl+0x2F00 of a VERIFIED walker to catch the walk-state writer; (3) keep the raw-write ban; all probes read-only.

## 2026-10-09 (night #2) - second watchpoint crash (v2 disarm race), v3 fix + sandbox validation; crowd anim state is child-level
- **CRASH #2 (again our tool, again not the game):** the v1->v2 watchpoint run that caught the ctl+0x2FB0 writers ended with `STATUS_SINGLE_STEP 0x80000004` at the exact watched instruction (AC4BFSP.exe+0x25939D) 1s AFTER detach. Root cause: v2's mandatory-disarm pass swept 88 threads but 89 had been armed (one thread missed / context set race on a running thread) -> a leftover armed thread raised an unhandled single-step on its next write to the watched address. Dump: AC4BFSP.exe.21660.dmp, tid=24344, eip=0x0065939D, eax=0x4079 (one more than the last hit's 0x4078). No raw writes involved; distinct from the 0xc0000005 raw-write crash.
- **v3 FIX (validated in a sandbox first):** `watch-writer-addr.ps1` v3: every DR/TF context write now happens with the thread SUSPENDED + VERIFIED (suspend -> get -> set -> get-verify -> resume); grace drain of queued debug events after maxHits; verified disarm loop (sweeps until zero armed); post-detach verification sweep. Sandbox = `tools/TestWatch.cs` (x86 C#, 8 threads hammering the same dword): 40 hits, 5 pending single-steps drained, disarm pass 1 -> 0 armed, verify sweep -> 0 armed, post-detach -> 0 armed, target process lived. The HIT log now also scans the stack for code addresses (`stk:` field). Live game captures with v3 resume in the next entry.
- **WHAT THE CAPTURES FOUND (walk-state block on the crowd ctl, +0x2FB0 area):** writers are two *tiny accessor* functions with `in_ECX` = the object containing the block:
  - `FUN_0040b5a0` (part_00000.c:7924): copies 4 dwords param_1[0..3] into [this+0x230..0x23C], then zeroes +0x23C. Callers: FUN_004e4400 (part_00010.c, inside a big per-frame behavior update that reads FUN_0061f210 = "get path/pos point" and `vt+0x48` sub-object; writes [iVar7+0xC0..+0xCC] and [iVar7+0x180]) and FUN_0134aae0 (part_00152.c:230: writes a companion's +0x260 from [in_ECX+100], uses vt+0x48 of the +0x19C provider). So +0x230/+0x240/+0x250 rows = a 3x4-ish transform/attachment fed from path points — NOT the anim state itself.
  - `FUN_00659390` (part_00027.c:12820, via FUN_00659a80 <- FUN_016df090): zeroes [this+0x230..+0x26C], flips bits +0x224/+0x226/+0x227, resets list +0x284/+0x28A. A reset/clear.
  - Companion writers: FUN_0040b5c0 (writes +0x240 row), FUN_0040b5e0 (+0x250 row). All three store ROWS of 4 floats.
- **CORRECTION TO THE ARENA STORY:** ctl+0x2000..0x3000 is not one arena. The +0x2F00.. block is a stack of 4-dword rows/records written by the above accessors; the earlier "arena producer caught" (EIP 0x016D453B in FUN_016D4170, part_00192.c:12671) is the same family (FUN_016D4170 computes squared distances vs a target and calls vt+0x120/+0x600 - a follow/steer routine). Treat +0x230..+0x26C of that subobject as *steering/attachment rows*, not animation phase.
- **KEY REMAINING GAP:** no per-frame ANIM values were found on the crowd ctl at all; the walk-only churn we see at ctl+0x2F00 region is steering/row data. The crowd anim state must live on a CHILD object (children list was never included in the walk-diff because the vt-range filter `0x00400000..0x00700000` excluded crowd child vts `0x026Exxxx`). New tool `child_walk_diff.py` diffs ent+ctl+ALL children (0x1000 each) across walk/stand of one NPC.
- **STATE:** game relaunched clean (pid 29540) and parked at the main menu scene (only the player entity exists; position (1.3,7.1,1.3)). Waiting for the world to load before re-running the child-level walk diff.
- Tools: watch-writer-addr.ps1 (v3), TestWatch.cs/exe (sandbox), child_walk_diff.py.

## 2026-10-09 (night #3, live) - child-level walk diff: the walk state is on CHILDREN (not the ctl)
- First full child-level diff of a verified walking crowd NPC (runner, 2.2 m/s, ch=20 cnt=23): ent (0x400) + ctl (0x3800) + ALL 8 valid children (0x1000 each), 14s walk vs 10s stand, SAME npc. Output: bf-coop/child_walk_diff.txt (write tool: child_walk_diff.py).
- RESULT: 13501 changed offsets walking / 5767 standing. The **walk-only** set (changed while walking, ~zero while standing) is concentrated on children, NOT the ctl:
  - **c14 vt=0x01E41E58** (own bytes): +0x0D0..0x0D5, +0x150..0x155, **+0x2C4 (byte counter, +~6.3 per 100 ms = ~63/s, stops when standing)**.
  - **c15 vt=0x01E410F0** (own bytes): +0x0F8..0x0FB, +0x118..0x119, +0x204..0x215, +0x490..+0x4B9, etc. (c14/c15 allocations are adjacent: c15 = c14 + 0x350, so bytes past c14+0x350 in the c14 window duplicate c15's low bytes — the "identical sequences at c14+0x448 vs c15+0xF8" are the SAME memory).
  - **c18 vt=0x01E5CD10**: +0x214/+0x215 x95 walk-only.
  - ent: +0x40..0x49 (transform), +0x74..0x76.
- **ctl (vt 0x026E34D8): NO walk-only changers at all this run** — every ctl offset that churns (e.g., +0x2C4/+0x2C0/+0x364/+0x11D8..+0x12BA, the ~63/s timer family) also churns while standing. The ctl+0x2C4 counter carries the same values as c14+0x2C4 (a shared tick copied into several objects).
- Class notes (from the earlier static survey): 0x01E41E58 = large multi-subsystem character component (ctor FUN_004498f0 / teardown part_00003.c:20012); 0x01E410F0 = smaller sibling (part_00002.c:4315); 0x01E5CD10 = 8-byte-entry array component; 0x01E61938 = location/pose; 0x01E47480 = 0xc-byte-entry container; 0x01E6CC50 = render/display-list; 0x026EE050 = 4-handler controller.
- **STATE:** the game process (29540) hung/was unresponsive during post-run scanning and was killed -> relaunched (pid 26136); v3 live watchpoint capture is still PENDING (not yet used on the live game). Scan throttling: prefer 0.15-0.2 s intervals and avoid repeated full-address-space sweeps.
- **NEXT:** with a verified walker in world: locate its child vt=0x01E41E58 and arm the v3 write watchpoint on child+0x2C4 (or +0xD0) -> the writer is the crowd locomotion/anim update function = the drive channel we need. Tool ready: find_walker_children.py.
