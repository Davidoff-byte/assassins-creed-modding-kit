# Assassin's Creed — modding & RE work (Rogue, Black Flag, and the Anvil family)

A snapshot of everything we built for the Assassin's Creed games.

No game files are included anywhere in this repo, and nothing here ships any. Every tool reads
*your own* copy of the game, and the two mods in `mods/` edit *your own* `DataPC.forge`.

---

## Contents

| Path | What it is |
|---|---|
| `docs/rogue/` | AC Rogue mod journal, combat/stealth research, hand-off notes, Nexus page drafts |
| `docs/rogue-coop/` | Rogue co-op: journal, plans, RE notes, two-machine test sheet |
| `docs/blackflag-coop/` | Black Flag co-op: full journal, plans, code review, crash analysis, overnight reports |
| `docs/coop-project-plan.html` | the co-op project dashboard (open in a browser) |
| `tools/rogue/` | Rogue `.forge` (v27) reader, in-place patcher, `.data` container reader (LZO), live-memory scripts, ATK wrapper |
| `tools/coop/` | co-op protocol v2 (`coop_proto.h`), fake peer, playback/interpolation rig |
| `tools/blackflag/` | ~248 live-RE scripts (PowerShell/Python/C#) + QuickBMS scripts for scimitar archives |
| `tools/ghidra/` | reusable Ghidra scripts used across both projects |
| `plugin/` | working copy of AC.PatchFix: MSVC fixes, x86 core port, Rogue **and** Black Flag targets, co-op features, parked hooks (`plugin/excluded-hooks/`) |
| `mods/` | the two shipped Rogue mods — One-Handed Sword, Hidden Dagger |
| `knowledge/` | agent field notes: AC-family tooling survey, Rogue internals, BF transform + co-op ghost |

## Where to start

- **Co-op story, end to end:** `docs/blackflag-coop/MODLOG.md` (journal) →
  `docs/blackflag-coop/RE-NOTES.md` (current facts) →
  `knowledge/blackflag-coop-ghost-avatar.md` (one-page summary).
- **Data pipeline:** `tools/rogue/forge.py` + `tools/rogue/anvil.py`,
  and the "big unlock" section of `docs/rogue/MODLOG.md`.
- **Reusable native-mod technique:** `plugin/` plus `plugin/OUR-CHANGES.md`.

---

## The projects, one screen each

### 1. AC Rogue — mod + data pipeline (shipped)

Two released mods (in `mods/`, zips are self-contained):

- **One-Handed Sword** — remaps the player's weapon class so Shay fights with the single-sword
  moveset; a plugin hook, toggleable in the INI.
- **Hidden Dagger** — hides the off-hand dagger on all sword sets; a pure `.forge` data edit
  (Python installer edits your own `DataPC.forge`).

Tooling built along the way (`tools/rogue/`):

- `forge.py` — AnvilNext `scimitar` **forge reader, version 27**. Validated against 330 entries of
  Rogue's `DataPC.forge`; resolves names, offsets, sizes.
- `forge_patch.py` — **in-place blob replacement** inside a forge (same or different size).
  Proven with an A/B experiment: swapping the *active* localization package hangs the game, an
  inactive one doesn't — i.e. the modded forge *is* what the game loads. (See the journal.)
- `forge_append.py` — grow the forge and repoint an entry; the game loads it.
- `anvil.py` — **`.data` container reader** (LZO1X blocks, TOC form). Reads localization packages,
  weapon resources and the 46 MB `Game Bootstrap Settings` (20,988 resources). Reverse-engineered
  from AnvilToolkit 1.3.6's own code.
- `memscan.ps1` / `memread.ps1` / `memwrite.ps1` — live process memory scan/read/write
  (P/Invoke, no debugger attach needed).
- `atktool/` — small .NET wrapper around AnvilToolkit's own `DataFile` (needs ATK 1.3.6 DLLs).
- Plus the scan/verify helpers (`bin_diff.py`, `find_float.py`, `scan_*.py`, `resolve_sigs.py`, …)
  and `re_scratch/` with the raw pipeline experiments.

Research (`docs/rogue/COMBAT_STEALTH_RESEARCH.md` + journal): weapon-class chain, stance names,
the engine's crouch machinery, and the full counter-window investigation — the conclusion there
was **"this is a data wall, not a code lever"**, with all the evidence for why (FightSettings live
writes, event-driven fight-action state machine, action-map dispatch). If you ever hack on fight
feel, read that first; it saves days.

### 2. Rogue + Black Flag co-op — the big one

Goal: two-player free-roam co-op (parkour together) over Radmin VPN, in the single-player games
(no netcode shipped — it had to be synthesised).

**What worked:**

- **Player transform read** — Rogue (x64) and Black Flag (x86): engine's own PlayerPosition path,
  crash-safe pointer reads; streamed over a small UDP protocol (`tools/coop/coop_proto.h`, 72 B
  player packet with position + quaternion).
- **Interpolation rig** (`tools/coop/playback_rig.py`) — render ~100 ms in the past, extrapolate on
  loss: ~6× smoother than naive playback on a real capture.
- **Black Flag: a visible ghost avatar.** Identified the character-node class by signature
  (vtable + marker + a humanoid flag + child count), then wrote the node matrix from UDP packets —
  a crowd NPC walks around as the peer. User-confirmed on two machines over Radmin.
- **The engine's own clone/spawn recipe** — character class descriptor + clone (sync = job-posting
  chain; async = serialize + post = a complete renderable character). Parked project, but the
  recipe is written down.
