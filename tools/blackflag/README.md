# bf-coop tools

All scripts are PowerShell, run live against the *running* game. Everything resolves
addresses at run time (heap objects move per session). Launch with:

    powershell -ExecutionPolicy Bypass -File <script> [args]

Keep the game **focused and in-world** while a script runs — it pauses on focus loss.
Screenshots via PrintWindow are stale for this game; trust the player's eyes or a real
screen grab.

## Core (current toolkit)

| Script | What it does |
|---|---|
| `bp-capture-param2.ps1` | Attaches a WOW64 debugger, INT3s the camera smoother (`AC4BFSP.exe+0xD2218E`), captures the **character node** address (EAX), dumps it, detaches. The reliable way to find the player's node. |
| `fake_peer_send.ps1` | Plays a **fake co-op peer**: sends the AccCoop Player packet to the plugin (default port 27810) while circling the player; also listens on 27811 for the plugin's own packets. Args: `-PluginPort -DurationSec`. |
| `set-remote-ip.ps1` | **Test day:** points the live `[Coop]` config at a peer — `-Ip <addr>` writes RemoteIp1..4 octets in place (plus optional `-LocalPort/-RemotePort/-ClientId`). Safe while the game runs (live reload). |
| `drag-body-test.ps1` | Reels a drivable crowd body in to the player and holds it — the "can you see it?" test. |
| `shove-edward-and-burst.ps1` | Captures the player node, shoves the player (visible), then bursts nearby bodies — the demo that proved writes move characters. |
| `follower-test2.ps1` | Standalone (no plugin) demo: makes the nearest humanoid follow the player's walk. |

## Look sampling (outfit picking)

| Script | What it does |
|---|---|
| `calibrate-front.ps1` | Hops one body around the player to 4 candidate "front" spots (90° apart, 9 s each, readback per spot). **Confirmed 2026-10-06: spot 1 (+Y convention) = true front, err 0.00 m.** |
| `sample-looks.ps1` | Brings crowd clothing variants to the player one at a time for picking. Args: `-All` (no variant dedupe), `-MinDist` (min start distance, default 4), `-HoldSec`, `-Samples`. Variant fingerprint = FNV-1a over the child-part class sequence. |
| `find-graphics.ps1` | Read-only: graphic-class instance scan + node correlation + raw dumps. Ruled out: 0x02595BC8 / 0x02595050 are common components, not unique visual objects. |
| `find-shared-refs.ps1` | Read-only: finds pointer fields equal across same-variant civs but different on the player. Caveat: dynamic state can fake "shared" — sample twice. |
| `outfit-probe.ps1` | Live write-and-revert probe of candidate node fields on a civ body. 2026-10-06 result: **zero visible change** — the look builds only at spawn/rebuild time (outfit = parked rebuild-path project). |
| `trace-states.ps1` | Broad sampler of the player's node + both controllers (300 ms); logs every field flip + heartbeat (pos/speed). First B4 data source. |
| `trace-actions.ps1` | Focused action tracer (150 ms, noise offsets skipped, `CLIMB?` marker on fast z-rise). Produced the B4 action-field map (see MODLOG). |
| `action-write-probe.ps1` | Guarded write-and-revert of the action-state fields into a **civ** controller. Result: invalid (civ controller is a different class layout) — play side needs the engine action API. |
| `watch-writer.ps1` | WOW64 **hardware write-watchpoint** (DR0/DR7 on all game threads) on a chosen address; logs each write's EIP + registers + return address. Caught the B4 action writer (FUN_01ab52c0). Game tends to crash after detach — data is captured before that. |

## Scanners / diagnostics

| Script | What it does |
|---|---|
| `scan-class-instances.ps1` | Census of the character-node class (instances, ids, positions). |
| `scan-npcs.ps1` | Classified body scan: `f7c` histogram, humanoid filter, movers, groups. |
| `scan-special-bodies.ps1` | Children-count histogram; finds non-standard rigs. |
| `wait-and-scan-npcs.ps1` | Waits until the game actually simulates (player moves), then scans movers. |
| `diff-multi-bodies.ps1` | Field-by-field diff: player vs several confirmed-visible crowd bodies. |
| `compare-parts.ps1` | Part-by-part (rig/children) comparison between two bodies. |
| `find-body-owner.ps1` | Finds every pointer to the player's node and dumps the referencing structures. |
| `scan-edward-strings.ps1` | Memory string scanner (ASCII / UTF-16) for model/name references. |

## For the model-swap project (parked)

| Script | What it does |
|---|---|
| `snapshot-puppet.ps1 -Label A` | Snapshots the player node + rig + pointer targets to `logs/snap-A.txt`. |
| `diff-snaps.ps1 -A a -B b` | Diffs two snapshots — the before/after oracle for outfit/model changes. |

## Archive (`tools/archive/`)

Superseded or one-off scripts, kept for reference: the failed hardware-write-breakpoint hunt
(`find-writer.ps1`), the pop/glide/follow experiments (`npc-pop-test*.ps1`, `puppet-test.ps1`,
`follower-test.ps1`, `group-test.ps1`), the early screenshot test (`live-test.ps1`), the probe
series (`probe-*.ps1`), `diff-char-nodes.ps1`, `src-write-test.ps1`, `walk-descriptors.ps1`,
`scan-transform-objects.ps1`.

## Gotchas (learned the hard way)

- Never name helpers `rd`, `rp`, `rm`, `dir`, `gm`, … — PowerShell aliases shadow them and
  silently break scripts mid-run.
- The game **pauses when unfocused** — scans see a frozen world; wait for real movement first.
- The game-side plugin log is `...\plugins\AC.BlackFlag.PatchFix.log`; it rotates at ~1 MB,
  so copy captures out promptly.
- WOW64 breakpoints arrive as exception code `0x4000001F` (not `0x80000003`); handling them
  wrong kills the game.
