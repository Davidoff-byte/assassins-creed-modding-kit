# HANDOFF — AC Rogue modding (read this first in a new session)

Handoff from a long working session. Read this, then `MODLOG.md` and
`COMBAT_STEALTH_RESEARCH.md` in this folder for detail. Everything below is verified on this machine.

---

## 0. LATEST STATUS (2026-10-05) — read this block first

The detailed `MODLOG.md` has the full journal; the short version:

- **Shipped / working:** one-handed Shay sword moveset (fight-type remap `7→1` at
  `FUN_141807200`/`FUN_141715160`); ultrawide + FOV + FPS-unlock + language hooks; the ASI-loader
  "8 copies" fix (backups live in `ac-rogue\plugins_asi_backups\`, one `.asi` only in the game's
  `plugins\`).
- **Parked / not delivered:** the "short last-moment counter window / parry", "disable the block",
  and "extreme AI aggression". Whole-fight system is data/action-map driven; several plausible
  code levers were disproven (see `MODLOG.md` cont.4–cont.9). Do **not** re-chase
  `FightSettings` pacing floats, `FUN_1420fa3a0`, or `FUN_14183b970`.
- **Throwing knife → permanent arsenal:** not delivered. Both routes investigated to a conclusion;
  it is a contextual combat *state*, not a stored inventory item, and the data has no tool
  definition to edit. **See `THROWING_KNIFE.md`** — read it before touching this feature.
- **Deployed hook state:** `AC.Rogue.PatchFix.asi` (1,401,856 B) with all experiment hooks
  default-OFF (`CounterWindow=false`, `CounterGate=false`, `NoBlock=false`, `ExtremeAggression=false`,
  `KnifeProbe=false`, `ThrowingKnives=false`, `ThrowingKnifeAll=false`). Extra hooks in-tree but off:
  `KnifeProbe`, `KnifeGrant`, `AIAggression`.
- **Tooling now available:** full `ACC.exe` decompile + `gamedb` index
  (`C:\Users\Administrator\ghidra-acc\acc-decomp`, query with
  `C:\Users\Administrator\gamedb\target\release\gamedb.exe` — `search`/`read`/`graph`/`strings`/`sql`);
  AC Rogue `.data`/forge tooling (`anvil.py`, `forge.py`, `forge_patch.py`, `forge_append.py`);
  memory scripts (`memscan.ps1`, `memread.ps1`, `memwrite.ps1`, `memdump.ps1`).
- **Build:** `cmake --build build-msvc --config Release --target ac-rogue` (VS 2022 generator).
  New hook `.cpp` files are auto-globbed; re-run `cmake -S . -B build-msvc` if needed.


## 1. The mission (user's goals)
Mod Assassin's Creed Rogue (Steam) to:
1. **Combat:** counters have a **short, specific window to insta-kill**; miss the window → **normal block**;
   overall harder than base. (User asked for the window = **0.2 s**.)
2. **Shay's sword = single sword, one-handed (pickup-sword) moveset.** *(ACHIEVED — see §6.)*
3. **Hide the off-hand dagger** of the sword+dagger set (or if impossible, hide its mesh/texture).
   *(NOT achieved — see §7.)*
4. Enemies = musket infantry (already provided by the "AC Rogue Revived" patched `ACC.exe`; nothing to do).

User is happy with aggressive hacks (single-player, no anti-cheat). Keep it offline.

---

## 2. Environment
- Game: `D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue`, exe **`ACC.exe`** (x64, native
  AnvilNext), MD5 `a323729f3799a808c8148b695e1e23b8`. No anti-cheat. ASI loader + ReShade present.
- Saves/config: `C:\Users\Administrator\Documents\Assassin's Creed Rogue`.
- Mod work dir: `C:\Users\Administrator\Documents\Default Project\ac-rogue` (this folder). The workspace
  root is shared by several mods; each has its own folder + `MODLOG.md` (`ac-rogue`, `acc-coop`,
  `crash-twinsanity-psp`, `dishonored-rs`, `dishonored-vr-analysis`, `doi-ds3-passthrough`, …).
  The `AC.PatchFix` framework clone lives in this folder (`ac-rogue\AC.PatchFix`).
- AC Rogue tooling (this folder): `forge.py`, `forge_patch.py`, `forge_append.py`, `anvil.py`,
  `memscan.ps1`/`memread.ps1`/`memwrite.ps1`; backups in `forge_backups\`.
- **universal-modder** toolkit installed globally for OpenCode; skills available (`mod-any-game`,
  `reverse-engineering`, `game-automation`, `gamedb-cli`, …). `um` CLI: `C:\Users\Administrator\.local\bin\um.exe`.
  Guidance: `C:\Users\Administrator\universal-modder`.
- **Ghidra 12.1.4**: `C:\Users\Administrator\ghidra\ghidra_12.1.4_PUBLIC`. Analyze with `JAVA_HOME` =
  `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` and `GHIDRA_HEADLESS_MAXMEM=8G`
  (2 GB default **OOMs**). Project: `C:\Users\Administrator\ghidra-acc\ACC.Rogue`.
- **MSVC BuildTools 2022** (`cl.exe` 14.44) + **CMake** (`C:\Program Files\CMake\bin\cmake.exe`).
  No ClangCL, no Rust, no `uv`. **Cheat Engine 7.5** installed (CE breakpoints freeze hot functions —
  avoid; its `autorun` folder runs Lua at startup, `-luascript` is gated by a prompt).
- Ghidra helper scripts + dumps: `C:\Users\Administrator\ghidra_scripts\` (see §9).

---

## 3. Plugin (native ASI) — the thing that works
Base: **`playday3008/AC.PatchFix`** (public GitHub), cloned to
`C:\Users\Administrator\Documents\Default Project\ac-rogue\AC.PatchFix`. It is a per-game hook framework
(SafetyHook + Hooking.Patterns + mINI + spdlog) with a hook registry.

**MSVC patches already applied to the clone** (needed because upstream is clang-only):
- `core/src/logger.cpp`: `<flat_map>` → `<map>` (`std::flat_map` → `std::map`).
- `core/include/core/logger.hpp`: `consteval` → `constexpr` (2 places).
- `CMakeLists.txt`: added `/EHa` to `SHARED_COMPILE_OPTIONS`.
- `core/include/core/diagnostics/seh_guard.hpp` + `core/src/diagnostics/seh_guard.cpp`:
  refactored SEH guard (moved `__try` bodies into no-object helpers, added `guarded_call`).
- `games/ac/rogue/src/game_entry.cpp`: thunk-based `__try`.

**Build (target `ac-rogue`):**
```
cmake -S "C:\Users\Administrator\Documents\Default Project\ac-rogue\AC.PatchFix" -B "...\ac-rogue\AC.PatchFix\build-msvc" `
  -G "Visual Studio 17 2022" -A x64 -DPATCHFIX_BUILD_TESTS=OFF -DPATCHFIX_WERROR=OFF
cmake --build "...\AC.PatchFix\build-msvc" --config Release --target ac-rogue
```
Artifact: `build-msvc\bin\Release\AC.Rogue.PatchFix.asi`. Deploy: copy it over
`...\plugins\AC.Rogue.PatchFix.asi` (stock backup at `...\plugins\_backup_stock\`).

**How to add a hook (the pattern):**
1. `games/ac/rogue/include/games/ac/rogue/game_data.hpp`: add an `std::optional<uintptr_t>` field to
   `ResolvedAddresses` and a `scan_entries` row `{.name=..., .field=&ResolvedAddresses::x, .offset=0,
   .bytes="AA BB ??"}` (byte signature; `?` = wildcard).
2. New `hooks/<name>.hpp`: `HookTraits<Tag>` with `name`, `hard_deps`/`soft_deps`, `required_patterns`,
   `optional_patterns`, a `Config : config_base<Config>` (INI fields), `install(const Addrs&) -> bool`.
3. `hooks/<name>.cpp`: install a `mem::MidHook` via `mem::make_hook<Functor>(addr)`; in the functor read/
   write registers (`regs.rdx` etc.) or call `mem::write`. Guard with `registry().enabled<Tag>()` /
   `registry().config<Tag>().<field>.get()`.
4. Register the tag in `games/ac/rogue/include/games/ac/rogue/registry.hpp` `AllHooks`. Sources are
   globbed from `src/hooks/`.
5. Runtime log: `...\plugins\AC.Rogue.PatchFix.log`; hook journal: `...\plugins\AC.Rogue.PatchFix.journal`.
   INI: `...\plugins\AC.Rogue.PatchFix.ini` (section `[Gameplay]`, key `OneHandedSword`).
- **Watch out:** if ANY `required_pattern` is missing or a `make_hook` fails, the whole hook is marked
  failed and its `enabled<Tag>()` is false → silently no-ops (this bit us once).
- The current build only installs ~9-10/12 hooks; `CameraLean`, `MouseSmoothing` patterns don't match
  this exe and are skipped (unrelated to our work).

---

## 4. Current on-disk state (what's deployed right now)
- Deployed `.asi` = our build with **three targets** but the 3rd removed:
  `OneHandedSword` hooks **`FUN_141807200`** and **`FUN_141715160`** (both remap fight-type `7→1`).
  Installs cleanly; **single-sword moveset works** (user confirmed).
- Data edits (all currently present in `Extracted`):
  - `FightSettings` `2562_...FightSettings` (bin+XML): `TimeCounterInputIsValid 1.5→0.2`,
    `CounterOpenWindowRatio 0.7→0.4`, `AllNPCsFightCowards False→True` (test; revert via `.bak4`/`.bak3`).
  - `256_-_..._ShayDefaultSword_Secondary.data\0_-_..._Secondary.Entity`: byte **228** `1→0`
    (Visual `Active=False`) — **verified correct offset vs the Primary** (both have type hash
    `29 8d 65 ec` at 224; Primary byte 228 = `01`).
  - `...\4_-_CHR_W_Dagger_Axe.Material`: byte **73** `0→1` (`MaterialDisabled=True`) — mapping verified
    against the XML bool order.
  - Backups: `*.Entity.bak`, `.bak2`; `4_-_CHR_W_Dagger_Axe.Material.bak`; `*.xml.bak`;
    `2562_...FightSettings.bak`, `.bak3`, `.bak4`.
- **None of the data edits had any in-game effect** (counter unchanged; dagger still shows).
  The **plugin (code) edits DO take effect** — that's the key asymmetry.

---

## 5. THE OPEN QUESTION (do this first in the new session)
The **`DataPC.forge` repack may not be reaching the game.** `DataPC_patch.forge` was checked — it is
menu/UI/localization only (no bootstrap/weapons), so **no override**.

**Decisive test (ATK localization route):**
1. ATK → `DataPC.forge` → unpack `59_-_LocalizationPackage_English.data`.
2. Export it to XML, change a visible string (e.g. `Options` → `OPTIONSX`), Import it.
3. Repack `DataPC.forge`. Launch, look for the changed word.
- **Changed** → pipeline works ⇒ our gameplay targets were wrong; find the *real* ones.
- **Unchanged** → the forge repack is broken; diagnose the ATK repack/launch path.

Also possible: the game reads the settings/entities from a **different forge** (e.g. `DataPC_extra.forge`
or `DataPC_extra_chr.forge`), or the fight settings come from the **save/difficulty** rather than
`FightSettings`.

---

## 6. Working feature — single-sword moveset (how it was achieved)
Weapon/moveset chain (all RVAs, image base `0x140000000`):
```
entity WeaponType → FUN_1417153e0 (class getter; HUD-only, remapping it did NOTHING)
→ FUN_1414a6270 (class→fight type) → FUN_1420f3d20 (applies) → player+0x218
```
What DID work: MidHooks remapping the fight type `7 (DualWield) → 1 (Sword)` at:
- `FUN_141807200` (entry; stores type at `char+0x218`, then calls `FUN_1418041f0`)
- `FUN_141715160` (entry; sets the player's weapon pose/class on the weapon object)
Both use the same functor: `if (regs.rdx & 0xffffffff) == 7 → regs.rdx = 1`.

Enums (exact):
- **WeaponType** (`FUN_1414a63c0`): 0 Unarmed,1 Medium,2 Small,3 Heavy,4 Long,5 Musket,6 Blunt,**7/8 Dual Wield**,
  9 Machete,0xb Hidden Blade,0xc Medium Blunt,0xd Crossbow,0xe/0x1a holster pistols,0xf Bow,0x10 Throwing dagger,
  0x11 Arrow,0x12-0x15 blowpipe,0x16 Rock,0x17 Gun,0x18 AppleOfEden,0x19 RopeDart,0x1b Explosive,0x1c LeftHandKnife,
  0x1e/0x1f up-holster pistols,0x22-0x28 air-rifle ammo,0x2a MaxType.
- **Weapon class** (`FUN_1410234b0`): 0 Unarmed,1 AssassinBlade,2 Sword,3 Heavy,4 Dagger,5 Long,6 CrossBow,
  7 Musket,8 Blunt,9 DualWield,10 Machete,0xb SwivelGun.
- **class from WeaponType** (`FUN_1414a6300`): 1→2,2→4,3→3,4→5,5→7,6→8,**7|8→9**,9→10,0xd→6,0x20→0xb.
- **fight type from class** (`FUN_1414a6270`): 1→0xb,2→1,3→3,4→2,5→4,6→0xd,7→5,8→6,**9→7**,10→9,0xb→0x20.

Key function bytes (for signatures):
- `FUN_141807200`: `40 53 48 83 EC 20 8D 42 FF 48 8B D9 83 F8 0B 76 04 85 D2 75 43 0F B6 81 1C 02 00 00 84 C0 74 33`
- `FUN_141715160`: `40 53 55 48 83 EC 28 48 8B 81 E8 01 00 00 41 0F B6 E8 8B DA 48 8B 48 08`
- `FUN_1420f3d20`: `40 55 57 41 54 48 83 EC 40 45 8B E0 8B EA 48 8B F9 41 83 F8 02 75 09 83 FA 19`
  — **SafetyHook cannot hook this** ("inline hook failed"); an entry MidHook on it hung startup. Avoid it.
- `FUN_1417153e0` (class getter): `40 53 48 83 EC 20 48 8B 81 E8 01 00 00 C7 44 24 30 01 00 00 00 48 8B D9 48 8B 48 08`
- `FUN_14102e960`, `FUN_14185cc40` (CounterFail, state 0x19), `FUN_141845e60` (Parry, state 0x13),
  `FUN_141849470` (GrabCountered, state 0x3f), `FUN_14185e990` (weapon setup, state 0x26),
  `FUN_141047ed0` (combat **telemetry**, not gameplay), `FUN_1420f1850` (fight manager),
  `FUN_1414a5e90`, `FUN_1400c09a0`, `FUN_1418041f0` (apply anim set), `FUN_14132d410` (type→component id).

---

## 7. The off-hand dagger problem (NOT solved)
Goal: hide the dagger of Shay's sword+dagger set (game has **no inventory**; weapons are fixed
"sword and dagger sets"). Tried, all failed:
- `ShayDefaultSword_Secondary.Entity` Visual `Active=0` (byte 228) — no effect on the **held** model.
- `CHR_W_Dagger_Axe.Material` `MaterialDisabled=1` (byte 73) — no effect.
- A plugin hook on `FUN_1420f3d20` (the `+0x400(…,2)` off-hand set) — **cannot hook**.
⇒ The held weapon mesh likely comes from elsewhere: **suspect the player character buildtable**
(`CHR_P_Shay*` in `DataPC_extra_chr.forge`) or a weapon `ObjectPack`/`BuildTable`, not the weapon
entity's Visual. **Next lead:** find `CHR_P_Shay` buildtable / weapon attachment and how the sword+dagger
meshes are attached; or hide via a texture if the attach can't be broken.

---

## 8. Combat/stealth research summary (full detail in COMBAT_STEALTH_RESEARCH.md)
- Player combat state id at `player+0xaf8`: 0x13 Parry, 0x19 CounterFail, 0x3f GrabCountered, 0x26 weapon setup.
- Combat is dispatched through **`Fight*ActionMap` data graph**; `CounterWindowSettings` is a reflected type
  with **no data-file instance found** and no code xref. `FightSettings` timing fields are in
  `49_-_Game Bootstrap Settings.data\2562_...FightSettings` (the ones we changed had no effect).
- Fight pacing tiers: `FightPacingSettings[0]` = "Low Health Setting" (used below 25% health),
  `[1]` = **"Basic Setting"** = the active normal tier (`Current/Initial/OneOnOneFightPacingSetting = 1`).
  Each has `Counter*DecisionOffset`, `OpenDefense*`, `FightActions*Delay`, etc.
- AI: `FUN_14010ee00` builds the AI global pipeline (AIGlobalUpdateStep1/2/3, **PerceptionManager**,
  PathManager, Coordinator); NPC combat AI is a behaviour graph built by `FUN_1417d1ff0`.
- Stealth: stance namer `FUN_141022070` (Stalking/Blended/Cover/Haystack…), player state code
  `FUN_1401a5590`; detection predicates `FUN_141435370`/`FUN_14132ddc0`/`FUN_1414351b0`/`FUN_141353260`;
  vanish `FUN_141ebc6e0` ("[Blend Action] Toggle Player Vanish"); hide-spot `CLSearchHideSpot*`.
  Crouch/stalking engine events exist (`ActivityCrouch`, `ActionBlockCrouching`, `RestrictCrouchingEvent`)
  but **no crouch input action** exists.

---

## 9. Reverse-engineering assets
- Indexes (grep-able): `ghidra_scripts\acc_functions.txt` (all functions `addr size name`),
  `acc_strings.txt` (`addr<TAB>text`), `acc_string_refs.txt` (`funcAddr name<TAB>strAddr<TAB>text`).
- Reusable scripts: `DumpAll.java`, `FindStrings.java`, `DecompileList.java` (reads `targets.txt`),
  `CallersList.java` (reads `callers_targets.txt`), `GetBytes*.java`, `WeaponTypePath.java`.
- Run pattern:
  `analyzeHeadless.bat C:\Users\Administrator\ghidra-acc ACC.Rogue -process ACC.exe -noanalysis -postScript <script>`
  (with `JAVA_HOME` + `GHIDRA_HEADLESS_MAXMEM=8G`).
- Output dumps: `decomp_set.txt`, `callers_set.txt`, `callers_decomp.txt`, `strings_out.txt`, etc.
- The exe has **no field-name strings** (only type names like `FightSettings`); ATK's XML is how you see
  field names, and the game reads fields by offset.

---

## 10. AnvilToolkit (ATK) workflow that's in use
- ATK 1.3.6 in the game folder. `Extracted\` holds unpacked forges (currently `DataPC.forge` +
  `DataPC_extra_chr.forge` + now `DataPC_patch.forge`).
- Edit files under `Extracted\<forge>\Extracted\<name>.data\...`; then **repack the `.data`**, then
  **repack the forge**. User does this via the GUI. `.xml` and `.bak` are in `IgnoredExtensions`
  (`CompileXMLWhenRepacking=False`), so **binary edits** are what usually get packed — but XML is also
  edited when we want the schema value visible.
- `.Entity`, `.Material`, `.FightSettings`, `.FightStrategyManager` all export to XML; **Entity Import was
  NOT available** in this ATK build (so we binary-patch entities/materials directly).
- Save safety: `um backup create "C:\Users\Administrator\Documents\Assassin's Creed Rogue" --name rogue-saves`.

## 11. Gotchas
- Do not MidHook `FUN_1420f3d20` (fails/hangs). Do not CE-breakpoint hot combat functions (freezes).
- A failed required pattern disables the whole hook silently.
- Ghidra headless needs 8 GB heap or it OOMs and the .bat sits at "Press any key".
- A stuck `ACC.exe` can make Steam refuse to relaunch — kill by PID.
- Watch for leftover `*.Entity.bak*`, `*.xml.bak*`, `*.FightSettings.bak*` files when repacking (they're
  ignored by ATK, but keep track).
