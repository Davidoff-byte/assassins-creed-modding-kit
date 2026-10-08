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
  to the proven local install) + ini prefilled for B (RemoteIp1..4 = [A's Radmin IP],
  LocalPort 27801, RemotePort 27800, ClientId 2) + ASCII README (exact expected log lines, peer/fresh
  semantics, troubleshooting, firewall notes). v0.1 moved to dist/archive/. A-side quick sheet:
  dist/README-FOR-A.txt. New tool: tools/set-remote-ip.ps1 (-Ip [-LocalPort -RemotePort -ClientId]).
- Log semantics documented (source-verified): PlayerTransform "peer=" prints the STICKY struct flag
  (1 forever after the first packet of the session; a config reload does NOT reset it), "fresh=" is the
  real liveness (peer timeout 2 s; ghost body stops being driven when stale, stays assigned). Guides
  say: fresh=1 is the live indicator. Future polish: make the log print liveness directly.
- fake_peer_send.ps1 defaults updated to the new port pair (27800/27801).

## 2026-10-06 17:46 — *** MILESTONE: two-machine co-op ghost LIVE over Radmin ***
- First real two-machine run (user A [A's Radmin IP] <-> "Suhiro" B [B's Radmin IP], ~105 ms ping, ping 3/3).
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
  guest 'PlayerB' vs A's [Radmin IP]. A-side deployed + configured (RemoteIp pending his IP).

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
