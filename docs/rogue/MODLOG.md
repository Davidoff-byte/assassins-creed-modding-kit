# MODLOG — AC Rogue gameplay mod

> **Workspace refs (root `REFERENCES.md`, use every session):** `trevaintdead/ai-game-modding-guides`
> (rules + AGENTS/MODLOG/STATUS templates), `rehan-remade/universal-modder` (`um`/skills/KB),
> `NationalSecurityAgency/ghidra` + `akiselev/ghidra-cli`, `smileybaal/gamedb` (`gamedb-cli` skill),
> `morluto/rea` (RE methodology / `reverse-engineer-anything` skill; Windows Ghidra currently
> unavailable), `bevyengine/bevy`, `fmhy/FMHY` (never for piracy/DRM/anti-cheat).
> **Hygiene:** the `*_decomp*.txt` / `*.txt` dumps in this folder are decompiled-game output — keep
> them out of anything shipped and run `um publish check` before sharing (no game files).


Game: Assassin's Creed Rogue (Steam), `D:\\SteamLibrary\\steamapps\\common\\Assassin's Creed Rogue`
Engine: AnvilNext, native x64 (`ACC.exe`, note: patched by "AC Rogue Revived").
Anti-cheat: none. Loader: ASI loader (`dinput8.dll`) + plugins (`AC.Rogue.PatchFix.asi`).
Saves + config: `C:\\Users\\Administrator\\Documents\\Assassin's Creed Rogue`

## Requested features
1. Combat: short counter window -> insta-kill; miss -> normal block; harder than base.
2. Shay's default sword: single sword, one-handed (pickup-sword) moveset.
3. Stealth: manual crouch button anywhere; remove bush invisibility; crouch reduces guard detection cone.
4. All enemies musket infantry (believed already from "AC Rogue Revived" patched exe).

## Route
Native hooks via the ASI plugin framework `playday3008/AC.PatchFix` (SafetyHook + Hooking.Patterns).
Reused their hook registry, pattern scanner, diagnostics. Built with MSVC BuildTools 2022 + CMake.

## Lab
- Saves backed up: `~/.universal-modder/backups/rogue-saves/20261003-181814.zip`
- DataPC.forge currently re-packed (131MB -> 145MB) from earlier entity experiment.
- Entity experiments (no in-game effect): set `WeaponType` 7->1 (primary) and 8->1 (secondary) in
  `ACC_W_P_ShayDefaultSword_*` `.Entity`. Backups: `.Entity.bak`.

## Findings
- Framework builds with MSVC after 4 patches: `flat_map`->`map`, `consteval`->`constexpr`,
  `/EHa`, SEH-guard thunk refactor. Artifact: `build-msvc/bin/Release/AC.Rogue.PatchFix.asi`.
- Dual-wield is NOT driven by the weapon entity `WeaponType` (verified: no in-game change).
  Moveset selection is elsewhere (player/character action-set / buildtable layer).
- Engine strings confirm crouch machinery exists: `ActivityCrouch`, `ActionBlockCrouching`,
  `RestrictCrouchingEvent`, `PlayerStalkingCondition`, `StalkingZoneComponent`, `StalkerManager`,
  `[Blend Action] Toggle Player Vanish`. Crouch anims/sets: `cas_sneak_*`, `CAS_Sneak_Walk_02`.
- Invisibility + detection are data: `PerceptionSettings`, `DetectionSettings`, stalker `TagRules`,
  `Stalking Crouch Book.GraphRuleBook`.
- No crouch input action exists in `DefaultBindings.map` -> a crouch button needs a code hook.

## Static RE (Ghidra 12.1.4, ACC.exe MD5 a323729f3799a808c8148b695e1e23b8)
Project: `C:\Users\Administrator\ghidra-acc\ACC.Rogue`. Scripts in `C:\Users\Administrator\ghidra_scripts`.
Run: `-process ACC.exe -noanalysis -postScript <script>`, heap 8G (2G defaults OOM).

### Function map (RVA base 0x140000000)
- `FUN_1410234b0(int)` -> weapon-class **name** string. Values: 0 Unarmed, 1 AssassinBlade, 2 **Sword**,
  3 Heavy, 4 Dagger, 5 Long, 6 CrossBow, 7 Musket, 8 Blunt, 9 **DualWield**, 10 Machete, 0xB SwivelGun.
- `FUN_1417153e0(entity)` -> weapon-class **int** for an entity (feeds FUN_1410234b0).
  Callers: 13 (HUD prompts + gameplay). `FUN_1414a6300(FUN_141339ac0(ent+0x1e8->+8))` is the item->class path.
- `FUN_141022070(out, entity)` -> player **stance** name: Stalking / Blended / Ghost Mode /
  Low/High Profile / Low Profile / High Profile / Haystack / Hiding Door / Cover / Unknown.
- `FUN_14102e960` -> contextual-prompt name (Attack/Parry/PerfectParry/Dodge/Loot/...); calls
  FUN_1417153e0 + FUN_1410234b0. HUD-side, not combat logic.
- `FUN_141ebc6e0` refs `[Blend Action] Toggle Player Vanish` (player vanish/blend toggling).
- `FUN_14029f1e0` refs `VanishingManager` + `StalkerManager` (manager factory/registry).
- `FUN_1416e1b60` refs `Stalking Assassination`, `Counter Kill`, `Counter Kill Tool`.
- `FUN_1417bf580` / `FUN_1417cc380` -> fight-strategy counter tables (HTM_CounterKill/Tool/Hurt/Throw).
- `FUN_14185cc40` -> `CounterFail`; `FUN_141849470` -> `GrabCountered`; `FUN_1417d5c00` -> `HasCounterGrabbed`.
- Event/type name strings (data, resolved via engine reflection): `ActionBlockCrouching` @142a10048,
  `ActivityCrouch` @142a21e50, `RestrictCrouchingEvent` @1429f87b0, `StalkingZoneComponent` @142a3e950,
  `PlayerStalkingCondition` @142a95b80, `PlayerVanishedConition` @142a95b28, `CounterWindowSettings` @142a2a5c0,
  `StalkerManager` @142395838.

### Consequence for each feature
- **One-handed Shay sword**: best lever is `FUN_1417153e0` remap 9(DualWield)->2(Sword) for the player, or
  find the item->class source `FUN_1414a6300`/`FUN_141339ac0`. Data `WeaponType` was a dead end.
- **Counter window**: `CounterWindowSettings` is a code-side type; no data file found containing it ->
  hook the counter/parry path (`FUN_1417bf580`/`FUN_1417cc380`/`FUN_14185cc40`).
- **Crouch**: `PlayerStalkingCondition` / `RestrictCrouchingEvent` / `FUN_141ebc6e0` are the hooks; the
  crouch **input** still does not exist and must be synthesised.

### Framework constraint
`AC.PatchFix` core exposes only **MidHook** (`safetyhook::MidHook`) + byte writes. Return-value overrides and
call hooks need either a MidHook on the function's `ret` (adjust `regs.rax`) or a new `InlineHook` wrapper
(SafetyHook already a dependency).

