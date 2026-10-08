# AC Rogue — Combat & Stealth code research (ACC.exe)

Reverse-engineered with Ghidra 12.1.4. Image base `0x140000000`.
Data: `ghidra_scripts\acc_functions.txt` (all functions), `acc_strings.txt` (all strings),
`acc_string_refs.txt` (string → referencing function). Decompiles in `decomp_set.txt`, `callers_set.txt`.
Project: `C:\Users\Administrator\ghidra-acc\ACC.Rogue`. MD5 `a323729f3799a808c8148b695e1e23b8`.

> All addresses are RVAs from the image base. `FUN_xxxx` = Ghidra's auto-name.

---

## 0. Player object model (what the code assumes)

Most player functions take `param_1` = a **player/actor wrapper**, and dereference:

| Expression | Meaning (inferred) |
|---|---|
| `*param_1` (i.e. `param_1[0]`) | the player **entity** |
| `*(*param_1 + 0x1e8)` | an entity sub-object; `+8` is the **skeleton/scene node** (used for world position) |
| `*(*param_1 + 0x1f0)` | **component manager** (big vtable, `+0x2f8`, `+0x400`, `+0x658`) |
| `param_1[0x3c]` / `param_1[0x3e]` | shared-ptr handles (targeting) |
| `param_1[0x43]` = `+0x218` | **fight weapon type** (Sword=1 … DualWield=7 …) |
| `param_1[0x148]` | anim/state index (8 = some grab state) |
| `(longlong)param_1 + 0xaf8` | **current combat action id** (see §2) |
| `(longlong)param_1 + 0xa3c/0xa3e/0xa37` | grab/counter flags |
| `param_1[0x244]`=+0x1220 | grab/counter scratch |
| `param_1 + 0x108` | status block; `FUN_14132d010(+0x108)` = fallen/stunned |
| `FUN_1400c3be0()` | get local player slot / controlled character |
| `FUN_1400d85e0(entity)` → vtable+0x90 | get a sub-component by id (0, 0x10, 0x11, 0x1e…) |

Weapon/state on the player entity is reached via `FUN_1400d85e0(ent)` then vtable calls.

---

## 1. Weapon type & moveset chain (for the one-handed-sword feature)

Enums recovered:

**WeaponType** (`FUN_1414a63c0`, the on-entity field): 0 Unarmed, 1 Medium, 2 Small, 3 Heavy, 4 Long,
5 Musket, 6 Blunt, **7/8 Dual Wield**, 9 Machete, 0xb Hidden Blade, 0xc Medium Blunt, 0xd Crossbow,
0xe/0x1a holster pistols, 0xf Bow, 0x10 Throwing dagger, 0x11 Arrow, 0x12-0x15 blowpipe darts,
0x16 Rock, 0x17 Gun, 0x18 AppleOfEden, 0x19 RopeDart, 0x1b Explosive, 0x1c LeftHandKnife,
0x1e/0x1f up-holster pistols, 0x22-0x28 air-rifle ammo, 0x2a MaxType.

**Weapon class** (`FUN_1410234b0`): 0 Unarmed, 1 AssassinBlade, 2 **Sword**, 3 Heavy, 4 Dagger, 5 Long,
6 CrossBow, 7 Musket, 8 Blunt, 9 **DualWield**, 10 Machete, 0xb SwivelGun.

**Class from WeaponType** (`FUN_1414a6300`): 1→2, 2→4, 3→3, 4→5, 5→7, 6→8, **7|8→9**, 9→10, 0xd→6, 0x20→0xb.

**Fight weapon type from class** (`FUN_1414a6270`): 1→0xb, **2→1 (Sword)**, 3→3, 4→2, 5→4, 6→0xd,
7→5, 8→6, **9→7 (DualWield)**, 10→9, 0xb→0x20.

Chain: `entity WeaponType` → `FUN_1417153e0` (class getter) → `FUN_1414a6270` (fight type) →
`FUN_1420f3d20` (apply combat set) → stored at `player+0x218`.

Hard facts learned by testing:
- Editing the entity `.data` `WeaponType` (7→1) had **no effect**.
- Overriding the class getter `FUN_1417153e0` return (9→2) at runtime had **no effect** on the moveset;
  the getter is called 100+/s but feeds HUD/prompts.
- `FUN_1420f3d20` is on the **hot combat path** (a CE breakpoint freezes the game on attack; a plugin
  entry-hook destabilised startup). The value it is called with was observed as `type=1, slot=1`.

Player weapon setup function: `FUN_14185e990` (sets action id 0x26, computes
`iVar3 = FUN_1414a6270(FUN_1417153e0(*param_1))`, calls `FUN_1420f3d20(player, iVar3, 1)`, stores at
`player+0x218`, and re-applies via `FUN_141807200` when flag `+0x21e` set).

**Remaining unknown:** where the *stored* `player+0x218` is consumed to pick the animation action set —
i.e. why overriding the compute paths doesn't change the moveset. Next: trace readers of `player+0x218`
and the vtable `FUN_1420f3d20` uses (`FUN_14132d410`, component vtable `+0x400`).

