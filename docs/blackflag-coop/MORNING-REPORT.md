# BFCoop — overnight report (2026-10-05 → 06)

> **Historical snapshot** (the night B1 was confirmed and B3 anchored). For the current state see
> `PLAN.md` (status + design) and `RE-NOTES.md` (CURRENT TRUTH box); the co-op avatar was first
> confirmed visible the following afternoon (MODLOG, 2026-10-06).

## Headline

**B1 is confirmed: our plugin runs inside Assassin's Creed IV Black Flag and reads a live transform.**
**And B3 got its first confirmed anchor: the player's world body position.**

```
PlayerTransform: base 0x400000 hook 0x63BBB0
PlayerTransform: installed
CamProbe: installed
Initialization complete: 2/2 enabled hooks installed (2 total)
PlayerTransform: pos=(-536.8,281.0,2.8) → (-490.3,358.7,3.3)   ← walking, in-world
PlayerTransform: quat=(-0.019,-0.018,0.675,0.738)              ← valid unit quaternion
```

## B3 CONFIRMED: the player's body position

Walk-and-turn test (4 Hz capture):

| Phase | offset `cand − cam` | Reading |
|---|---|---|
| Walking straight | `(-0.3, -2.8, -0.6)` rock stable | body + camera move 1:1 |
| Turning | swings `(-0.3,-2.8) → (2.5,0) → (0.5,+2.3)` | camera **orbits a fixed point** |

⇒ **`camobj+0x68 → object+0x50` is the player's world body position.** Stable object across 340
samples. Chain: `mgr (0x02abe588) → +0x4C → holder → camobj → +0x68 → obj → +0x50`.

## What was built

1. **The patch framework now builds for x86.** Four arch-specific files ported; x64 Rogue untouched.
2. **Game target `games/ac/blackflag`** (`ARCH x86`): game_data (`AC4BFSP.exe`), registry, entry,
   `PlayerTransform` hook, ported `CoopNet` transport, and `CamProbe` discovery hook.
   Artifact: **`AC.BlackFlag.PatchFix.asi`, 1,069,568 B (latest), i386**.
3. **Deployed** behind **Ultimate ASI Loader v9.7.4 (x86)**: `Black Flag\dinput8.dll` +
   `Black Flag\plugins\AC.BlackFlag.PatchFix.asi` + `.ini`.
4. **Saves backed up** (`ac4-saves`, 46 files, 15.9 MB).
5. **Enhanced probe deployed** (second half of the night): `CamProbe` now also dumps the camera
   target object's **vtable and every pointer field (with their vtables)** — so the next run
   identifies the *class* of the player object.

## Signature discovery

- Camera manager global **`0x02abe588`** (RVA `0x026BE588`); camera object **`**(mgr+0x4C)`** with
  position `+0x10`, orientation `+0x20`; camera position globals `0x02abe530` / `0x02abe540`.
