# OVERNIGHT RE REPORT — 2026-10-08 night

Living document; updated as the overnight run progresses. Anything marked **[P#]** feeds the
co-op ladder; **[RW]** feeds a future rewrite.

## 1. The corpus (done, indexed)

| Exe | Functions exported | Indexed | Call edges | Strings |
|---|---|---|---|---|
| AC4BFSP.exe | 135,108 | 134,020 | 361,841 | 12,845 |
| AC4BFMP.exe | 106,900 | 106,269 | 283,506 | 15,463 |

Queries: `gamedb read/strings/graph/sql -r <sp_src|mp_src>` (seconds per query).

## 2. Analysis artifacts (bf4_re/analysis)

- `features_{sp,mp}.tsv` — per-function size/callees/strings
- `strings_{sp,mp}.tsv` — string → function index
- `callers_{sp,mp}.tsv` — hub map (most-called functions; allocator/refcount layer tops it)
- `propnames_{sp,mp}.tsv` + `symbol_suggestions.tsv` — 3,660 naming proposals (string-anchored,
  some transferred via the cross-map)
- `cross_sp_mp.tsv` — 1,048 matched SP↔MP function pairs (shared strings) **[RW]**
- `vtables_{sp,mp}.txt` — **15,201 + 10,269 vtables**: address, slot count, referencing
  functions (ctor/dtor sites), every slot's function **[RW]** (the class skeleton)
- `globals_{sp,mp}.txt` — **149,144 + 92,902 referenced data symbols** with their reading/writing
  functions **[RW]** (the global-state map)
- `strings_ghidra_{sp,mp}.txt` — strings with ADDRESSES + refs (hook anchors) — SP: 98,478 done, MP running
- `top_classes_sp.tsv` — most-referenced vtables (engine "who's who"; top: `01e41070` 276 refs,
  `01e7f474` 66, `01e6a2a8` 55, `01e7faf8` 42 with 190 slots)

## 3. Entity lifecycle (P1 groundwork) **[P1]**

- ctor `FUN_0052a4a0`; base dtor `FUN_00526d90` (+ wrapper `FUN_0052a950`); derived-body dtors
  `FUN_004ffe70`/`FUN_008a0fc0`. vtables: `0x1E4CE90` (6 slots), `0x1E4A128` (6), `0x1E809A0` (3).
- Dtor teardown: children array `+0x60`/count `+0x66`, scene ref `+0x68`, arrays `+0x78/+0xA0/+0xD4`,
  module-unregister `FUN_00a385c0(1)` etc.
- Destruction is virtual → the live CullWatch (deployed in the plugin, armed) catches it at the
  zone crossing.

## 4. MP netcode oracle (BFCoop event channel) **[P4/P5/events]**

See `RE-NETCODE-ORACLE.md` for the full map. Highlights:
- Registration hub `FUN_004ce584`; descriptor layout {vtable, pack-fn, 0, id, apply-fn, name}.
- `M2R_ReplicateEnterCustomActionState` fully located (pack `FUN_004d9140`, apply `FUN_004d1bed` →
  `FUN_004caa4a`) — reference implementation for remote climb/vault replay **[P3]**.
- `S2C_NotifyDamageKill` sender `FUN_00567b52` (complex kill flow, to be studied for the P4 schema).
- Speed events `S2C_ChangeEngineSpeed`/`S2C_ResetEngineSpeed` **[P5]**.

## 5. Immediate-goal candidates **[P2-P5]**

See `RE-CANDIDATES.md`. Highlights: marker component + `PLAYER_MARKER_ADD` names; parkour family
(`ActorCustomActionOperator` etc.); `Action_Assassinate`; ship-type map `FUN_01045cd0`.

## 6. In-game instruments ready for the next live session (needs the user)

- Netcode v0.3 (session + events) — kit shipped, verify pending.
- `CullWatch` — armed; the zone-crossing test decides destroyed vs detached vs re-picked.

## 7. Status / next

- Running: strings-with-refs export (SP, then MP).
- Next once done: finalize docs, morning summary, note any follow-up exports.