---

## 2. Player combat state machine

`player+0xaf8` holds a **combat action id**. Handlers set it and often emit a telemetry event:

| Function | sets +0xaf8 | telemetry name | role |
|---|---|---|---|
| `FUN_141845e60` | 0x13 | **"Parry"** | parry action (also sets `+0x1156`=1) |
| `FUN_14185cc40` | 0x19 | **"CounterFail"** | failed counter (uses `FUN_1417f9e50` + table `DAT_143321280`) |
| `FUN_141849470` | 0x3f | **"GrabCountered"** | grabbed/countered |
| `FUN_14185e990` | 0x26 | – | weapon setup / equip refresh |

Telemetry dispatcher: `FUN_141047ed0(name, entity, target)` builds `PlayerAction` payload and posts to
channel `DAT_1432c9c50`. (Analytics only — not gameplay.)

Combo/state helper `FUN_1417f9e50(class, actionId) -> small code`:
- `class 7|8 -> 8|9`, `0xb -> 6|7`, `0 -> 4|5`, `FUN_14170bb40(class) -> 2|3`, else `0|1`
  depending on `actionId ∈ {5,0x21..0x28,0xf,3,4,6}`.
Used by fight-action functions `FUN_14180fc60`, `FUN_14180fdf0`, `FUN_14180ff20`, `FUN_141810040`,
`FUN_141810230`, `FUN_14182ad10`, `FUN_1418417a0`, `FUN_14185a9c0`, `FUN_14185cc40`, `FUN_14185d260`,
`FUN_141860e10`, `FUN_141868cb0`.

Fight manager: `FUN_1420f1850` returns the manager; `FUN_1417f7010` resets fields `+0x1044..+0x1062`
(sets `+0x105c = 0x2a`).

**Combat setting types** (a reflection cluster of strings at `0x142a2a4b0..`):
`FightStrategyRole, DodgeAttackFightAction, StepAttackFightAction, GrabFromBehindFightAction,
OpenDefenseAttackFightAction, ComboAttackFightAction, AttackFightAction, FightAction,
TransitionsHackSettings, VariationHackSettings, RangeAccuracyModifier, CounterWindowSettings,
FightPacingSetting, SpecialAttackSettings, FightSettings, FightManagerData, FightManagerDifficultyData,
RecyclePoint, FightManager, GrenadeVolley, GrenadeVolleyManager, FightEvent, FightEventManager,
FireLineManager, FireLineNPCsVsNPCs`.