- Ring writer `FUN_005062e0`: `manager+0x130` (`%5`) → `+0x90 + idx*0x10`.
- **Camera target** at `camobj+0x68`; player body position at `target+0x50`.
- **Dead ends confirmed** (don't re-chase): spawn type-names have **no code xrefs**
  (reflection-only); `g_MainPlayerPosition` is a **shader uniform**, not a global; engine RTTI is
  partial (mostly Havok/third-party), so classes must be identified via **vtables**, not names.

## Bug found and fixed

Camera-manager RVA was `0x26ABE588`; correct is **`0x026BE588`** (`0x02abe588 − 0x400000`).
The bad address failed safely (null manager, no crash).

## Next session (one run)

1. **Launch + load a save.** The enhanced probe logs the target object's vtable and pointer fields.
2. I look up that vtable in Ghidra → **class identity** → the owning **character entity**.
3. Match the entity against the BF MP oracle's replicated fields
   (`0x80/0xe8/0x128/0x1f8/0x170`, move-mode `+0x398`).
4. **Controlled write test** (with you present, in case it crashes): nudge the body position and see
   if the player moves — that proves "drive a character", the core of B3.

## State / files

- Logs: `bf-coop/logs/b1-confirmed-*.log` (633 KB), `b3-inworld-*.log` (106 KB).
- Detail: `bf-coop/RE-NOTES.md` §4–§6, `bf-coop/MODLOG.md`, tracker `PROJECT-PLAN.html`.
- Operational: launches need **Ubisoft Connect** running (`upc.exe`), else the game silently won't
  start. The plugin log **rotates at ~1 MB** — copy it out if you need a long capture.


## What was built

1. **The patch framework now builds for x86.** Four architecture-specific files were ported
   (`crash_report.cpp`, `crash_handler.cpp`, `stack_walker.cpp`, `protect.cpp`); the x64 Rogue build
   is untouched.
2. **New game target `games/ac/blackflag`** (`ARCH x86`): game_data (`AC4BFSP.exe`), registry,
   entry point, the `PlayerTransform` hook, the ported `CoopNet` UDP transport, and a read-only
   `CamProbe` discovery hook. Artifact: **`AC.BlackFlag.PatchFix.asi`, 1,067,520 B, i386**.
3. **Deployed to Black Flag** behind **Ultimate ASI Loader v9.7.4 (x86)**:
   - `Black Flag\dinput8.dll`
   - `Black Flag\plugins\AC.BlackFlag.PatchFix.asi`
   - `Black Flag\plugins\AC.BlackFlag.PatchFix.ini`
4. **Saves backed up** (`um backup` → `ac4-saves`, 46 files, 15.9 MB).

## Signature discovery (the useful RE)

- **Camera manager global `0x02abe588`** (RVA `0x026BE588`), found via its reader
  `FUN_0063ba70` (first callee of `Ai::UpdateCamera` = `0x0063bbb0`).
- **Ring confirmed by its writer** `FUN_005062e0`: advances `manager+0x130` (`%5`), writes the
  transform to `+0x90 + idx*0x10`; quaternion ring `+0xE0`.
- **Camera position globals `0x02abe530` / `0x02abe540`** (vec4), produced by `FUN_0040bea0`,
  written by `FUN_00417650` from the camera object.
- **Camera object** = `**(u32**)(manager+0x4C)`; position `+0x10`, orientation `+0x20`.
- **Candidate player entity**: `FUN_0071ba10` stores a *focus entity* at `obj+0x914`.
- **Correction:** `g_MainPlayerPosition` is a **shader uniform** name, not a code global.
- **Dead end repeated from Rogue:** spawn type-names (`PlayerSpawnEvent`, `SpawnPlayerParams`, …)
  have **no code xrefs** (reflection-only).

## Bug found and fixed

My camera-manager RVA was `0x26ABE588`; the correct value is **`0x026BE588`**
(`0x02abe588 − 0x400000`). The wrong address failed safely (null manager, no crash). Fixed, rebuilt,
redeployed, and confirmed.

## State to resume from

- **The game is running at the main menu with `CamProbe` armed.** Loading a save will capture the
  in-world transform plus a scan for candidate player/character objects.
- No launch wedge occurred. (Two launches silently failed until **Ubisoft Connect** was running —
  if the game won't start, launch `upc.exe` first.)

## Next steps (in order)

1. **Load a save** (press Continue). Confirm B1 "tracks walking", and read the `CamProbe` output for
   the player/character object — that is the **B3** evidence we need.
2. **B2**: two machines on Radmin VPN — set `RemoteIp1..4` in the ini on both, look for `peer=1`.
3. **B3**: pick the candidate character object, match the BF MP oracle's replicated fields
   (`0x80/0xe8/0x128/0x1f8/0x170`, move-mode `+0x398`), and try driving a second body.

## Where the detail lives

- `bf-coop/RE-NOTES.md` (§4 camera path, §5 B1 confirmed + camera object chain)
- `bf-coop/MODLOG.md` (overnight entry)
- `PROJECT-PLAN.html` (tracker — B1 now marked Verified)
