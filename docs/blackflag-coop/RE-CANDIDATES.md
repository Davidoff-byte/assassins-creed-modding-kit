# RE: candidate leads per priority (P2–P5) — BFCoop

Candidates from the overnight corpus sweeps (2026-10-08). Each row = a string→function join
result; "read next" = the first thing to examine when that priority comes up.

## P2 — HUD marker / partner tag

- **`PLAYER_MARKER_ADD` @ `FUN_01223790`** — marker component method; dispatches the named message
  `PLAYER_MARKER_ADD` via `FUN_007fe9a0(name,2,&payload)`. No direct callers (behavior-dispatched).
  `FUN_0117d1d0` (`MARKER_ADD`) is called only by `FUN_01223620` (`MARKER_FACTION_ADD`).
  Payload objects are 0x28-byte allocs (`FUN_004061f0(0x28,2,..)`).
- Marker message names: `MARKER_REMOVE` (`FUN_0114cc30`), `MARKER_ADD` (`FUN_0117d1d0`,
  `FUN_012a9770`, `FUN_01a550b0`), `MARKER_FACTION_ADD` (`FUN_01223620`), `PLAYER_MARKER_ADD`.
- Map/UI markers (separate system): `CustomMarker` `FUN_017351d0`, `addCustomMarker` `FUN_017497f0`,
  `MapIconCustomMarker` `FUN_017499a0`, `placeCustomMarker`/`removeCustomMarker` `FUN_014df800`.
- **Read next:** `FUN_007fe9a0` (the named-message dispatcher) → who receives `PLAYER_MARKER_ADD`;
  then decide engine-markers vs D3D overlay for the partner tag.

## P3 — parkour / custom actions (play side)

- SP custom-action family: `ActorCustomActionOperator` `FUN_018899a0`, `PlayerCustomAction`
  `FUN_01b75620`, `CLOrientedCustomAction` `FUN_018fe5d0`, `CLCustomActionReaction` `FUN_011678c0`,
  `CRLCustomAction` `FUN_013a8f60`, `CLInvestigation_..._CustomAction` `FUN_00f8ae40`.
- Known from earlier sessions: action machine `FUN_01ac1ad0` (applies request slots `[owner+0x2F50…]`),
  writer `FUN_01ab52c0` ("BhvAssassin", writes `+0x8D4/+0x8D8/+0x8E0` — the fields B4 reads).
- MP oracle: `M2R_ReplicateEnterCustomActionState` (see RE-NETCODE-ORACLE.md) — the remote replay
  handler `PTR_FUN_0139a5dc` vicinity (read `FUN_0137272d` next) shows exactly what a remote
  custom action needs.
- **Read next:** `FUN_0137272d` (MP) + `FUN_018899a0` (SP operator) → map the request-slot write
  that replays a climbing/vaulting state on the ghost body.

## P4 — kill/damage sync

- Action-name strings: `Action_Assassinate` `FUN_0150bde0`, `Assassinate High/Low Profile` `FUN_01732ce0`.
- MP kill event: `S2C_NotifyDamageKill` — sender `FUN_00567b52` (MP), id `DAT_01a1c454`.
- **Read next:** `FUN_00567b52` payload layout → mirror in `EventKind::Kill` (NPC type + position +
  victim id), then find the SP local kill moment (same action-name strings in SP, and the health
  write path) to detect kills on the host.

## P5 — ships / naval

- **Ship type map (SP, clean): `FUN_01045cd0`** = `ShipTypeName(type, allyFlag)`:
  1 Gun Boat · 2 Schooner · 3 Brig · 4 Frigate · 6 Man Of War · 7 Jackdaw · 8-0xB Super Ship ·
  0xC Qar · 0xD The Revenge · 0xF-0x10 named legendaries · allyFlag → "Ally Ship".
- UI-side names: `SAIL` `FUN_015d6340`, `SAILS` `FUN_015d65b0`, `HUD_NAVAL_SAILS`
  `FUN_01779d60`/`FUN_0177a120`/`FUN_0177c420`.
- MP speed events: `S2C_ChangeEngineSpeed` / `S2C_ResetEngineSpeed` (registered in `FUN_004c0463`).
- **Read next:** the ship entity class (search vtable refs for sail-mast components), the helm input state,
  and how `S2C_ChangeEngineSpeed` reaches the ship sim (MP `FUN_004c0463` family).
