# AccCoop — Assassin's Creed Rogue shared-world co-op

Goal (user, 2026-10-04): **free-roam co-op in one shared world.** Same AI, mirrored kills
("my friend kills a guard → it dies on my screen"), board and sail ships together, hop on each
other's ships. Connection: **LAN via Radmin VPN**.

Route: build a **replication layer** for an engine that shipped without one. Native ASI plugin
(reuse `AC.PatchFix`: SafetyHook + pattern scan + registry), peer state exchange over UDP, and
**AC4 Black Flag's `AC4BFMP.exe` as the reference implementation**.

## Reality check (read this)

Rogue's engine is Black Flag's, **minus the multiplayer binary**. There is no netcode to unlock
(verified: no replication/session strings in `ACC.exe`; the `Online*` strings are Ubisoft OSDK and
"Desynchronization" is AC's mission-fail). So this is not a fix — it's a from-scratch networking
project against a closed, undocumented 67 MB native engine.

Therefore: **incremental, one verifiable stage at a time**, and "everything perfectly synced" is the
asymptote we push toward, not the first build. Stage 1 makes you *see* each other; stage 2 makes
*kills* mirror; stage 3 drags *crowds* into sync; stage 4 is *ships*.

## Why Black Flag is required, not optional

| | Black Flag | Rogue |
|---|---|---|
| Single-player exe | `AC4BFSP.exe` | `ACC.exe` |
| Multiplayer exe | **`AC4BFMP.exe`** | *(none)* |
| Engine | AnvilNext (scimitar) | AnvilNext (scimitar) |

`AC4BFMP.exe` is a shipped AnvilNext replication implementation: networked entity/pawn spawn,
state streaming, avatar animation, and the **entity identity** scheme. Rogue was built from it, so
its functions/structures correlate. We reverse it as a **design oracle** (never a drop-in, never
run online — that would be PvP cheating).

## The identity problem (critical path)

"He killed NPC X" requires both machines to agree which NPC X is. Candidate keys, best first:
1. **Engine entity id/hash** — AnvilNext entities are named/hashed; find the stable runtime id.
2. **Spawn-order index** — works only if both clients load the identical save/scene.
3. **Position+archetype match** at session start, then track by owner.

Black Flag's MP exe solves exactly this; RE it first. Without a stable key, kills cannot mirror.

## Architecture (staged, host-authoritative)

Two clients on a Radmin VPN virtual LAN, UDP. One is **host** (authoritative world + NPC AI +
events); the other **client** applies. Each player always owns their own avatar and ship.

```
 Player A (host)                                   Player B (client)
   owns avatar A, ship A, NPC AI, world events       owns avatar B, ship B
   ── avatar A / ship A / npc snapshots / events ──▶ applies avatar A, NPC state, events
   ◀── avatar B / ship B / requests ────────────────  ◀──
```

| Stage | What | Oracle |
|---|---|---|
| S1 | **Avatars** — see each other, walk/ride together | second character stands where the peer stands |
| S2 | **Events** — kill, KO, damage, alarm, board, enter/exit ship | peer kills a guard → it dies on your screen |
| S3 | **NPC correction** — host streams nearby NPC transform+anim; client freezes its local AI for them | a crowd fights the same way on both screens |
| S4 | **Ships** — player ship replicated with owner; AI ships corrected; boarding = event+attach | sail together; stand on the peer's deck |
| S5 | **World/objectives** — objective/story flags (partly out of scope) | objective completes on both |

**Shared world:** both load the same region from the same save. Start with free-roam
(North Atlantic / River Valley); story-mission sync is a later, separate problem.

## Hooks found in `ACC.exe` (Ghidra, base `0x140000000`)

**Structural discovery:** the engine is a **task-graph scheduler**. `FUN_1400d53b0`,
`FUN_14010f850`, `FUN_1402b4840`, `FUN_1405d4320` are *registrars* — they build named task nodes
(e.g. `Engine::BeginFrame`, `Ai::UpdateCamera`, `Ai::SpawningManagerUpdate`) and store the real
per-frame function pointers. Full detail in **`RE-NOTES.md`**. The useful targets:

- **`Ai::UpdateCamera` = `FUN_1403664e0`** (and `Ai::AdjustCameraAfterPhysics` = `FUN_140358f00`) —
  fastest reliable read of a position/rotation (M2).
- **`Ai::SpawningManagerUpdate` = `FUN_14046b6f0` / `FUN_14046b7e0`** — the **entity spawn path**
  (M4 remote avatar).
- **`Ai::AIUpdate` = `FUN_140107450` / `FUN_1401075c0`** — AI/entity iteration (M6 NPC sync).
- **`Anim::UpdateDisplacement` = `FUN_140420bc0`**, `Anim::ActionUpdateEvents` = `FUN_14041fc90`,
  `Anim::UpdateActionBones` = `FUN_14041fcf0` — root motion / events / skeleton (avatar + deaths).
- Physics final transforms come through the `FUN_1402b4840` action/animation/physics graph.
- The camera-manager global is **already pattern-resolved** by `AC.PatchFix`, and
  `CameraSettings{4x4, fov}` is in `structs.hpp`.
- **GameState** struct (`structs.hpp`): `scene_context +0x260`, `world_context +0x290`,
  `session_ref +0x298`, `session_handler +0x2A0`.
- Existing player-object offsets: fight type `player+0x218`, state `player+0xaf8`; class getter
  `FUN_1417153e0(entity)`; stance `FUN_141022070(out, entity)`.

**Two integration options:** (1) read-only MidHook on a named task function (safe, chosen first);
(2) register our own task node into the scheduler (cleanest, needs the node-add API).

## Milestones

| # | Deliverable | Oracle | Needs |
|---|---|---|---|
| M0 | Recon + plan | this doc | done |
| M1 | Protocol (player + entities + events) + oracle | `tools/fake_peer.py --selftest` green | done |
| M2 | Read the **local player transform** in the plugin | walk/turn → logged numbers move; no crash | user runs the game |
| M3 | Two clients exchange + log each other (S1 plumbing) | peer position tracks over Radmin | M2 + 2nd machine |
| M4 | Peer **avatar** visible (S1) | see a character where the peer stands | M3 |
| M5 | **Event** channel + kill/KO apply (S2) | peer's kill kills on your screen | M4 |
| M6 | NPC correction (S3) | crowd stays consistent | M5 |
| M7 | Ships (S4) | sail + board together | M6 |
| BF | Reverse `AC4BFMP.exe` netcode (identity, spawn, stream) | design notes + matched `ACC.exe` anchors | BF installed |

## Risks

| Risk | Sev | Mitigation |
|---|---|---|
| Entity identity across machines | high | BF MP RE; test id/hash candidates live |
| Suppressing local AI on replicated NPCs | high | freeze flags / skip AI tick per entity; BF shows the pattern |
| Spawning/possessing the peer avatar | high | reuse AnvilNext character spawn; fall back to bare `AnimatedEntityComponent`; BF reference |
| Ships (physics, sailing, boarding) | high | treat player ship as part of the avatar; AI ships via correction |
| Two instances on one PC | med | prefer two machines over Radmin (user's plan) |
| Desync/float divergence | med | host-authoritative + periodic keyframe correction |
| Effort | high | staged; each stage independently shippable |

## Safety

Offline/LAN only; AC Rogue has no anti-cheat and we touch no servers. Never mod BF's live online
PvP — MP exe is reverse-engineered offline only. Back up saves first (`um backup create`). Ship our
code only; no game files or decompiled output in the repo. Ask before driving input or publishing.
