# Throwing knife — permanent arsenal: investigation record

Goal: make the throwing knife (dropped by **Agile** enemies, picked up and thrown in combat) a
permanent part of Shay's arsenal, reachable in the tool wheel.

**Outcome: not delivered.** Both obvious routes were investigated to a conclusion; the feature is
a contextual combat *state*, not a stored inventory item, and neither route is a mod tweak. This
file is the concise record so no future session re-treads it.

---

## Established facts (do not re-derive)

| Thing | Value |
|---|---|
| Throwing knife as a **Tool** | `FUN_141022b90` Tool enum, value **7** |
| Inventory category | `InvItem_Knives` (type 8) in `FUN_14102b180` |
| Combat action | `Action_ThrowKnife`, registered id **0x1b** (`FUN_1417bf580`) |
| Tool-wheel input | `NextToolSelection` / `PrevToolSelection`, `Inventory0..7` (acc_00000.c ~0x660) |
| HUD ammo readout | `FUN_1410f7460(id, actor)` / `FUN_1410f73d0(actor, id)` |
| Player tool object | vtable `0x142ACD4B0`, reached via `FUN_141e6bea0` |
| Player holder | `*(playerSlot+0x30)`; player type `(*(u32*)(holder+0xd0) & 7) == 1` |

## What is proven NEGATIVE (skip these)

1. **`FightSettings` pacing floats** — no effect (earlier sessions).
2. **`FUN_1420fa3a0` ("DoesPacingAllowNPCActions")** — **never called** in combat.
3. **`FUN_14183b970` (fight-action availability)** — **player-only**; NPCs never call it.
4. **HUD quantity accessor `FUN_1410f7460`** — **display-only**. It accepts only ids
   `{1, 0x14..0x1b}`; **tool id 7 is rejected**. Forcing it (even `force_all`) changes the HUD
   numbers and does **not** add the knife or change the in-game count.
5. **Player tool object + its ~10 child tool objects + the holder** — **byte-identical** with and
   without a knife (probed live, throttled dumps diffed across pickups/throws).

## Data route (ruled out)

Every real wheel tool has a data definition:

- Pistols: `ACC_WR_*_Pistols_*`
- Rope dart: `ACC_WR_Player-RopeDart`, `CHR_W_P_RopeDart_SpawnedProjectile`
- Smoke bomb: `CHR_W_P_SmokeBombPlayer`
- Money: `CHR_W_P_Money_Throwable`

The throwing knife has **only assets**: `TPL_WP_Throwing_Dagger`, `TPL_WP_Throwing_Dagger_LOD0`,
`TPL_WP_Throwing_Dagger_BoxShape`, `ProjectileSoundSet_ThrowingDagger`. There is **no**
`ACC_WR_Player-ThrowingKnife`, no item-catalog / inventory-page / shop / ammo entry (searched the
whole `Game Bootstrap Settings.data`). ⇒ nothing to edit; a true inventory item would need brand-new
engine resources (hashed type ids) + UI + input mapping — a large content-engineering job.

## Recommended next step (if resumed)

**Whole-process differential**, not more object probing:

1. With 0 knives, snapshot the process's writable regions.
2. Pick up 1 knife.
3. Diff to find the loadout/pickup state; then a small hook writes it at load.

This is the only method that cannot miss if the state lives in RAM, and it needs no new assets.

## Diagnostic hooks left in tree (all default OFF)

- `KnifeProbe` — `knife_probe.{hpp,cpp}` (patterns `KNIFE_PROBE`, `KNIFE_ENTITY`).
- `KnifeGrant` — `knife_grant.{hpp,cpp}` (patterns `KNIFE_QTY`, `KNIFE_QTY_MAX`).
- `AIAggression` — `ai_pacing.{hpp,cpp}` (patterns `AI_PACING`, `AI_ACTION_AVAIL`).

INI keys (deployed): `KnifeProbe=false`, `ThrowingKnives=false`, `ThrowingKnifeAll=false`.
