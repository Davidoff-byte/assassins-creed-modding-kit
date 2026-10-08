# Our changes to AC.PatchFix

`plugin/` is a **modified working copy** of [playday3008/AC.PatchFix](https://github.com/playday3008/AC.PatchFix)
(MIT — see `LICENSE`). Upstream supports AC Rogue and AC Syndicate with display/QoL fixes, built
with clang. We added a second game, a 32-bit target, the co-op features, and the ability to build
it on a stock MSVC toolchain.

If you want the pristine upstream, clone it from GitHub. This tree is what *we* actually built and
ran in-game.

## Build changes

- Built with **MSVC BuildTools 2022 + CMake** (upstream toolchain is clang-cl/VS2026). To make it
  compile on MSVC we patched:
  - `flat_map` → `map` where MSVC's STL refused it,
  - `consteval` → `constexpr`,
  - added `/EHa` to the compile options,
  - refactored the SEH-guard thunk.
- **x86 core support** — the core's exception/stack-walk/protect paths were hard-wired x64; they now
  compile and work for 32-bit targets as well (needed by Black Flag; relevant to AC1 if you ever
  hook it — it's 32-bit MSVC too).

Typical build (from `plugin/`):

```sh
cmake -S . -B build-msvc -G "Visual Studio 17 2022" -A x64 -DPATCHFIX_BUILD_TESTS=OFF
cmake --build build-msvc --config Release --target ac-rogue
# 32-bit:
cmake -S . -B build-x86 -G "Visual Studio 17 2022" -A Win32 -DPATCHFIX_BUILD_TESTS=OFF
cmake --build build-x86 --config Release --target ac-blackflag
```

Output: `build-*/bin/Release/*.asi`. Deploy to `<game>/plugins/` with an ASI loader
(`dinput8.dll`) in the game root. **Never keep backup `.asi` files inside the game folder** — the
loader recurses subfolders and loads them all (see the root README gotchas).

## Rogue target (`games/ac/rogue/`) — what we added

- `hooks/player_transform.*` — samples the player body position + orientation every frame from the
  engine's own PlayerPosition path; RVA-addressed; all pointers `VirtualQuery`-guarded.
- `hooks/player_probe.*` — actor/component enumeration diagnostics.
- `hooks/hijack_avatar.*` — drives a donor actor from a network position (superseded on BF by the
  character-node route; kept for the write-up).
- `hooks/debug_spawn.*` — calls the retail exe's debug "Spawn Dude" handler (proved the handlers
  run; the spawned objects are per-frame debug markers, not characters).
- `hooks/set_transform.*` — the interface-0xD set-world-transform path (debug-scoped; see notes).
- `hooks/weapon_class.*` — the one-handed sword remap (ship feature).
- `coop/coop_net.*` + `coop/coop_proto.hpp` — UDP transport + protocol v2.
- `registry.hpp` / `registry.hpp.full` — `registry.hpp` is the shipped config (co-op hooks);
  `.full` keeps the parked combat hooks registered, for reference.
- Upstream's display features (FOV, FPS, ultrawide, language unlock, …) are untouched.

## Black Flag target (`games/ac/blackflag/`) — new, x86

- `hooks/cam_probe.*` — safe per-frame camera hook used to bootstrap all other reads.
- `hooks/player_transform.*` — player body read + action-state packing + UDP publish.
- `coop/coop_net.*`, `coop/coop_proto.hpp` — same protocol, x86 build.
- `coop/ghost_body.*` — the co-op ghost: picks a humanoid crowd node and drives its matrix from
  the peer's packets (this is the feature that made a visible second character).
- `coop/combat_sync.*` — combat/event sync experiments.
- `coop/overlay.*` — in-game overlay for co-op state.
- `game_data.hpp` — the RVA/pattern table for this exe build (pinned; BF SP
  `AC4BFSP.exe` MD5 `2058342866688F780C8B34526A65BC35` — the exact pins for both BF exes are in
  `docs/blackflag-coop/MODLOG.md`).

## Parked hooks (`excluded-hooks/`)

The Rogue combat experiments, removed from the build but kept for reference:
`counter_window`, `counter_probe`, `counter_gate`, `combat_tweaks`, `ai_pacing`, `knife_grant`,
`knife_probe`, `combat_trace`. Their story (why they don't solve the counter window) is in
`docs/rogue/COMBAT_STEALTH_RESEARCH.md` and the Rogue MODLOG — read those before reviving any of
them.

## Diagnostics (from upstream, worth knowing)

Crash reports + minidumps + a hook journal are written to the game directory; a fault inside one
hook callback disables only that callback ("Hook callback crashed — permanently disabled") and the
game keeps running. That fault isolation is why we could iterate on live games at all — keep it in
mind when writing new hooks: put each experiment in its own hook.