`CounterWindowSettings` has **no direct code xref** (it's a reflected type); its instance data is what an
action-map / settings resource would serialise. The per-action timing is probably enforced by the
`Fight*ActionMap` graph (data in `49_-_Game Bootstrap Settings.data`, e.g. `FightCounterKillActionMap`,
`FightParryDeflectActionMap`, `FightCounterPoseActionMap`).

**Combat state-name enums (telemetry/UI):**
`FUN_141022f50` FightState: Invalid / Not in fight / Normal / Stunned / Fallen.
`FUN_141021cf0` Conflict: Anonymous / Detected / In conflict / In fight.
`FUN_1410231c0` Movement: None / Slow Walk / Walk / Fast Walk / Jog / Sprint / Climb.
`FUN_141022b90` Tool: Nothing / Pistols / Rope Dart / Smoke Bomb / Throwing knife / Throw Money /
Treasure Map / Air-Rifle variants.
`FUN_141021ef0` Targeting: No / Free Aiming / Locked Target.
`FUN_141021b70` TerrainType: Ground / Rooftop / InTree / Cart / Water.
`FUN_141021a30` small state: N/A / Fight / Detected / Mission.

**Combat setting entry point:** `FUN_14102b180` = `InvItem_*` category names (inventory).

---

## 3. AI architecture (combat AI + perception)

**AI global object** built by `FUN_14010ee00`; registers a named update pipeline:
- `Ai::AIGlobalUpdateStep1` → `FUN_140106c80`
- `Ai::UpdatePathManager` (PathManager) → `FUN_1404f6220`
- `Ai::UpdatePerceptionManager` (**PerceptionManager**, object at `AIGlobal+0xb1*8`)
- `Ai::AIGlobalUpdateStep2`, `Ai::AIGlobalUpdateStep3`
- `Ai::CoordinatorUpdate` (multi/single-threaded), `CoordinatorManagerUpdate`
- after-update begin/end nodes.

NPC combat AI is a **behaviour graph** built by `FUN_1417d1ff0` with named condition nodes:
`CanTakeAction`, `TakeAction`, `IsEnemyOpenDefenseAttacking`, `EnemyAttack`, `IsEnemyOutOfRange`,
`TakeNewAction`, `IsArmed`, `NPC Attack`, `IsEnemyAttackIncoming`, `IsEnemyFocusedOnMe`,
`Done Node : Do Nothing`, `DT Paranoid`.

---

## 4. Stealth: detection, stalking/crouch, hide, vanish

### 4.1 Detection / conflict (the "cone")
- `FUN_141435370(obj)` → `FUN_141434f60(*(obj+0x30))` : **is-detected** predicate.
- `FUN_14132ddc0(session)` : **in conflict / in fight** (reads `+0xe80`, `+0xea8`).
- `FUN_1414351b0(obj)` : **in fight** bitfield test.
- `FUN_14132d010(status)` : stunned/fallen.
- `FUN_141353260(entity, threshold)` : **range/visibility compare** (compares a computed distance to a
  threshold constant) — used by terrain and by the Detection Loop.
- `FUN_141bf67e0` : triggers AI script `"Detection Loop Start"` / `"Detection Loop Start Rooftop"`.
- `FUN_141a2e0e0` : `"CSRVDetectionPersistence"` — detection persistence/investigation handoff.
- HUD detection: `FUN_1411ab240`, `FUN_1411cb970` build `detection_blink`, `los_%s` / `nolos_%s`,
  `addConflictIcon` (icon + timer per guard).
- Perception data resources: `PerceptionSettings`, `DetectionSettings` (AnvilToolkit-editable).

### 4.2 Stance / crouch / stalking
`FUN_141022070(out, entity)` → **Profile/stance name**, decided in this order:
1. a sub-object vtable `+0x5f0` → **"Stalking"**
2. `FUN_141799430(sub, 1)` → **"Blended"**
3. global player state code (`FUN_1401a5590(stateMachine, 1)`):
   `3` Ghost Mode · `4/9/10/0x11` Low/High Profile (split by `FUN_141259390`→"Low Profile"/"High Profile")
   · `8/0x1e/0x1f/0x27/0x29` High Profile · `0x14` **Haystack** · `0x15` Hiding Door · `0x2e` Cover.
- `FUN_141008d30()` returns that state code (default 2). `FUN_1401a5590` reads `stateMachine + 0x58*idx + 0x30`
  → vtable+0x48 → `*(result+8)`.
- Crouch/stalking engine names (events/types): `ActivityCrouch` @0x142a21e50, `ActivityStealth` @0x142a61880,
  `ActionBlockCrouching` @0x142a10048, `RestrictCrouchingEvent` @0x1429f87b0,
  `PlayerStalkingCondition` @0x142a95b80, `PlayerVanishedConition` @0x142a95b28,
  `StalkingZoneComponent` @0x142a3e950, `StalkerHidespotComponent`.

### 4.3 Blend / vanish
- `FUN_141020fc0` maps a small enum → `blend / death / desynch / escape / exit / hide / kill_all`.
- `FUN_141ebc6e0` : `"[Blend Action] Toggle Player Vanish"` (called from `FUN_141ec4a50`).
- `FUN_141e71360` : player vanish state (called from `FUN_141ec7550`).
- `FUN_14029f1e0` : manager factory/pair for `VanishingManager`, `StalkerManager`, `EagleVisionManager`.
- `FUN_141e6bb10(entity, out)` : writes the entity's weapon class (used by the chain and by vanish code).

### 4.4 Hide spots
`CLSearchHideSpot*` family: `FUN_141f677c0`, `FUN_141f67d00` (`TossGrenadesAtHideSpot`),
`FUN_141f68450` (`ParanoNotoriousSearchFailed`), `FUN_141f689d0`/`FUN_141f6a880` (`SearchAround`),
`FUN_141f68b40`, `FUN_141f77cd0`, `FUN_141f784e0`, `FUN_141f843d0`.

---

## 5. Candidate implementation levers (per feature)

- **One-handed Shay sword:** trace readers of `player+0x218` and the component vtable used by
  `FUN_1420f3d20` (`+0x400`). The apply function is hot → needs an inline/trampoline hook, not a
  breakpoint; must not run before the player exists.
- **Short counter window / block-on-miss:** the parry path is `FUN_141845e60` (state 0x13) fed by
  `FUN_1417f9e50` and the `Fight*ActionMap` graph. Either retune the ActionMap data (CounterWindowSettings
  instance) or intervene at the parry decision.
- **Manual crouch:** set the stalking sub-state that `FUN_141022070` step 1 / `FUN_141799430(sub,1)`
  reads, plus neutralise `RestrictCrouchingEvent`; the crouch pose/anim (`ActivityCrouch`,
  `CAS_Sneak_Walk_02`) already exists. Input must be synthesised (no crouch action exists).
- **Reduce detection cone/remove invisibility:** retune `PerceptionSettings`/`DetectionSettings` and the
  stalker `TagRules` data, and/or hook `FUN_14132ddc0` / `FUN_141435370` (detected predicates).

## 6. Still unknown / next steps
1. Reader(s) of `player+0x218` and the animation action-set selector.
2. The exact counter-timing arithmetic (find the `CounterWindowSettings` instance / its data hash).
3. Where the player state code (`FUN_1401a5590`) is set to stalking/crouch.
4. Input plumbing: map a key to `ActivityCrouch`/`ActivityStealth`.
