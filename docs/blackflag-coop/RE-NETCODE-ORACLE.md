# RE: MP netcode oracle (AC4BFMP) — event/message system

All addresses = MP exe. Source: `bf4_re/mp_src` corpus + gamedb + who_refs.py.
Purpose: mirror the engine's own replication scheme in the BFCoop plugin (P4 kill sync, P3
custom-action replay, C-event channel), and keep the map for a future rewrite.

## The event system

- **Registration hub**: `FUN_004ce584` builds the whole event table. Pattern per event:
  ```
  FUN_011fc7e0("<NAME>");            // ensure/lookup the event
  id = FUN_0122d3a0();               // assign an id
  DAT_<global> = id & 0xffff;        // store the id
  FUN_00c3348c(mgr, &DAT_<global>, "<NAME>");  // bind name <-> slot
  ```
- **Senders** reference the id global (e.g. `local_3c = DAT_01a1c454;` then pack it into a message).
- **Teardown/reset**: `FUN_01371bdb` sets ids back to `0xffffffff`.
- Message name families (all registered here): `S2C_*` (server→client), `M2R_*` (member→replication?),
  `D2M_*`, `M2D_*`, `M2All_*`, `M2A_*`, `C2S_*`.

## Message descriptor layout (derived from `FUN_0137272d`)

Every registered event has a descriptor struct at its `&DAT_slot`, filled before binding:

```
+0x00  vtable/class ptr        (MP: PTR_FUN_0139a5dc)
+0x04  serialize/write fn      (MP: FUN_004d9140 - packs transform+action; sender side)
+0x08  0
+0x0C  assigned id (0xffffffff until bound)
+0x10  apply/read fn           (MP: FUN_004d1bed -> FUN_004caa4a - applies to candidates)
+0x14  char* name              (MP: "M2R_ReplicateEnterCustomActionState")
```

Binding: `FUN_00c3348c(mgr, &slot, name)` (called from the registration hub `FUN_004ce584`).

## Key events located

| Event | Id global | Evidence | Notes |
|---|---|---|---|
| `S2C_NotifyDamageKill` | `DAT_01a1c454` | sender `FUN_00567b52` (reads id, builds payload), reset `FUN_01371bdb` | **P4 oracle** — payload construction to study |
| `S2C_Transition` | `DAT_01a1c3f4` | `FUN_004ce584` | stance/state transition |
| `S2C_TransitionToLedgeClimb` | `DAT_01a1c40c` | `FUN_004ce584` | **P3 ledge climb** |
| `S2C_TransitFromLedgeOrClimbToDieRagdoll` | `DAT_01a1c424` | `FUN_004ce584` | cliff-death ragdoll |
| `S2C_PostRespawn` | `DAT_01a1c43c` | `FUN_004ce584` |  |
| `S2C_NotifyHumiliation` | (after 1c454) | `FUN_004ce584` |  |
| `M2R_ReplicateEnterCustomActionState` | `DAT_01a1c838` | init `FUN_0137272d` sets `&PTR_FUN_0139a5dc`; traffic `FUN_009a7074` → `FUN_00c31951(mgr, slot, fn)` | **P3 core** — the remote custom-action state replay |
| `M2R_ReplicateExitCustomActionState` | — | `FUN_004ce584` |  |

## Next steps (resume pointers)

1. Read `FUN_0137272d` → it wires the M2R custom-action handler struct (`PTR_FUN_0139a5dc` vicinity);
   the handler that applies a remote custom action is what we mirror for P3.
2. Read `FUN_00567b52` (kill notifier) fully → payload layout → our `EventKind::Kill` schema.
3. Find the RECEIVE path: the table registered by `FUN_00c3348c` + `FUN_00c31951` — locate the
   dispatch function that calls handlers by id (`who_refs.py` for the mgr global once identified).