- **Action/behaviour machine mapped** — `BhvAssassin` family: the action writer, the per-frame
  machine, the request slots to command actions (climb/vault), and the read-side fields
  (phase / hang / flags) that are already in the protocol.

**Tooling of note inside `tools/blackflag/`:**

- `bp-capture-param2.ps1` — a **WOW64 PowerShell debugger**: INT3 breakpoint, single-step re-arm,
  captures a wanted register/pointer, clean detach. (Gotcha inside: WOW64 breakpoints arrive as
  `0x4000001F`, not `0x80000003`.)
- `watch-writer.ps1` — hardware **write-watchpoints** (DR0–DR7, all threads) that find *who* writes
  a field, with EIP + registers. This is how the action writer was caught.
- `puppet-test.ps1` / `drag-body-test.ps1` / `shove-edward-and-burst.ps1` — drive/puppet tests.
- `scan-npcs.ps1`, `sample-looks.ps1`, `outfit-probe.ps1` — the (parked) model/outfit-swap project;
  the write-and-revert probes conclusively ruled out runtime field writes.
- `bms/*.bms` — QuickBMS scripts for the scimitar archive format (extract-only).

The Rogue co-op notes (`docs/rogue-coop/`) share the protocol/rig work and its dead ends
(debug-spawn objects are transient; actors are not the teleport `char`; the set-transform path is
debug-scoped). The BF project then found the real character-node route — read both, the contrast
saves time.

### 3. The plugin framework (`plugin/`)

`plugin/` is a modified working copy of **playday3008/AC.PatchFix** (MIT). Ours:

- **MSVC 2022 build fixes** (the upstream targets clang): `flat_map`→`map`, `consteval`→`constexpr`,
  `/EHa`, SEH guard thunk refactor.