## Final status (stopped by choice)
- **Left in place:** our MSVC-built `AC.Rogue.PatchFix.asi` (v3.3.1, master) in `plugins\`, working.
  It ships the stock QoL hooks plus a **no-op** `OneHandedSword` hook (class getter remap; harmless).
  Stock ASI backed up at `plugins\_backup_stock\`.
- Entity `WeaponType` edits (7->1, 8->1) remain in `ACC_W_P_ShayDefaultSword_*` with `.bak` files; no gameplay effect.
- `DataPC.forge` was ATK-repacked (131->145 MB); behaviourally identical.
- Saves untouched. CE debugger closed, CE autorun script removed.

## Hard-won engine facts (ACC.exe, base 0x140000000)
- WeaponType enum (`FUN_1414a63c0`): 0 Unarmed, 1 Medium, 2 Small, 3 Heavy, 4 Long, 5 Musket, 6 Blunt,
  7/8 Dual Wield, 9 Machete, 0xb Hidden Blade, 0xd Crossbow, 0x1e/0x1f holster pistols, 0x2a MaxType.
- Class mapping (`FUN_1414a6300`): 1->2, 2->4, 3->3, 4->5, 5->7, 6->8, 7|8->9, 9->10, 0xd->6, 0x20->0xb.
- Class names (`FUN_1410234b0`): 0 Unarmed, 1 AssassinBlade, 2 Sword, 3 Heavy, 4 Dagger, 5 Long, 6 CrossBow,
  7 Musket, 8 Blunt, 9 DualWield, 10 Machete, 0xb SwivelGun.
- Fight-type mapping (`FUN_1414a6270`): class 2->type 1 (Sword), class 9->type 7 (DualWield).
- The chain: entity WeaponType -> FUN_1417153e0 (class) -> FUN_1414a6270 (fight type) ->
  FUN_1420f3d20 (applies combat set; player field +0x218). FUN_1420f3d20 is on the **hot combat path**
  (CE breakpoint freezes the game the instant you attack) and a plugin MidHook on its entry destabilised
  startup -> not safely instrumentable in a blind loop.
- Stance names (`FUN_141022070`): Stalking / Blended / Ghost Mode / Low|High Profile / Haystack /
  Hiding Door / Cover. Stalking/crouch events: ActivityCrouch, ActionBlockCrouching, RestrictCrouchingEvent,
  PlayerStalkingCondition; `FUN_141ebc6e0` = [Blend Action] Toggle Player Vanish.
- Counter: `FUN_14102e960` (PerfectParry/Parry prompt namer), fight strategies FUN_1417bf580 /
  FUN_1417cc380 (HTM_CounterKill/Tool/Hurt/Throw), CounterFail FUN_14185cc40.

## Big research session (combat & stealth) — see COMBAT_STEALTH_RESEARCH.md
Full map written to `C:\Users\Administrator\Documents\Default Project\ac-rogue\COMBAT_STEALTH_RESEARCH.md`.
Index files: `ghidra_scripts\acc_functions.txt`, `acc_strings.txt`, `acc_string_refs.txt`.
Reusable Ghidra scripts: `DecompileList.java` (reads `targets.txt`), `CallersList.java` (reads
`callers_targets.txt`), `DumpAll.java`, `FindStrings.java`, `GetBytes.java`.

Highlights:
- Weapon chain: WeaponType -> class -> fight-type -> `FUN_1420f3d20` -> player+0x218. Getter override =
  no effect (HUD-only); apply fn is hot.
- Player combat state = `player+0xaf8` action ids; Parry `FUN_141845e60`, CounterFail `FUN_14185cc40`,
  GrabCountered `FUN_141849470`; combat is dispatched through **ActionMap data** (`Fight*ActionMap`,
  `CounterWindowSettings` type) -> counter window is likely data-editable.
- AI global `FUN_14010ee00` registers the pipeline incl. PerceptionManager; NPC combat AI is a behaviour
  graph (`FUN_1417d1ff0`).
- Stealth: stance `FUN_141022070` (Stalking/Blended/Cover/Haystack...), player state code
  `FUN_1401a5590`, detection predicates `FUN_141435370`/`FUN_14132ddc0`/`FUN_1414351b0`,
  vanish `FUN_141ebc6e0`, hide-spot `CLSearchHideSpot*`.
- Crouch/stalking engine events exist (`ActivityCrouch`, `ActionBlockCrouching`,
  `RestrictCrouchingEvent`) but there is no crouch input action.

Remaining unknowns: reader of `player+0x218` / animation action-set selector; exact counter-window
arithmetic; where the player state is set to stalking; input plumbing.

---

## Session 2026-10-04 (continued) — attacking the "data edits do nothing" blocker

State at start: game `ACC.exe` (PID was live) + AnvilToolkit 1.3.6 open; deployed plugin = MSVC build
with working `OneHandedSword` (fight type 7→1) hooks. Data edits (Shay Secondary `Visual.Active=0`,
`CHR_W_Dagger_Axe.Material MaterialDisabled=1`, `FightSettings TimeCounterInputIsValid 1.5→0.2`,
`CounterOpenWindowRatio 0.7→0.4`) all present but reported ineffective.

### What was verified this session
- **Repack chain timestamps are correct**: `.Entity` edited 16:22, `256_*.data` rebuilt 16:39;
  `FightSettings` edited 16:49:39, `49_*.data` rebuilt 16:50:50, `DataPC.forge` written 16:50:52 →
  every repack happened *after* its source edit. So the edits are physically in the forge.
- **No higher-priority override**: `findstr` over `DataPC_extra.forge` (427 MB) and
  `DataPC_extra_chr.forge` (1.7 GB) finds no `ShayDefaultSword` / `Dagger_Axe` / `FightSettings` /
  `LocalizationPackage_English` entries. Weapons + `Game Bootstrap Settings` exist **only** in
  `DataPC.forge`. (`DataPC_patch.forge` = 33 entries, menus + `LocalizationPackage_Russian` only.)
- **Stock backups**: `D:\...\Assassin's Creed Rogue\Backups\` holds stock `DataPC.forge` (139 MB),
  `DataPC_extra_chr.forge`, `DataPC_patch.forge`. Current `DataPC.forge` = 145 MB (repacked).
- **ATK config** (`AnvilToolkit.dll.config`): `IgnoredExtensions = dependency;bak;dds;obj;glb;xml;ignored`
  → `.Entity`/`.Material`/`.FightSettings` **are** packed; `EnableCompression=True`;
  `CompileXMLWhenRepacking=False`.

### New tooling built (in this folder)
- `forge.py` — AnvilNext `scimitar` **forge reader** (version 27, AC Rogue). Parses the 0x41A header +
  FileSet table + 0xC0-byte name records. Validated: 330 entries, and e.g.
  `ACC_W_P_ShayDefaultSword_Secondary` idx=256 off=0x7658000 size=458780 id=0x11043B9A6F, current
  blob size 458780 vs stock 460854. **Forge entries store their `.data` blob raw** (no forge-level
  compression) → a forge repacker is straightforward.
- `container.py` — dumps the `.data` container header. Container = 8-byte prefix +
  `CompressedFileData` magic `33 AA FB 57 99 FA 04 10`, `Version=1 Algorithm=0` (LZO-family), 32768-byte
  blocks, two chunks (metadata + payload). Editing inside requires the LZO codec; AC Rogue uses
  `lz o.dll` from ATK's `Libs\`.
- `probe.py` / `probe2.py` — extract/compare forge blobs; list a forge's entries.

### DECISIVE TEST — pipeline WORKS (forge IS read)
Ran a controlled A/B with the new in-place forge patcher (`forge_patch.py`), no ATK GUI:
- Registry says game locale = **English** (`HKCU\Software\Ubisoft\Assassin's Creed Rogue\language`).
- **Test:** replaced the ACTIVE `LocalizationPackage_English` blob (826936 B) in `DataPC.forge` with the
  smaller `LocalizationPackage_Spanish(Spain)` blob (817476 B) in place → **game hung on the loading
  screen** (it reacted to the change).
- **Control:** replaced the UNUSED `LocalizationPackage_Finnish` (684737 B) with
  `LocalizationPackage_Norwegian` (655488 B) → **game loaded normally into gameplay**.
- ⇒ If the game ignored `DataPC.forge`, both would have loaded identically. It hung only when the
  *active* package changed ⇒ **the modded `DataPC.forge` IS loaded.** The in-place size-changing patch
  mechanics are valid (control proved it).
- Corollary: the previous session's data edits were simply the **wrong targets/fields**; the forge
  repack was never broken. (The language-swap hang is a *content* mismatch inside the active package,
  not a repack defect — don't swap whole packages; small same-language edits are the safe unit.)

State after test: `Backups\DataPC.forge` = stock; `forge_backups\DataPC.forge.modded_20261004` = current
modded pre-test forge; the live forge currently has the inert Finnish control swap (harmless, locale is
English) — restore from the backup before shipping. Game left running (ACC.exe, ownership of PID was
killed/relaunched a few times). Saves backed up: `~/.universal-modder/backups/rogue-saves-pretest/`.

### The edits ARE loaded — so the fields are just the wrong lever
Extended `forge.py`/`memscan.ps1` and scanned the running game (ReadProcessMemory):
- `bin_diff.py` shows the `.FightSettings` binary really does contain the edits:
  `0x0371 00→01` (AllNPCsFightCowards), `0x05D0 0x3F333333(0.7)→0x3ECCCCCD(0.4)` (CounterOpenWindowRatio),
  `0x062A 0x3FC00000(1.5)→0x3E4CCCCD(0.2)` (TimeCounterInputIsValid).
- Memory scan of ACC.exe: the ASCII `"Basic Setting"` is present (1 hit), and the **edited** float run
  `0.7,0.75,0.4,0.75,0.35` is present while the **stock** run `0.7,0.75,0.7,0.75,0.35` is absent.
  ⇒ the game loaded our edited FightSettings values. The pipeline and the target file are correct.
- Therefore `TimeCounterInputIsValid` / `CounterOpenWindowRatio` / `AllNPCsFightCowards` are live but do
  **not** produce the counter-window behavior the user asked for. The lever is elsewhere (code counter
  decision, animation action-map timing, or another reflected setting).

### `.data` container codec (NEW — `anvil.py`) — the big unlock
Reverse-engineered AC Rogue's `.data` container from **ATK 1.3.6's own code** (decompiled with
`ilspycmd`; ATK is the same tool/version used for Rogue). Rogue = `Game.Rogue → (Version 1,
Algorithm 0 = LZO1X, BlockSize 32768)`, TOC mode.

Container layout:
```
[int32 filterTableSize][filterTable bytes]
[CompressedFileData meta][CompressedFileData files]
CompressedFileData: u64 magic 0x1004FA9957FBAA33
                    i16 Version(1), u8 Algorithm(0), u32 (TOC<<31 | BlockSize=32768)
                    u16 blockCount, blockCount*(u16 uncompressed, u16 compressed)
                    per block: u32 adler32(over COMPRESSED bytes, LZO seed 0) + bytes
files block = records: u32 typeId | i32 len | i32 nameLen | name | FileHeader | payload[len]
FileHeader = 1 byte, or (if byte==1) 12*count+8 bytes
```
`anvil.py` reads any Rogue `.data` (uses the generic `lzo.dll` codec; no AC1 game data involved).
**Validated:** `LocalizationPackage_English` (1 resource, 984912 B) and
`ACC_W_P_ShayDefaultSword_Secondary.data` → 9 resources (Entity, 2× WeaponSoundSet, Mesh, Material,
TextureSet, 3× TextureMap). Still TODO: a writer (repack) to modify a resource and rebuild the
container, then push the new blob into the forge with `forge_patch.py`.

### Dagger finding: the weapon entity/material is the PICKUP template, not the held mesh
`256_-_ACC_W_P_ShayDefaultSword_Secondary.Entity` is an Entity with `EntityDescriptor.
IsPickableByPlayer=True`, `IsSpawned=False` — a **world weapon pickup template**. Its components are
`WeaponComponent` + `Visual` + `VisualTrailComponent` + sound + `RigidBodyComponent`. Setting
`Visual.Active=0` (byte 0xE4) and `Material MaterialDisabled=1` (byte 0x49) does nothing to the dagger
Shay holds. ⇒ the **held** off-hand weapon mesh comes from the **player character buildtable**
(`CHR_P_Shay_*`, in `DataPC_extra_chr.forge`) or an equipment/attachment system, not this entity.
Note: `3574_-_CHR_P_Shay_Templar_Default.data` (31 MB) is a **different container type** (`anvil.py`
doesn't parse it yet — header starts `6C 02 00 00 00 00 38 00 …`, a flat hash table, not the simple
filterTable+2×CFD layout).

### 2026-10-04 (cont.2) — ReShade was crashing the game; dagger resource = negative
- **The "game won't launch" was ReShade (`dxgi.dll`)**, not the forge. ACC.exe crashed at
  `D3D11CreateDeviceAndSwapChain` (ntdll 0xc0000005, dumps in `%LOCALAPPDATA%\CrashDumps`). Renamed
  `dxgi.dll` → `dxgi.dll.off` and the game launches normally. **Restore/reset ReShade before shipping.**
- **Forge "append + repoint entry" works** (`forge_append.py`): the game loaded the grown forge. The
  earlier "appended forge hangs" was actually ReShade.
- **Dagger test (decisive, but negative):** put `ACC_W_P_ShayDefaultSword_Primary`'s data into the
  `ACC_W_P_ShayDefaultSword_Secondary` slot → the off-hand still looked like a **dagger**. So that
  resource is **not** the held off-hand mesh. Dagger is parked.
- `anvil.py` also parses the 46 MB **`Game Bootstrap Settings.data`** (20,988 resources) — so action
  maps / FightSettings can be read (and, with a writer, edited) programmatically.

### Counter deep-dive — the window is combat-action/animation data, not a settings value
- Decompiled the `FightAction` functions that use `FUN_1417f9e50` (states set: 0x2e, 0x41, 0xb) and the
  parry/counter-fail functions. The parry `FUN_141845e60` is invoked via **data tables / action-map
  dispatch** (its "callers" are data pointers at 0x142c72624 / 0x14354c7b8), so there is no direct call
  site where timing is decided. The `Fight*ActionMap` binaries are numeric graphs (no named window
  field; no strings inside).
- `CounterWindowSettings`, `CounterKillFightAction`, `CounterStrongEvent` are reflection/event type
  names with **no code xref** in the string-ref index.
- Combined with the earlier live test (`CounterOpenWindowRatio=0` changed nothing), **no FightSettings
  field tested so far drives the player's counter window.** The window is per-attack (enemy attack
  animation / action-map "open defense"), which is hard to edit in data.

