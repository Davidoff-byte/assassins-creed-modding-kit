# Co-op plugin — code review (2026-10-08)

Scope: `games/ac/blackflag/src/coop/*`, `hooks/player_transform.cpp`, `hooks/cam_probe.cpp`,
plus the netcode. Method: full-file read of `ghost_body.cpp` and `coop_net.cpp`, targeted
reads of the hook entry points, cross-checked against crash dumps and live logs.

## Fixed in this pass (build 2026-10-08 12:49)

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | **critical** | `ghost::tick` runs on the game thread while config setters (`set_enabled`, `set_params`, ...) run on the ini file-watcher thread. `set_enabled(false)` clears `g_body` while `tick` could be mid-use -> read/write through address 0x10 -> crash. | `std::mutex g_drive_mtx` guards `tick` and all setters. |
| 2 | **critical** | Network samples (`remote.px/py/pz/qx..qw`) were used unvalidated in matrix math and passed to the engine setter. A malformed/NaN packet propagates NaN into the engine scene graph. | `std::isfinite` guard on all seven floats before any use. |
| 3 | high | Path-replay: after a >20 m snap the ghost lerped back through up to 1.5 s of stale delayed samples (rubber-band). | On snap, fast-forward the whole replay buffer to the new position. |
| 4 | high | `scan_step` could spend the whole frame scanning (8 MB of 4-byte compares) during re-picks -> frame hitches. | Time budget: at most ~2 ms of scan per tick, then the frame is handed back. |
| 5 | high | The private despawn-pin vtable page stayed `RWX` after setup. | `VirtualProtect` to `RX` once written (writes happen only at setup). |
| 6 | med | Engine-setter path did `memcpy(g_body + 0x10, ...)` with only start-of-tick validation; a mid-tick free could fault. | `readable(g_body + 0x10, 0x40)` re-check before the setter; the warp-detector block got the same guard. |
| 7 | med | Adoption wrote the fake vtable without a final readability check. | `readable(g_body, 4)` before the write. |
| 8 | med | `g_resist` could carry a stale count across body drops. | Reset on every loss path. |
| 9 | med | Netcode: a failed UDP bind left the plugin offline until the next ini poke (the per-restart port-hop dance). | `SO_REUSEADDR` + a 2 s background bind-retry driven by the per-frame `publish`/`poll` calls; `shutdown()`/success clear it. |

## Known remaining risks (documented, accepted for now)

- **Matrix tearing**: the body's transform rows are also touched by engine job worker threads.
  Our read-modify-write of a matrix row can interleave with theirs. Effects are visual-only
  (a single-frame glitch); the engine performs the same class of updates internally.
  Mitigation would need engine-side quiescing (not worth it yet).
- **Pinned-body leak**: a body dropped after our pin stays allocated forever (its delete slot
  is a stub). Bounded (one body per drop), ~1-2 objects per hour of play. Acceptable.
- **Trust model**: the netcode accepts packets from any sender with the right magic/version
  (LAN/offline co-op intended). A hostile LAN peer could inject state. Out of scope.
- **Disabled machinery**: `CloneTest`/spawn-replay probes and `AnimDrive` stay config-gated
  off; they crash-prone by nature of their experiments and must only run in dedicated
  sessions with logging.
- **CullWatch/StateProbe**: read-only samplers; capped log volume (4000 entries).

## Architecture notes (for the spawn route)

- Body classes: base vtable `0x1E4CE90`; spawn system mapped in RE-NOTES (classes = CRC32
  names, `Entity = 0x0984415E`, template catalog 3584, manager `*(world+0x924)`).
- Recipe to finish: spawn Entity with a real key pair, feed deserialize + registration,
  then reuse: def-swap (Duncan look) + despawn pin (persistence) + the driver.
- All three pillars are already built and proven in the current route; the spawn route only
  changes where the body comes from.
