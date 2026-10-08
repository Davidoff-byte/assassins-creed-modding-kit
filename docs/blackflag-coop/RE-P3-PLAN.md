# P3 design — parkour/animations on the ghost (from overnight RE)

Goal (user priority #1): two players vault/climb together — the partner's body *animates* the same
actions instead of sliding.

## What we know

- **Read side (done, in the plugin)**: the local player's action state = `phase` (+0x8E0),
  `hang` (+0x8D8), `blend` (+0x8D4), in-action flags (bits of +0x138/+0x8D0) — packed as
  `anim_state` and already sent over the wire (B4 read side).
- **Write side (open)**: the action machine `FUN_01ac1ad0` applies request slots at
  `[owner+0x2F50…]`; the writer `FUN_01ab52c0` ("BhvAssassin") writes the player's fields; the
  ghost body has a controller at `node+0xE8` (same layout as the player's, per B4 read side).
- **MP reference (from tonight)**: `M2R_ReplicateEnterCustomActionState` descriptor —
  pack `FUN_004d9140` (carries transform + action block), apply `FUN_004d1bed` →
  `FUN_004caa4a` (visitor: applies callback over a candidate container at
  `[+0x14],[+0x18],[+0x30],[+0x40]`). So MP replays custom actions by writing an action-state
  block onto the target puppet — the same idea as B4-play but engine-native.

## Plan (incremental, each step verifiable in the log)

1. **Write-only test (no anim yet)**: on receiving a fresh remote `anim_state`, write the SAME
   field layout onto the ghost body's controller (`ctl = [node+0xE8]`):
   `ctl+0x8E0 = phase`, `ctl+0x8D8 = hang`, `ctl+0x8D4 = blend`, bits into `ctl+0x138/+0x8D0`.
   Watch: does the body visually change pose at all (even a step/hang)? CullWatch protects the body.
2. If direct writes are ignored (AI overwrites), snapshot the write pattern from the engine:
   temporarily hook `FUN_01ac1ad0` call sites via `who_refs`/`FUN_01ab52c0` and log arguments when
   the LOCAL player enters a custom action; replay the same call with the ghost as owner.
3. Coarse first: map only 4-6 states (idle/run/climb-up/climb-down/vault/land). Refine later.

## Fallback

If engine calls are too fragile, accept "steering-only" (today's behavior) for the live test and
push P3 after P1/P2 — the corpus won't block us; this is a tuning loop on a live save.