### Session state
- `DataPC.forge` restored to `E7E963F0F6EEDFF83146159F4E6AF1E9` (clean modded, 145,260,544 B).
- `dxgi.dll` currently renamed to `dxgi.dll.off` (ReShade disabled).

---

## 2026-10-04 (cont.3) — workspace separation + combat-trace + counter deep-dive

### Workspace separation (user request)
Every project now has its own folder + `MODLOG.md`; root is an index (`README.md`). This AC Rogue mod
moved to `ac-rogue/` (docs + tools + `AC.PatchFix` + `forge_backups`). Dishonored docs moved to
`dishonored-rs/docs/` and `dishonored-vr-analysis/docs/dishonored/`.
- **Sharing caveat:** `AC.PatchFix` was a SHARED clone — it contains both this mod's hooks and
  **AccCoop** hooks (`PlayerTransform`, `PlayerProbe`, `HijackAvatar`, `Config` `[Coop]`) and AccCoop's
  `DataStorage`/registry edits. The deployed `.asi` builds all of them. Also `~/ghidra_scripts` is
  shared — AccCoop overwrote `targets.txt` mid-session. **Now using project-specific filenames**
  (`acrogue_targets.txt`, `acrogue_decomp.txt`, `acrogue_bytes.txt`, `acrogue_dump.txt`; scripts
  `DecACRogue.java`, `BytesACRogue.java`, `DumpACRogue.java`).

### Combat trace (new plugin hook) — `combat_trace.{hpp,cpp}`
A `CombatTrace` hook in the (shared) `ac-rogue/AC.PatchFix` MidHooks 14 combat functions and logs
`CT <name> #n t=<ms> rcx/rdx/r8/r9`. INI: `[Debug] CombatTrace=true`. Signatures are in
`game_data.hpp` (`COMBAT_*` scan entries). Hooked: `PAR`(FUN_141845e60 parry), `CFA`(CounterFail
FUN_14185cc40), `GRB`(GrabCountered), `WSET`(weapon setup), `POSE_A`(FUN_14185a9c0, state 0x2e),
`POSE_B`(FUN_14185d260, state 0x41), `FA1..FA8` (fight actions; FA9 pattern missing).

**What the trace shows (user counter attempts):** every counter press calls **`PAR` only**; a
*successful catch* additionally calls **`FA6`+`FA8`+`POSE_B` in the same ms**. So the catch/no-catch
decision is upstream of those. `PAR`'s 4th arg (`r9`) is a pointer that varies per variant.

### Counter window — data route conclusively dead
`FightSettings` is NOT the lever: forge edits (0.4/0.2) AND live writes to **all 11
`OpenWindowRatio`s → 0.01**, and to the four fields after `CounterOpenWindowRatio`, and to
`TimeCounterInputIsValid`/`MaxWaitTimeForDefenceCounter` candidates — **no in-game change** (user
tested). Live object found by scanning for `CounterOpenWindowRatio` (idx 64 of the float block,
e.g. 0x6CE8ADB4). ⇒ the catch window is computed in code from the enemy's attack state.

### Other findings
- The red "!" over an attacking enemy is the **conflict/detection HUD** (`FUN_1411ab240` /
  `FUN_1411cb970`: `FloatingIconGauge`/`FloatingIconAttackGauge`, `detection_blink`, `los_%s`,
  state at `obj+0x134`, gauge timer float at `obj+0x13c`) — NOT the counter prompt.
- `FUN_1416e1b60` maps fight-action ids → prompt strings: **`case 9/10 → "Counter Kill"`**,
  **`case 0x4a → "Counter Kill Tool"`** (also `0x16/3/6/0x18`→Shot, `0xd/0x14/0x13`→Poison,
  `8`→assassination variants, `0x26`→Stun Kill, `0x2d`→Combo Kill).
- `FUN_1420eef60` = lazy getter for the fight manager (field at `+0xf8`), not the update.
- `FUN_1411cb970`/`FUN_1411ab240` are HUD only.

### Counter deep-dive outcome (PARKED)
Conclusion after much RE + crash-prone experiments: **the counter window could not be located reliably.**
- The parry action `FUN_141845e60` is keyed by the **incoming attack's action code** via four classifiers
  `FUN_142052de0/e10/e40/e70` (each tests the fight-action object at `player_wrapper+0xb70` for
  `0x1F6 / 0x1F7 / 0x1F8 / 0x1F9`) and dispatches a parry variant (`FUN_14204faa0/fae0/fb20/fb60` /
  `FUN_14205e4d0`). A logged successful catch had code **`0x1F6`**; non-catch presses read `0x1F5`/`-11`.
  So those four codes = **counterable attack types**, not a time-into-swing phase → gating on the code is
  the wrong axis for "window nearer the hit".
- Gating attempts failed: skipping the parry by emulating a `ret` via `regs.rip`/`regs.trampoline_rsp`
  **crashes** (bad `RIP`); raw pointer reads in the trace are also crash-prone. All gate/trace code was
  **removed** and a clean `AC.Rogue.PatchFix.asi` rebuilt + deployed (CombatTrace off by default).
- The true lever (attacker animation/action **phase**) was never found; the enemy attack isn't any of the
  hooked `FightAction` functions.

**Parked status:** the timed-counter goal is not solved. Safe/clean plugin deployed; `dxgi.dll` remains
disabled (ReShade). Useful reusable results from this dive: the fight-action↔state map, the `CombatTrace`
hook (off), the `0x1F6..0x1F9` counterable-codes, and the forge/`.data` tooling.

### NEXT (reliable path)
Find the **enemy attack action function** (the action-id→function mapping; the AI picks a FightAction)
and/or the **counter-decision** that gates `FA6/FA8/POSE_B`, then hook it to enforce a
plugin-controlled window (INI-tunable, default 0.2 s). Candidate: trace the enemy side with more
`FightAction` functions, or decompile `FUN_1417d1ff0` (NPC AI graph) for the "NPC Attack" action.

---

## PAUSED 2026-10-04 (end of this session)

### Game-launch problem (IMPORTANT for next session)
`ACC.exe` was hanging/crashing at `D3D11CreateDeviceAndSwapChain` (ntdll `0xc0000005`; dumps in
`%LOCALAPPDATA%\CrashDumps`). Root cause looked like a **Direct3D overlay**: disabling ReShade
(`dxgi.dll` → `dxgi.dll.off`) let the game reach gameplay once, then it wedged again with **Bandicam
(`bdcam`) and Fraps** also running (both hook D3D). A wedged `ACC.exe` process (84 MB, no window) may
linger and **cannot be killed** ("no running instance of the task") — it clears on reboot.
- To run: close **ReShade (already off)**, **Bandicam**, **Fraps**. Restore ReShade later with
  `Rename-Item dxgi.dll.off dxgi.dll` (reset its preset if it still crashes).
- Never leave a crashed `ACC.exe` — kill by PID via `um win kill <pid>` before relaunching.

