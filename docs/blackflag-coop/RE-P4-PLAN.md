# P4 design — host-authoritative kill sync (from overnight RE)

Goal: host detects a kill → guest applies the same kill to the matching NPC (both run the same
save/mission, so NPCs match by type + position).

## What we know (tonight)

- **MP kill event**: `S2C_NotifyDamageKill` — descriptor at `0x01a1c448..0x01a1c460` (id
  `DAT_01a1c454`), sender `FUN_00567b52`, init cluster `FUN_01371b96`/`FUN_01371bdb`/`FUN_01371c20`
  (part_00211). Sender passes descriptor fields `+4/+8` into `FUN_00555f9f(msg, ...)` — the generic
  message emitter. The payload is the MP reference for "someone died": study `FUN_00555f9f` args +
  the fields in `FUN_00567b52` (victim entity, killer, kill type, weapon).
- **SP kill moment**: `Action_Assassinate` (`FUN_0150bde0`), `Assassinate High/Low Profile`
  (`FUN_01732ce0`) — action-name side; the health/damage write path is still to be pinned live.
- **Our event rail (built tonight)**: `EventKind::Kill` (id 2) with 40B payload, resend+ack — ready.

## Detection options (pick one for the first test)

A. **Position-delta heuristic (no engine knowledge)**: host tracks nearby NPCs' positions at
   ~2 Hz; when a tracked NPC vanishes from the scan (or plays the death/ragdoll transition), emit
   `Kill {ship-type or entity class, x, y, z}`. Robust to engine changes; needs a body registry scan
   (we already scan bodies for the ghost picker — reuse).
B. **Action-state hook**: watch the player controller's action fields (`+0x8D4..+0x8E0`) for the
   assassinate action id; then find the victim = nearest NPC in front (<1.5 m). Cheaper; slightly
   fragile to action-id mappings.

Start with **A** (it also covers non-assassinate kills later), fall back to B for precision.

## Guest application (what "syncing" means)

- Match the NPC: same class (`f7c` family + children count) + nearest to the transmitted position
  (both run the same save; NPC layout matches within metres).
- Apply: route through the kill path if found (preferred), else the visual minimum — play the
  death/ragdoll transition by writing the action-state block (same mechanism as P3 step 2) and stop
  driving that body. Kill-shot: "he dies where my partner saw it die."

## Wire format (ready)

`EventKind::Kill`: `{u8 class_kind, u8 flags, u16 pad, f32 x, f32 y, f32 z, u32 victim_tick}` —
fits the 40B payload; host-authoritative (guest only applies, never emits kills).