- **x86 core port** so the framework runs on 32-bit titles (that's Black Flag; if you ever put a
  native hook into AC1, it's 32-bit too — this is the starting point).
- **Rogue target additions**: player transform/probe, avatar hijack, debug spawn, set-transform,
  co-op net, weapon class — plus upstream display features.
- **Black Flag target** (new): camera probe, player transform read, co-op net, ghost body driver,
  combat sync, an overlay.
- **`plugin/excluded-hooks/`** — the parked combat hooks (counter window/probe/gate, combat tweaks,
  AI pacing, knife probes). `registry.hpp.full` next to `registry.hpp` shows how they were wired in.
- See **`plugin/OUR-CHANGES.md`** for the full list and build instructions.

### 4. `knowledge/` — the distilled field notes

Four short notes written during the work (front matter included):

- `ac-family-modding-survey.md` — the AC-family modding ecosystem: what tools exist per title
  (ACUFixes, ACExplorer, AnvilToolkit, ScriptEngine), who shipped multiplayer, and why co-op
  prior art doesn't exist.
- `rogue-anvilnext-internals.md` — Rogue co-op internals: task graph, player transform, debug
  cheat system, set-transform path, entity ids.
- `blackflag-player-transform.md` — reading the player's world transform/body in BF (x86).
- `blackflag-coop-ghost-avatar.md` — the co-op ghost, the node class, the spawn/clone recipe.

---

## Gotchas worth more than the code (all learned the hard way)

1. **ASI loaders recurse subfolders.** Backup `.asi` files inside `_backup/` folders *load too* —
   we had 8 copies of a plugin loaded at once (only half the hooks installed, weird faults).
   Keep backups out of the game folder entirely.
2. **The pattern scanner's wildcard is one `?` per byte.** `??` parses as two wildcard bytes and
   silently matches nothing.
3. **Guard every pointer with a readability check** (`VirtualQuery`) before dereferencing from a
   hook. A fault inside a callback permanently disables it — validate first, then read.
4. **An unkillable game process can wedge a relaunch** (windowless, taskkill says "no running
   instance"). It clears only on reboot. Design tests for one launch per boot when live-tuning.
5. **Wrong-thread engine calls deadlock, they don't crash.** Calling the clone from a worker
   thread hung in a TLS job-context init while the game kept running. Engine creation/
   deserialisation must run on the engine's own thread/job queue.
6. **Game pauses when it loses focus.** Any memory scan during an alt-tab sees a frozen world —
   wait for movement or keep the game focused.
7. **D3D overlays crash games randomly.** ReShade/Bandicam/Fraps gave us `0xC0000005` inside
   `D3D11CreateDeviceAndSwapChain` — nothing to do with the mod. Rule them out before debugging.
8. **A "field diff" can lie.** MSVC folds identical vtables (same vtable ≠ same layout), and
   dynamic fields can look "shared across variants". Sample twice; probe with write-and-revert.
9. **Some nodes are exactly 0x100 bytes.** Everything past the end is the *neighbouring* heap
   allocation — easy to misread as fields (we did, twice).
10. **Engine type names can be reflection-only** — no code xrefs, by design (spawn types, skin
    components). Grep won't find them; go through the data/registry instead.

## Running the tools

- Python: 3.11+ (most scripts are dependency-free; some use only stdlib).
- PowerShell scripts: Windows PowerShell 5.1, run with `-ExecutionPolicy Bypass -File`.
- Ghidra scripts: Ghidra 12.1.4 + JDK 21, headless
  (`analyzeHeadless -noanalysis -postScript …`). Bump `GHIDRA_HEADLESS_MAXMEM` (x86 big exes OOM
  at 8 GB — we used 20 GB).
- `tools/rogue/atktool` needs AnvilToolkit 1.3.6's DLLs beside the exe.

## Ground rules

- No game files here, ever — and none of the tools ship any. Everything reads your own installs.
- Produced against the owner's own Steam copies of Rogue and Black Flag; single-player/offline
  only. No anti-cheat was involved or worked around.
- Educational/personal use; the RE notes exist so people can mod their own copies.

## Credits

- **AC.PatchFix** — playday3008 (MIT). `plugin/` is a modified working copy.
- **Ultimate ASI Loader** — ThirteenAG.
- **AnvilToolkit** — Kamzik123 (+ the ATK resource community).
- **QuickBMS** — Luigi Auriemma (the `.bms` scripts here are ours).
- **SafetyHook**, **Hooking.Patterns** (lethal.org) — used by the plugin framework.
- **Ghidra**, **IDA**, **gamedb** — the analysis side.
- Field notes were produced with the `universal-modder` agent toolkit.

*Endpoints in the journals are placeholders (`[Radmin IP]`); the live ones were redacted.*