### What works / what's proven
- **Single-sword moveset** plugin hook: works (user-confirmed).
- **Data pipeline works**: modded `DataPC.forge` IS loaded (A/B proven).
- **Tooling built** (this folder): `forge.py` (forge reader), `forge_patch.py` (in-place blob swap),
  `forge_append.py` (grow-forge + repoint entry — the game loads it), `anvil.py` (AC Rogue `.data`
  container reader; reads localization, weapon, AND the 46 MB `Game Bootstrap Settings` = 20,988
  resources), `memscan.ps1`/`memread.ps1`/`memwrite.ps1` (live memory), `list_all.py`,
  `bin_diff.py`, `find_float.py`, `find_bytes.py`, `scan_floats.py`, `atktool/` (.NET wrapper around
  ATK's own `DataFile` — note ATK reports the big `CHR_P_Shay_Templar_Default.data` as `Locked=True`).
- Stock backup: `D:\...\Assassin's Creed Rogue\Backups\`. Pre-test forge backups:
  `forge_backups\DataPC.forge.modded_20261004`, `...cleanmodded_20261004b`. Save backup:
  `~/.universal-modder/backups/rogue-saves-pretest/`.

### Remaining goals + honest state
1. **Timed parry/counter** (user's current focus). Window is NOT a `FightSettings` value (live
   `CounterOpenWindowRatio=0` changed nothing; parry `FUN_141845e60` is action-map/table-dispatched).
   It is the enemy attack's per-attack "open defense" period in the animation/`Fight*ActionMap` data
   (numeric graphs, no named window field). **Recommended path:** plugin-side timed counter — hook the
   player's parry/counter-kill path and only allow the insta-kill inside a short window we control
   (miss → block). Needs RE to find the enemy-attack state + counter trigger.
2. **Hide off-hand dagger.** `ACC_W_P_ShayDefaultSword_Secondary` was proven **not** the held mesh
   (putting the sword's data in its slot left the dagger visible). The held dagger comes from elsewhere
   (character buildtable is `Locked`, or another attachment path). Next lead: find the held weapon's
   actual spawn/attach (Ghidra) or the player loadout/equipment resource.
3. **Counter window / harder combat** also still open.
- `DataPC.forge` restored to the clean modded state (`forge_backups\DataPC.forge.modded_20261004`).
- Saves backup: `~/.universal-modder/backups/rogue-saves-pretest/`.
- Tools added: `anvil.py` (Rogue `.data` reader), `forge.py` (forge reader), `forge_patch.py`
  (in-place forge blob swap), `memscan.ps1`/`memread.ps1`/`memwrite.ps1` (live process memory).

### Counter code RE (Ghidra, this session)
Decompiled `FUN_141845e60` (Parry, sets state 0x13 + a `Param_4`-selected parry variant via
`FUN_142052d*` → `FUN_14204f*`), `FUN_14185cc40` (CounterFail 0x19), `FUN_141849470` (GrabCountered
0x3f), `FUN_14102e960` (action-name→string map), and the two big registration functions:
- `FUN_1417bf580` = registers the **fight action/strategy set**: `Action_AttackCombos`, `Action_Deflect`,
  `Action_CounterDodge`, `Action_OpenDefenseAttack`, `Action_MeleeShield`, `Action_GrabFromBehind`,
  plus AGI patterns and `HTM_CounterKill/CounterTool/CounterHurt/CounterThrow`.
- `FUN_1417cc380` = builds the **NPC AI behaviour graph** with nodes `CanTakeAction`, `TakeAction`,
  `IsEnemyOpenDefenseAttacking`, `EnemyAttack`, `IsEnemyAttackIncoming`, `IsEnemyFocusedOnMe`,
  `IsEnemyOutOfRange`, `Random Counter With Check`, `Opponent Resists Counter Kill/Tool/Hurt/Throw`,
  `OpponentResistsOpenDefense`, `IsEnemyInDefenseStance`, `DoesPacingAllowNPCActions`, etc.
⇒ the counter timing is not a simple constant in code; it lives in the **Fight\*ActionMap graph** and the
AI strategy/A.G.I. patterns (binary, no XML in this ATK build). No difficulty-specific FightSettings
override found (`GamePlaySettings` `109_*`, `FightStrategyManager` `97_*` exist but no `Difficulty` entry
in any forge).

### User play-test: counter "feels unchanged"
With the edited values live and loaded, the user fought enemies and reported the counter window **felt
unchanged** → `TimeCounterInputIsValid`, `CounterOpenWindowRatio` and `AllNPCsFightCowards` do **not**
drive the counter-kill timing. The counter window must live in the combat action-map graph
(`FightParryDeflectActionMap`, `FightCounterPose*ActionMap`, `FightCounterKillActionMap` in
`49_-_Game Bootstrap Settings.data`; binary, no XML export) or in code.
Action-map binaries are graph-structured (e.g. `10092_-_FightParryDeflect.FightParryDeflectActionMap`
= 6396 B, dominated by repeated `6.79102` floats) — not a simple editable timing field.
→ Next: decompile the counter/parry code path in Ghidra (targets listed below) and find the real
decision arithmetic, then hook it in the plugin.

### New capability: live memory scan/edit of the running game
`memscan.ps1` (P/Invoke VirtualQueryEx + ReadProcessMemory) can find byte/float patterns in ACC.exe. This
enables live experimentation (change a candidate value in memory, test, iterate) without repacking.

### Next: find the RIGHT targets (data pipeline confirmed)
- **Counter window**: `FightSettings` `TimeCounterInputIsValid`/`CounterOpenWindowRatio` had no effect →
  the active values likely come from a different instance/field (difficulty `FightManagerDifficultyData`,
  nested `CounterWindowSettings`, or the `FightStrategyManager`). Re-examine the FightSettings XML
  structure and the `Fight*ActionMap` graph.
- **Off-hand dagger**: the held mesh almost certainly comes from the `CHR_P_Shay*` character BuildTable
  in `DataPC_extra_chr.forge`, not the `ACC_W_P_*Secondary` weapon entity's `Visual.Active`.

---

## Session 2026-10-05 — Counter window: found a real, reversible lever (phase mask)

Resumed the parked counter work. New static RE (Ghidra) + a new plugin hook.

### The parry classifier levers (new, decisive)
`FUN_141845e60` (game's counter/parry input handler) classifies the **incoming attack's current
action id** and dispatches a parry animation per match:
- `FUN_142052de0` → id `0x1F6` → parry anim set 0x21B / +8=0x118
- `FUN_142052e10` → id `0x1F7` → 0x217 / 0x11B
- `FUN_142052e40` → id `0x1F8` → 0x216 / 0x11F
- `FUN_142052e70` → id `0x1F9` → 0x215 / 0x120
- any other id → `FUN_14204fb60` → action `-3` (the **default normal parry/block**, no counter)

Each classifier is a 0x30-byte function; the comparison is `81 39 <imm32>` at **func+0x1C**
(`cmp dword [rcx], id`). Immediates (verified live in the running exe):
`0x142052DFC` (1F6), `0x142052E2C` (1F7), `0x142052E5C` (1F8), `0x142052E8C` (1F9).
Overwrite an immediate with `0xFFFFFFFF` → that id falls through to the default block branch.
**Hypothesis:** the four ids are the four phases of the counter window (prev session saw 0x1F5
before the window and negative after). Keeping one phase ≈ 1/4 window (~0.2 s if base ≈ 0.8 s).

### New hook: `CounterWindow` (games/ac/rogue, MSVC build deployed)
- `counter_window.hpp/.cpp` + `game_data.hpp` scan entries (`COUNTER_PHASE_1F6..1F9`, offset 0x1C)
  + registered in `registry.hpp`.
- INI `[Gameplay]`: `CounterWindow` (bool, default false = vanilla) and `CounterWindowPhases`
  (int mask, default 0xF; bit0=1F6 … bit3=1F9). Custom `phase_mask_parser` (dec/hex/0b).
- Patches/reverts the 4 immediates via `mem::write`; hot-reloads on INI edit (verified in log).
- Deployed `.asi` = 1,342,976 B (prev ours backed up `plugins\_backup_ours_20261005\`).
- Verified install: journal `hook_installed CounterWindow`; log shows the four immediates resolved.

### Status: LIVE play-test pending
Game running (PID 4196) with `CounterWindow=true`, `CounterWindowPhases=1` (only 0x1F6 counters).
Ask user to fight and report: do counters still land, does it feel like a shorter window, and does a
mistimed counter give a normal block. If only-one-phase still counters reliably on timing → phases
confirmed; if counters fail randomly → they are attack **types**, and we need a different lever.
Tuning is free: edit `CounterWindowPhases` in the INI while playing (hot reload).
New RE dumps: `acrogue_combat_decomp*.txt`, `acrogue_combat_callers_out.txt`, `acrogue_tables_refs.txt`.
New helper scripts: `resolve_sigs.py`, `scan_ref.py`, `scan_atk_id.py`, `classifier_bytes.py`,
`count_cls.py`, `va_dump.py`.

### IMPORTANT BUG FOUND: the ASI loader loads `.asi` from SUBFOLDERS too
`plugins\_backup_stock\` held 5 stale `AC.Rogue.PatchFix*.asi` builds (plus a my own
`_backup_ours_20261005\`). The dinput8 ASI loader **recurses**, so ACC.exe had **8 copies** of the
plugin loaded at once → only 12/16 hooks installed, repeated `VEH: ACCESS_VIOLATION` in the old
`pre-rva-20261004-202006.asi`, and the hang the user hit ("isn't loading").
**Fix:** moved `_backup_stock\` and `_backup_ours_20261005\` OUT of the game dir to
`ac-rogue\plugins_asi_backups\`. Now exactly one `.asi` exists under the game folder; the run is clean
(16/16 hooks, 0 VEH/critical).
**Rule going forward:** NEVER keep `.asi` files (even in `_backup_*` subfolders) inside
`D:\...\Assassin's Creed Rogue\`. Keep backups in the project folder. Also avoid `_backup_*` folders
under `plugins\` entirely.

---

## Session 2026-10-05 (cont.) — the counter window is NOT the OpenWindowRatio settings; base game has NO timing gate

### What the user actually wants (clarified)
A Dark-Souls-style parry: the enemy attack animation is ~1 s; a counter **tap in the first ~0.9 s =
a block**, a tap in the **last ~0.1 s = the counter** (kill/throw/tool/disarm). Base-game reality
(per the user): **hold the counter button = block; tap = counter whenever an enemy is attacking** —
i.e. there is **no per-attack timing gate at all**, which is why counters feel easy. We want to ADD a
timing gate.

### FightSettings `*OpenWindowRatio` is NOT the lever (proven live, again)
Found the live `FightSettings` float block by pattern-scanning memory for the 11-float run
`[0.75,0.75,0.5,0.6,0.7,0.75,0.4,0.75,0.35,0.75,0.3]` → base **`0x6D85033C`** this run:
```
+0x00 AttackHurtOpenWindowRatio=0.75   +0x04 AttackOpenWindowRatio=0.75   +0x08 OpenDefenseOpenWindowRatio=0.5
+0x0C BackForth=0.6 +0x10 StunKill=0.7 +0x14 ComboKill=0.75 +0x18 CounterOpenWindowRatio=0.4
+0x1C Contextual=0.75 +0x20 AttackOnGround=0.35 +0x24 DoubleCounter=0.75 +0x28 DoubleComboKill=0.3
```
Set Attack/AttackHurt/OpenDefense → **0.9** live → **user: unchanged**. (Prior session set them all →
0.01 → also unchanged.) ⇒ these fields are loaded but the player counter does NOT consult them.
(Also note the old session edited `CounterOpenWindowRatio`, the player's *own* counter action window,
not the enemy attack's — wrong field *and* wrong direction.)

### Plugin tooling added this session
- `CounterWindow` hook (classifier-immediate mask) — **disproven**: those `0x1F6..0x1F9` ids are the
  **player's own parry-state** (poll of the constant `obj=BE421F60`, ids idle `0x20D` / combat `0x2A4`
  / window `0x1F5` / parry `0x216`); the classifiers only pick the parry *animation*.
- `CounterProbe` hook — logs `CAN`(`FUN_1417f6fa0`, per-frame), `RESOLVE`(`FUN_141869550`),
  `RESB`(`FUN_14183b970`), `PARRY`(`FUN_141845e60`). Per-frame resolvers have **constant inputs**;
  the decision state is internal to the fight manager. Left `CounterProbe`/`CounterForce` INI keys
  (default off).
- Helper: memory AOB scanner (C# via `Add-Type`, `Encoding.GetEncoding(28591)` since PS5.1 has no
  `Latin1`); live float read/write tools.

### Remaining unknown (the crux)
Add a timing gate ⇒ need the **enemy attack animation clock** (time into the attacking enemy's swing).
Player-side code does not appear to use it. Next step if pursued: hook the counter-success path
(`FUN_14182ad10`/FA6 takes (player, A, B) → get the enemy entity) and read its animation component's
current time, then gate a tap. No clean runtime scalar found otherwise.

---

## Session 2026-10-05 (cont.2) — actual counter system map (live-traced; NO per-attack clock)

Traced the live state while the user did a controlled 4× counter / 4× block / 4× hit fight.

### Fight-manager layout (reached via `player+0x18` → X → `X+0xf8` → FM; X == the constant `obj` the
parry classifiers read, i.e. `obj = *(u64*)(player+0x18)`)
- `FM+0x1008` (byte): counter **disable** flag. `FUN_141803850(player,x)` / `FUN_14210f030(player,x)`
  set it. `FUN_1418038d0`/`FUN_14183b970` allow a counter only when `FM+0x1008 == 0`.
- `FM+0x1138` (byte): the base "can counter" flag that `FUN_1417f6fa0` ("CAN") checks — CAN returns 0
  while it is 0. Toas 0/1 per exchange.
- `FM+0x1120`/`+0x1128` (u64): a monotonically increasing time base (`+0x1128` advances every frame).
  `+0x1130` stayed 0; `+0x1140` is a pointer to the time reference (`**(fm+0x1140)`).
- The reset pattern `+0x1130=0; +0x1138=0; +0x1120=+0x1128=**(fm+0x1140)` appears in many fight actions.

### Live behaviour (75 s poll, per-change)
- `FM+0x1138` = 1 for ~**1.4–1.6 s** per fight exchange, 0 between. `FM+0x1008` = 1 for stretches when
  counters are disabled (e.g. during a counter/counter-pose), 0 otherwise.
- The player action id the classifiers read (`obj+0x230` / `+0x6d0`, selected via `obj+0xb70`) cycles
  `0x1F5 → (-3) → 0x216/0x21E/0x220 → 0x2A4/0x2A6/0x2A7`; `0x1F6..0x1F9` appear only transiently at a
  counter input. So those ids are the **incoming attack's action ids (4 attack types)**, not phases.

### Conclusion
There is **no per-attack animation clock exposed on the player side**. A tap-counter succeeds while
`FM+0x1138==1 && FM+0x1008==0` — a broad (~1.5 s) window — which is why counters are easy. The enemy's
impact time is only implicitly in the enemy's animation/AGI data. The only usable "clock" is the
`+0x1128` time base, so the mechanic can at best be *approximated* by gating a tap on elapsed time
since the `FM+0x1138` 0→1 edge (tunable), and forcing a block otherwise (the force-block path —
`param_2+0x188` — is still unvalidated).

---

## Session 2026-10-05 (cont.3) — CounterGate built; counter-window conclusively PARKED; AI-aggression started

### Counter window — final verdict (PARKED, do not re-chase)
Built and tested `CounterGate` (hooks `FUN_1417f6fa0`, writes `fight-manager+0x1008`):
- **Confirmed we can force a block**: holding `FM+0x1008 = 1` (externally, and via the in-hook write)
  makes every counter attempt a block. `FM+0x1008 == 0` is required for a counter.
- **`FM+0x1138` is set by the player's own counter press**, not by the enemy's swing: in the trace,
  `CP CAN fm1138=1` and `CT PAR` (the press) occur in the **same millisecond**, every time. So it is
  the counter/parry *pose* state, not an enemy-attack window.
- Therefore every gate we wrote collapsed to either "block everything" (pre-deny `fm1138==0`) or a
  **cooldown** (deny `D` ms after the pose). There is **no player-side enemy-attack clock** to key a
  true "last 0.1 s" window on. The enemy's swing phase lives only in the enemy animation/AGI data,
  which the player-side counter code never reads.
- **If ever resumed**, the only route left is reading the *attacking enemy's* animation clock: obtain
  the enemy entity before the press (we currently only see it *after*, via `FUN_14182ad10`/FA6's args)
  and gate the tap on its attack phase. Big, uncertain.

### AI aggression (in progress — weak/uncertain)
Aggression knobs are in the same `FightSettings` object. Located live by AOB float-sequence scan:
- **OpenWindowRatio block** (11 floats) — located at `0x6C01AFAC` this run.
- **Low-Health pacing tier** 8 floats at `0x6C01B2A0`; **Basic pacing tier** 8 floats at `0x6C01B350`
  (order: `FightActionsMax, Min, KillStreakFightActionsMax, Min, FightDecisionsMax, Min,
  KillStreakFightDecisionsMax, Min`). A second/third copy matched at `0x7B3DE3D4`, `0x90B3D4F4`.
- **Basic decision offsets** (7 floats, starting `CounterDisarm=1.55, CounterKill=1.1, ...`) at
  `0x6C01B384`.
- `AllNPCsFightCowards` is a Bool in this object (XML shows `True`); live address not pinned — the
  memory layout does NOT follow the XML field order linearly, so it must be found by scan, not offset.
- **Applied live (lost on restart)**: Basic & Low tiers → `0,0,5,5,0,0,5,5` (extreme fast actions/
  decisions; 5 s kill-streak delays to try to stop chain-kills); decision offsets zeroed; also written
  to the 2 extra copies.
- **Result: user reports "can't tell if placebo... slight difference".** ⇒ `FightSettings` is only a
  weak lever at runtime; real "extreme" aggression is likely in the **AI behaviour graph**
  (`FUN_1417d1ff0`, nodes `CanTakeAction`/`TakeAction`/`EnemyAttack`/`IsEnemyAttackIncoming`…) — a
  bigger job. Chain-kill disabling via the streak delays unconfirmed.

### Current on-disk / deploy state (for resume)
- Deployed `.asi` = latest build (1,367,552 B) with `CounterWindow` + `CounterProbe` + `CounterGate`.
- INI now: `CounterWindow=false`, `CounterProbe=false`, `CombatTrace=false`, `CounterGate` **set back
  to false** (it only produced a cooldown, not the wanted feature), `CounterGateDelayMs=1200`.
- **All the FightSettings memory edits are live-only and revert on relaunch** (the forge still holds
  vanilla `FightSettings`), so a fresh launch is vanilla aggression.
- `_backup_stock\` / `_backup_ours_*` remain moved OUT of the game dir to
  `ac-rogue\plugins_asi_backups\` (the 8-copies loader bug). Keep it that way.

### New hooks/tools added this session
- `games/ac/rogue/hooks/counter_window.{hpp,cpp}` — classifier-immediate mask (disproven, harmless).
- `games/ac/rogue/hooks/counter_probe.{hpp,cpp}` — diagnostic trace of CAN/RESOLVE/RESB/PARRY.
- `games/ac/rogue/hooks/counter_gate.{hpp,cpp}` — counter gate via `FM+0x1008` (cooldown).
- RE/scan scripts: `resolve_sigs.py`, `scan_ref.py`, `scan_atk_id.py`, `classifier_bytes.py`,
  `count_cls.py`, `va_dump.py`, `dump_bytes.py`, `scan_1138.py/b.py`, `scan_fm.py`,
  `player_globals.py`, `check_sigs.py`, plus the C# AOB scanner snippets (PowerShell, since script
  execution + PS `Encoding.Latin1` are unavailable — use `Encoding.GetEncoding(28591)`).
- New RE dumps in this folder: `acrogue_combat_decomp*.txt`, `acrogue_fm_decomp.txt`,
  `acrogue_setter_decomp.txt`, `acrogue_health_decomp.txt`, `acrogue_hud_decomp.txt`,
  `fightsettings_fields.txt` (all 516 FightSettings fields in order).

### Next steps (when resumed)
1. **AI aggression, extreme**: go to the AI behaviour graph (`FUN_1417d1ff0` and the `FUN_1417c1b00..`
   builder chain) and/or find the per-NPC aggression/pacing parameter; confirm/deny
   `AllNPCsFightCowards` (find it by scan) and whether the streak delays stop chain-kills.
2. Everything else (one-handed sword, ultrawide/FOV/FPS/language, ASI-loader fix) is working.

---

## Session 2026-10-05 (cont.4) — counter flow mapped; "no block" hook built (untested at runtime)

Autonomous dig (no user tests). Two asks: (a) disable the block, (b) make the counter a
last-moment parry.

### The player counter is an EVENT-DRIVEN state machine (this is the real window)
- `FUN_14211d970(param_1, bool)` is the fight-action chain dispatcher. It reads the chain
  state `lVar2 = *(param_1+0x218)` (shorts at `+4`, `+6`, `+10`) and, per state, checks a
  **pending-event list** with `FUN_1402924c0(stateStruct, eventId)`, then dispatches:
  - state `+4 == 0xa8` and `+10 == 0xad` → `FUN_14183e8d0` (event **0x1F6**)
  - state `+4 == 0xa8` and `+10 == 0xae` → `FUN_14183e900` (event **0x1F7**)
  - state `+4 == 0xa8` else → `thunk_FUN_141803850` (event **0x1b6**)  ← sets `FM+0x1008`
  - state `+4 == 0x1ee` → `FUN_14210f030` (event **0x373**)          ← sets `FM+0x1008`
- `FUN_1402924c0(ptr,id)` = linear search of an array (`ptr+0x20`, count `*(u16*)(ptr+0x2a)`).
  So the counter fires when the relevant event id is **pending** — that pending set is the
  window, populated by the enemy's attack (open-defense), NOT a player-side timer.
- `FUN_14183b970` (action-availability) gates on the incoming action's **step**:
  `param_2+0x18a` (current step) vs `FUN_14183aea0(param_1, param_2+0x18, 1)` (total steps);
  it allows (`return 2`) when the step is at/near the last step. That is the closest thing to
  a "last moment" gate — it already exists, per-incoming-attack, and its granularity is the
  attack's animation action map (data). ⇒ To get a *tighter* last-moment window we would need
  to change the incoming attack's step timeline (action map / animation), still the data wall.
- `FUN_14183e900`: if `FM+0x1008 == 0` sets `player+0xaf8 = 3` else `= 0x12`; `FUN_14183e8d0`
  → `FUN_14183bdb0(player,0,0)`. These are the defense/counter handlers.

### Block lever (the deliverable) — `TimeButtonHeldForParry`
- `FightSettings` counter block located live; values in order:
  `CounterSlowMotionDuration 0.3, CounterSlowMotionIntensity 0.04, SlowMotionAdjustedDuration
  0.012, SlowMotionAdjustedDurationShellshocked 0.8, MaxWaitTimeForDefenceCounter 0.3,
  TimeButtonHeldForParry 0.2, TimeCounterInputIsValid 0.2` (this run at `0x6C01B004`..`0x6C01B01C`).
- **Hold = block** is `TimeButtonHeldForParry`; raising it (e.g. 999) should stop a held press
  becoming a block, so the button only attempts a counter. (Same values as
  `TimeCounterInputIsValid`, the input-buffer window.)
- New hook **`CombatTweaks`** (`games/ac/rogue/hooks/combat_tweaks.{hpp,cpp}`, registered):
  - INI `[Gameplay] NoBlock` (bool, default false), `BlockHoldSeconds` (default 999),
    `CounterInputValid` (float, -1 = leave). 
  - Because the block lives in heap memory (per-launch address), the hook spawns a background
    thread ~25 s after install that AOB-scans committed writable regions for the 7-float run
    above, requires **exactly one** hit, then writes `TimeButtonHeldForParry` (and optionally
    `TimeCounterInputIsValid`). It refuses to write if the pattern isn't unique.
  - **Deployed with `NoBlock=true`; NOT yet validated in-game** (see blocker below).

### Blocker / caveat for next session
- A wedged `ACC.exe` (PID 10672) that **cannot be killed** ("no running instance") is sitting
  on the machine and blocks a clean relaunch. It clears on **reboot** (documented before).
  So the `CombatTweaks` scan has not been verified by a live run yet.
- The zombie also **holds `plugins\AC.Rogue.PatchFix.asi` open**, so the newest build (with the
  12×12 s retry loop for the locate step) could not be copied over it. The deployed `.asi`
  (1,373,696 B, 12:22:53) is the earlier **single-25 s-scan** version. **After reboot, redeploy**
  the retry build from
  `ac-rogue\AC.PatchFix\build-msvc\bin\Release\AC.Rogue.PatchFix.asi`.
- To verify on return (after reboot): launch, wait ~40 s, check
  `plugins\AC.Rogue.PatchFix.log` for `CombatTweaks: counter block 0x...`; then play-test
  whether holding the button still blocks. If the log says "not found (unique)", widen/narrow
  the pattern (the two 0.2 s and the 0.3/0.04/0.012/0.8 values are the anchors).

### Next steps
1. Reboot (clears the zombie), launch, and confirm `CombatTweaks` finds the block; test "no
   block" and tune `BlockHoldSeconds`.
2. For the exact last-moment parry: the gate is the incoming attack's **step timeline** (in the
   `Fight*ActionMap`/AGI data) or the event-pending set fed by it — the last remaining data wall.
   A plugin alternative (schedule a block-for-N-ms to narrow the pend window) is NOT possible,
   since the pending events are set by the enemy attack, not the player.

---

## Session 2026-10-05 (cont.5) — tooling: gamedb + full decompile export

Pivoted from blind hooking to indexed RE (per `REFERENCES.md`).

- **Built `gamedb`** from source (`C:\Users\Administrator\gamedb\target\release\gamedb.exe`; Rust/cargo
  present). Validated: indexed our dumps → 3,348 fn / 128k edges in seconds; `search`/`graph`/`strings` OK.
- **Full `ACC.exe` decompile export** via new `ghidra_scripts\DumpAllDecomp.java` (arg: outDir, chunkSize,
  minAddr, maxAddr) → `C:\Users\Administrator\ghidra-acc\acc-decomp\acc_NNNN.c` (3000 fn/chunk, ~45 chunks,
  134k functions). Still running (~40% at time of writing; java PID 24940). Note: the OpenCode **server
  restart cancelled the shell job but the orphaned java kept writing** — the export is alive; a watcher job
  will `gamedb index` the tree when java exits.
- **Plan when indexed:** query the call graph to (a) find the guard/`Deflect` action and a **safe**
  neutralization for "disable the block" (the blind no-op crashed), and (b) trace the producers of pending
  events **`0x1f6`/`0x1f7`** + the step timeline (`FUN_14183aea0`/`FUN_141809e80`) for the last-moment parry.
- **Verdict on a Rust rewrite** (user asked): not 1:1 — see `REFERENCES.md`/mashup-mods; the realistic
  Rust work is a **data toolkit** (forge/.data/format converters) + a subsystem sandbox, not the game.
- Decompiled dumps stay out of anything shipped (`um publish check`).

---

## Session 2026-10-05 (cont.6) — full code index: verdict confirmed (both goals are data, not code)

`gamedb` over the **complete** decompile (132,478 functions, 424,838 call edges) settles the question.

- Fight actions are registered as **id + a shared generic vtable** (`FUN_1417a4f20(id)` →
  `PTR_FUN_142a621d0`; `FUN_1401d5930(id, entry)` into `DAT_14329e568`). **No code branches on the
  action** — behaviour is dispatched by id through the **action-map data**.
- The full tree contains exactly **one** `Deflect` reference (the `Action_Deflect` registration);
  no function implements a "block"/"guard" path by name. `CLBlockingGuard` is only an **event +
  animation** posted by `FUN_141abacd0`.
- `FM+0x1008` (counter gate) and the `0x1f6/0x1f7` counter events are all produced inside the
  **state machine `FUN_14211d970`** (called from `FUN_14211dbd0`/`FUN_14211dc40`, which are
  themselves data-dispatched) → `FUN_14183e8d0`/`FUN_14183e900`/`FUN_141803850`/`FUN_14210f030`.
- **Verdict:** neither "disable block" nor the "last-moment parry window" has a code lever. Both
  live in the fight **action-map / animation (AGI) data** (`Game Bootstrap Settings.data`), which is
  why every code hook/patch either no-ops or crashes. Time to attack the data or ship the rest.
- Tooling left: `acc-decomp\` (full decompile) + `acc-decomp\.gamedb\index.sqlite`; query with
  `C:\Users\Administrator\gamedb\target\release\gamedb.exe` (`search`/`read`/`graph`/`strings`/`sql`).

---

## Session 2026-10-05 (cont.7) — AI-aggression review against the decompile (why the pacing edit is a placebo)

Prompt: "look over the ai aggression now that we have decomped exe". Verdict: the melee AI is a
**behaviour tree built in code, one per NPC class**, and our `FightSettings` pacing edit only touches
a downstream throttle. Findings:

### The AI is per-class behaviour trees, built in code at load
- Builders: `FUN_1417c1b00` (107453-108407), `FUN_1417c3630`, `FUN_1417c51a0`, `FUN_1417c7490`,
  `FUN_1417c9410`, `FUN_1417cb0e0`, `FUN_1417cc380`, `FUN_1417ceab0`, plus `FUN_1417d1ff0`
  (116k-line range). Each builds a named tree: **`DT AC3 Militia`, `DT AC3 Red Coat`, `DT Agile`,
  `DT Default`, `DT Leader`, `DT Swiss Guard`**.
- Node factories: `FUN_1401b4f10` = **action** node (name + `[3]` = child condition ptr), e.g.
  `EnemyAttack`, `NPC Attack`, `TakeNewAction`; `FUN_1401b52e0` = **condition leaf** whose `[3]` is a
  **bitmask code** (`IsArmed`=`0x80`, `IsEnemyOpenDefenseAttacking`=`0x1000000000`,
  `IsTargetBusy OR IsTargetOnGround`=`0x40000010`); `FUN_1401b5540` = "Done Node : Do Nothing".
- **The pacing throttle is a decorator, not a branch**: the `NPC Attack` / `EnemyAttack` action node
  is wrapped by **`DoesPacingAllowNPCActions`** (created as a clone of the action node via its vtable
  `+0xa0`, value = the action node). So NPCs only attack when pacing allows it. The condition
  **code is a bitmask of world conditions** evaluated by a VM; the pacing decorator consults the
  fight-manager pacing state.

### The `FightSettings` field names are NOT in the exe
- `gamedb strings` for `FightSettings`, `FightPacingSetting`, `AllNPCsFightCowards`,
  `FightActionsMaximumDelay`, `LowHealthPacingRatio` → **all zero hits**. The schema lives in the
  data file (`Game Bootstrap Settings.data`); the exe reads by raw offset. So fields can only be
  found by pattern scan / live address, never by a name string.

### Why the pacing edit was weak — the object's bools are NOT inline (new, important)
- The schema dump (`fightsettings_fields.txt`) is a faithful field list. Cross-checking the known
  anchors proves the **float fields are contiguous but bool fields are stored separately**:
  between the 11-float `OpenWindowRatio` run (fields `382-392`) and the 7-float counter block
  (fields `406-412`) the fields `393-405` are **exactly 22 floats = 0x58 bytes** — the live
  OWR→counter delta. The two bools at 404/405 contribute **0 bytes**, so bools are not interleaved.
- Consequences: `AllNPCsFightCowards` (a bool) is **not** adjacent to the pacing floats and cannot be
  reached by an offset from our counter-block anchor; the size caps
  (`MaxFightersInPlayerInnerRing=3`, `TotalMaxFightersInPlayerInnerANDOuterRing=10`) are
  `Unsigned32` in a separate int block. Our hook only finds the **float** pacing tiers
  (counter-block `+0x29C`/`+0x34C`), which are the weakest knob.

### Verdict + options
- **Extreme aggression is not reachable by the pacing-tier write** (confirmed weak/placebo). The
  dominant levers are the per-class behaviour tree, the `DoesPacingAllowNPCActions` decorator, and
  the global `AllNPCsFightCowards`.
- Paths: (a) **pin `AllNPCsFightCowards` + the ring-count block by live memory scan** (needs the game
  running) and write them; (b) locate + neutralise the `DoesPacingAllowNPCActions` decorator in the
  fight-manager pacing state; (c) edit the forge data. (a) is the cheapest and highest-impact.
- Code kept from this pass: `CombatTweaks` gains `AIAggression` (scales the pacing tiers) and
  `NoChainKills`; these are the *tiers only*, so treat them as a mild lever, not "extreme".

---

## Session 2026-10-05 (cont.8) — EXTREME AGGRESSION: fight-manager pacing predicate hooked (#1)

Found and shipped the real lever. The per-class behaviour trees gate `NPC Attack`/`EnemyAttack`
with the condition **`DoesPacingAllowNPCActions`**; the BT leaf evaluator is
**`FUN_142103950`**, which calls the fight-manager predicate **`FUN_1420fa3a0`**:

```
bool FUN_1420fa3a0(param):
  a = *(param+0x18);            // entity
  b = *(a+0xf0);                // fight controller
  c = *(b+0x18); fm = *(c+0xf8);  // fight manager (0x11f0 bytes)
  if (*(u8*)(fm+0x1160) == 0) return 1;          // window closed -> PACING ALLOWS
  if (fm+0x1150 <= current_time) return 1;       // window expired -> allows
  return 0;                                       // window still running -> denied
```
i.e. it returns 1 (allow) once the action-pacing window is over, 0 while a just-started action's
delay runs. This is the "one action at a time" throttle; it was never the `FightSettings` floats.

- **Hook:** `games/ac/rogue/hooks/ai_pacing.{hpp,cpp}` (`AIPacingHook`, INI `[Gameplay]
  ExtremeAggression`, default on). Mid-hooks `FUN_1420fa3a0` and, on every query, walks
  `rcx→+0x18→+0xf0→+0x18→+0xf8` to the FM and writes **`FM+0x1160 = 0`**, so the predicate always
  returns allow → no NPC is held back by pacing.
- **Address table:** added `ResolvedAddresses::ai_pacing` + scan entry `AI_PACING` in
  `game_data.hpp`. Signature (verified **unique** in `ACC.exe`, resolves to VA `0x1420fa3a0`):
  `40 53 48 83 EC 20 48 8B 59 18 48 83 BB F0 00 00 00 00 75 0A 33 D2 48 8B CB E8 82 E4 FE FF
   48 8B 9B F0 00 00 00 48 8B 4B 18 E8 92 4B FF FF`
  (the two `E8 …` tail calls are what separate it from siblings `FUN_1420fa420` @FM+0x1188 and
  `FUN_1420fa4a0` @FM+0x11b0, which are "window active" checks — deliberately NOT hooked).
- **Built + deployed:** `AC.Rogue.PatchFix.asi` 1,384,960 B → `plugins\`, killed the wedged
  `ACC.exe` PID 16516 that was locking it. INI `[Gameplay]`: `ExtremeAggression=true`,
  `AIAggression=1.0` (mild tier scaler off), `NoChainKills=false`.
- **Status:** awaiting in-game test. If pacing was the dominant throttle this should read as a
  clearly more aggressive mob; if it is flat, the remaining lever is the tree action-selection
  itself (`FUN_1417d1ff0` chain) or the engagement caps.

---

## Session 2026-10-05 (cont.9) — AI aggression: pacing route DISPROVEN; player-vs-NPC path split found

Ran a live diagnostic build (unconditional call counters + a tracer on the fight-manager accessor
`FUN_1420eef60`). Results, then two failed experiments:

- **The pacing predicate is dead.** `FUN_1420fa3a0` (my `AIPacing` target, thought to be
  `DoesPacingAllowNPCActions`) is **never called** during combat: `pacingCalls=0` while
  `fmAccessorCalls` ~6-8k/s. The whole "pacing gate" story was wrong; that hook was inert.
- **Real combat code paths** (48 distinct callers of `FUN_1420eef60`): fight-action handlers
  `FUN_14183e050`, `FUN_14183fec0`, `FUN_1418507e0`, `FUN_1418563d0`, `FUN_141855350`,
  `FUN_141855180`, `FUN_141851260`, `FUN_14180cf50`, `FUN_14183bfe0`, `FUN_141839d50`,
  `FUN_14184ea20`, `FUN_14180ac40`, `FUN_141870d10/f10`; the counter code `FUN_1417f6fa0` /
  `FUN_141803850`; and exactly **one** tree condition `FUN_142102c50` (1 if `FM+0x1050 != 0` or
  `npc+0x8c8 != 0`).
- **Experiment A** — `FUN_14183b970(actor, action)` is the fight-action *availability* gate
  (2/3 = allowed; 14 callers, all fight-action handlers). Built an `InlineHook` detour returning
  "allowed" for NPC actors only (player via `actor+0xd0 & 7 == 1`). Live result:
  **`npcForced=0`, `playerPass=` every call** → the enemy AI never calls it; it is a
  **player-only** availability check. No combat change.
- **Experiment B** (same build) — no effect either.

### Where the enemy AI is NOT
`FightSettings` pacing floats, `FUN_1420fa3a0`, and `FUN_14183b970` are ruled out. The enemy attack
decision is the fight manager's **NPC-side** state (`FUN_142102c50` / `FM+0x1050` / `npc+0x8c8` and
the fight-action handlers above) — the NPC does not go through the player's availability function.
That is the next place to look.

### State left behind
- Rogue left with `ExtremeAggression=false`, `ExtremeAggressionTrace=false`.
- `AIAggression` hook (`ai_pacing.{hpp,cpp}`, `FUN_14183b970` detour) + `AI_ACTION_AVAIL` pattern
  remain in-tree, default-off.
- User is out of patience for live test cycles on this; treat further aggression work as an
  unattended RE task (no "launch and tell me" loops).

---

## Session 2026-10-05 (cont.10) — Throwing knife as a permanent inventory item (probe results)

Goal: make the Agile-dropped throwing knife a permanent part of Shay's arsenal, reachable in the
inventory.

**What the game actually has (found):**
- Throwing knife is a **Tool**: `FUN_141022b90` (Tool enum) case 7 = "Throwing knife"; the current
  tool is read via `FUN_141e6bea0` (dispatches `obj->vtable[0x18]`, `obj = comp->vtable[0x60](comp)`,
  indexed by the player slot byte at `DAT_1433866d8 + 0x65`).
- It is also an **inventory category**: `InvItem_Knives` (type 8) in `FUN_14102b180`.
- The combat action is `Action_ThrowKnife`, registered id **0x1b** (`FUN_1417bf580`).
- The item/grant catalog (`ACGA_*`, type `0xC69075AB`) has `ACGA_Crafting_SmokeBombPouch_*` /
  `RopeDartPouch_*` but **no knives entry** — the knife was never a buyable/craftable tool.

**Probe results (KnifeProbe hook, `FUN_141e6bea0 + 0x3a` = tool object; entry = holder):**
- The **tool object** (class vtable `0x142ACD4B0`) and the **holder** (`*(playerSlot+0x30)`,
  type byte at `+0xd0 & 7 == 1` for the player) are **byte-identical with and without a knife** —
  the stock is not in either.
- A **range diff** of the player heap block (`0xD3E1A000` +0x20000) and two child blocks across a
  throw was **inconclusive** — dominated by live pointer churn; no clean isolated count.
- `player+0xaf8` (documented "current combat action") is **not** written with `0x1b`; the throw is
  dispatched through the **fight-action/action-map data**, not a simple field.
- Rogue's real save is **not** at the obvious Ubisoft save paths (the `rogue-saves` backups only
  captured `AssassinRogue.ini`, a config file), so save-editing isn't immediately available.

**Conclusion:** the throwing knife behaves as a **contextual combat item**, not a stored inventory
count. Making it a true permanent inventory entry needs either (a) authoring a new tool/item asset
(ActionGraph, multi-session data job), or (b) pinning the fight-action 0x1b availability gate and
forcing it — which needs the action-map path, not a stored field.

**State:** `KnifeProbe=false`, `ExtremeAggression=false` (all experiments off). Probe hook and
patterns remain in-tree, default-off. Unity of the rest of the mod unaffected.

**Follow-up (player-only tool probe):** added a probe that follows the game's own chain from the
**local player** (`holder+0xd0 & 7 == 1`) to the player's tool object. Diffs with vs without a
knife:
- The player's **tool object** (`vtable 0x142ACD4B0`) is **byte-identical** with and without a knife.
- Its ~10 **child tool objects** (per-tool `{dataPtr, vtable}` entries) are **also byte-identical**
  across a throw.
⇒ The "throwing knife selected/available" state is **not** in the tool system at all. It is driven
from higher up (the fight manager / player combat state we explored in cont.3-9, or the Scaleform
inventory model), which is the next place to look. User's clarification: the knife **is** a
selectable item in the HUD wheel alongside rope dart / bombs / money / pistols — so the wheel's
availability comes from that higher-level state, not the tool objects.

---

## Session 2026-10-05 (cont.11) — Throwing knife: both routes investigated, concluded

Goal: make the Agile-dropped throwing knife a permanent wheel item / inventory tool.

### Key facts established
- Throwing knife = **Tool id 7** (`FUN_141022b90` Tool enum: Nothing/Pistols/Rope Dart/Smoke
  Bomb/…/Throwing knife=7). Combat action `Action_ThrowKnife` registered id **0x1b**.
- The wheel is **slot-based**, driven by input actions `NextToolSelection` / `PrevToolSelection`
  and `Inventory0..7` (`FUN_14100…` binding table, acc_00000.c ~0x660).
- The HUD tool/ammo readout goes through `FUN_1410f7460(id, actor)` (current) and
  `FUN_1410f73d0(actor, id)` (max). Both tail-call `[component_vtable+0xF8]` / `+0x108`, and
  `FUN_1410f7460` **only accepts ids `{1, 0x14..0x1b}`** — tool id **7 is explicitly rejected**
  (returns -1). ⇒ forcing it changes the HUD only; it is **display-only**. (Verified in game:
  `ThrowingKnifeAll=true` altered every other tool's HUD number and did not add the knife.)
- The player's **tool object** (`vtable 0x142ACD4B0`) and its ~10 **child tool objects** are
  **byte-identical with and without a knife**; so is the holder (`*(playerSlot+0x30)`,
  player type byte at `+0xd0 & 7 == 1`). The knife state is not in the tool system.
- **Data route (ruled out):** every real wheel tool has a data definition — pistols
  (`ACC_WR_*_Pistols_*`), rope dart (`ACC_WR_Player-RopeDart`,
  `CHR_W_P_RopeDart_SpawnedProjectile`), smoke bomb (`CHR_W_P_SmokeBombPlayer`), money
  (`CHR_W_P_Money_Throwable`). The throwing knife has **only assets**
  (`TPL_WP_Throwing_Dagger`, `TPL_WP_Throwing_Dagger_LOD0/BoxShape`,
  `ProjectileSoundSet_ThrowingDagger`) and **no player tool/item definition** anywhere (no
  `ACC_WR_Player-ThrowingKnife`, no item-catalog / inventory-page / shop / ammo entry). So there
  is nothing to edit — a real inventory entry would require authoring brand-new engine resources
  (hashed types) + UI + input mapping: a large content-engineering project.

### Verdict
The throwing knife is a **contextual combat state granted by the pickup event**, not a stored
inventory item. It's *possible* to make permanent, but neither of the two obvious routes is a mod
tweak:
- **Data:** nothing to edit; would need full new-resource authoring. (Not feasible in one session.)
- **Runtime:** the loadout/pickup state must be found first — the only method that can't miss is a
  **whole-process differential** (snapshot at 0 knives → pick up 1 → diff). Then a small hook could
  set it at load. This is the recommended next step if ever resumed.

### State left behind (all experiments OFF)
- Deployed `AC.Rogue.PatchFix.asi` (1,401,856 B, one copy in `plugins\`).
- INI `[Gameplay]`: `CounterWindow=false`, `CounterGate=false`, `NoBlock=false`,
  `ExtremeAggression=false`, `ExtremeAggressionTrace=false`, `KnifeProbe=false`,
  `ThrowingKnives=false`, `ThrowingKnifeAll=false`.
- New in-tree hooks (all default-OFF, harmless): `KnifeProbe` (`knife_probe.*`),
  `KnifeGrant` (`knife_grant.*`), `AIAggression` (`ai_pacing.*`). Patterns added to
  `game_data.hpp`: `KNIFE_PROBE`, `KNIFE_ENTITY`, `KNIFE_QTY`, `KNIFE_QTY_MAX`, `AI_PACING`,
  `AI_ACTION_AVAIL`.
- Working features untouched: one-handed Shay sword, ultrawide/FOV/FPS/language, ASI-loader fix.

### For the next agent — throwing knife
Do **not** re-probe the tool object / holder / HUD accessor (all proven negative / display-only).
Go straight to a **whole-process differential across a single pickup**, or author engine resources.
See also `THROWING_KNIFE.md` for the timeline.

---

## Session 2026-10-05 (cont.12) — Off-hand dagger HIDDEN (SOLVED)

The one-handed sword now reads as a true single sword: the off-hand dagger is invisible.

### What actually works
The held dagger is a **weapon entity**; hiding it = setting its **entity** visibility flags:

```
<Bool Name="IsVisible">False</Bool>
<Bool Name="IsHidden">True</Bool>
```

in the **Entity** resource of each sword set's `..._Secondary.data` (e.g.
`ACC_W_P_French_Cutlass_Secondary`). In the container's decompressed `files` block the two
flags sit in the bool run `00 01 01 01 01 00 01 00`
(= `IsSpawned, IsVisible, WasVisible, IsPhantom, IsStatic, IsHidden, IsSmallObject,
IsMediumObject`): flip the **IsVisible** byte → 0 and the **IsHidden** byte → 1.

### What does NOT work (proven, don't retry)
- `Visual` component `Active=False` (prior session) — no effect on the held mesh.
- Material `MaterialDisabled=True` — no effect (means something else).
- Entity `WeaponComponent` fields — no effect.

### How it was applied (repeatable)
- `re_scratch/container_rw.py` — read/rebuild an AnvilNext `.data` container (validated by
  byte-identical round-trip). Checksum = `adler32(block_data, init=0)`.
- `re_scratch/batch_patch.py` — for every forge entry ending `_Secondary`, extract the container,
  flip the two entity bytes, and write back **in place** if it fits, else **append + repoint**
  (recompressed LZO is sometimes a few bytes larger). Result: **46/46 patched** (11 in place,
  35 appended), forge `145260544 → 146980089` bytes.
- Backup: `forge_backups\DataPC.forge.predagger` (pre-edit). To redo after a game verify/update,
  restore that backup then re-run `batch_patch.py` (game must be closed — it locks the forge).
- At runtime the game must be **restarted** for forge changes to take effect.

### Gotchas learned
- ATK's per-resource `.xml` is only a sidecar; the game reads the binary, and ATK's repack
  re-exported the **unchanged** binary (forge rewrote byte-identically) — every ATK "test" was
  invalid until we wrote the binary ourselves.
- Writing into the forge **requires the game closed** (it holds `DataPC.forge`).
- The dagger is per sword set — patching one set only affects that set.

---

## Session 2026-10-05 (cont.13) — mod split: Single Sword + Hidden Dagger (coop/combat out)

Repackaged the work into two standalone mods (workspace-root folders):

- **`ac-rogue-single-sword\`** — `AC.Rogue.PatchFix.asi` **trimmed** to only the base
  display hooks (ultrawide/FOV/FPS/language) **+ the one-handed sword** (`weapon_class`),
  plus `AC.Rogue.PatchFix.ini` and `README.md`. Build = `registry.hpp` `AllHooks` reduced;
  the coop/combat hook sources moved to `ac-rogue\excluded-hooks\{src,include}\hooks\`
  so the recursive source glob no longer compiles them. Deployed to `plugins\` (1,272,832 B,
  vs 1,405,440 B full).
- **`ac-rogue-hidden-dagger\`** — its own mod: `Install.bat` + `hide_dagger.py` (one-click,
  self-contained patcher for the user's own `DataPC.forge`) + `README.md`. No game files
  shipped.
- **`ac-rogue\`** — the dev/RE workspace; `AC.PatchFix\...\registry.hpp.full` keeps the
  untrimmed hook list; `excluded-hooks\` keeps the coop/combat sources.

Attribution: the **ultrawide/FOV/FPS/language** features are upstream
**playday3008/AC.PatchFix** (tracked files), not ours. Ours = the one-handed sword
(`weapon_class`), the hidden-dagger data fix, and the (now-separated) coop/combat hooks.

Note: a wedged `ACC.exe` (unkillable, holds the `.asi`) recurs; clears on reboot.


## Session 2026-10-05 (cont.14) - one-handed sword SOUND set swap (built, then PARKED for release)

Goal: make the attack/finisher audio match the one-handed animations.

Findings:
- Weapon sound sets live in each `*_Secondary` container: `WeaponSoundSet_Dual_Medium_Sword`
  (+ `_NPC`). The single-sword sets `WeaponSoundSet_Medium_Sword` (16693 B) / `_NPC`
  (14829 B) live in the `Game Bootstrap Settings` container (in `DataPC.forge`).
- AnvilNext `.data` container = filter table + two CompressedFileData blocks (`meta`,
  `files`). `meta` is a per-resource index: `u16 count`, then `[u64 id][u32 record_size]
  [u16 pad]`; record_size = 12 + nameLen + headerLen + payloadLen. The game walks
  resources using these stored sizes.

First attempt (CRASH): rebuilt the `files` records with the SHORTER single-sword payloads
but did not update the `meta` record sizes -> the resource walk desynced -> crash
(`ACC.exe+0x819327`, `0xc0000005`). Fixed by restoring the pre-sound forge
(`forge_backups\DataPC.forge.presound`).

Working method (`re_scratch/swap_sounds2.py`): rebuild `files` records AND update the
matching `meta` sizes, then recompress both CFds. Applied to 45 `*_Secondary` sets
(90 payload slots), 0 problems; game loads and runs. Backup: `DataPC.forge.presound2`.

Status: applied locally, PARKED for release (not shipped).

## Session 2026-10-05 (cont.15) - Nexus release packaging

- `ac-rogue-single-sword\`: restructured to install layout `plugins\AC.Rogue.PatchFix.{asi,ini}`
  + `README.md` + `LICENSE.txt` (upstream MIT, PlayDay). `.asi` MD5 F0E8BB6D... = deployed/tested build.
- `ac-rogue-hidden-dagger\`: `Install.bat` + `hide_dagger.py` + `README.md`.
- `ac-rogue\NEXUS.md`: page copy (titles, bios, tags) + zip/upload steps + checklist.
- `dist\OneHandedSword-1.0.zip`, `dist\HiddenDagger-1.0.zip`.
- `um publish check`: both PASS (the sword's initial FAIL was a self-match against the
  deployed copy in the game folder).
- Credits per user: upstream only (no AI disclosure). Sound fix parked.
