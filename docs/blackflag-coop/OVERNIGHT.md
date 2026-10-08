# Overnight RE program — 2026-10-08 night

**Goal (user):** maximize understanding of AC4 for BOTH (a) the immediate co-op work (P1–P5)
and (b) a distant full rewrite.

**Mechanics:** background jobs run unattended; each completion wakes the agent, which processes
the result, writes docs, and launches the next job. All state lives in files (nothing is held
only in the conversation). If the chain ever stops, resume at the first missing output below.

**Corpus (done earlier tonight):**
- `C:\Users\Administrator\bf4_re\sp_src` — 135,108 functions (AC4BFSP.exe)
- `C:\Users\Administrator\bf4_re\mp_src` — 106,900 functions (AC4BFMP.exe)
- gamedb indexes at `<root>\.gamedb\index.sqlite`

**Queue (check off as outputs appear):**

1. [x] `analysis/features_sp.tsv`, `features_mp.tsv` — per-function features
2. [x] `analysis/strings_sp.tsv`, `strings_mp.tsv` — string → function index
3. [x] `analysis/callers_sp.tsv`, `callers_mp.tsv` — most-called functions (hub map)
4. [x] `analysis/propnames_sp.tsv`, `propnames_mp.tsv` — proposed names (string-anchored)
5. [x] `analysis/cross_sp_mp.tsv` — SP↔MP matched pairs (shared strings) — 1,048 pairs
6. [x] `analysis/vtables_sp.txt` — 15,201 vtables with ctor/dtor refs + slots
7. [x] `analysis/vtables_mp.txt` — 10,269 vtables
7b. [x] `analysis/globals_sp.txt` — 149,144 referenced data symbols (SP)
7c. [ ] `analysis/globals_mp.txt` — MP version (running)
7d. [x] `RE-NETCODE-ORACLE.md`, `RE-CANDIDATES.md` — hunt docs
7e. [x] `analysis/strings_ghidra_sp.txt` — 98,478 strings with ADDRESSES + refs (hook anchors)
7f. [x] `analysis/strings_ghidra_mp.txt` — 62,358 strings with addresses
7g. [x] `analysis/top_classes_{sp,mp}.tsv` — most-referenced vtables (engine "who's who")
8. [~] targeted hunts (agent-driven, each writes `bf-coop/RE-*.md`):
   - P2: HUD marker candidates + `RE-CANDIDATES.md` (engine-marker vs D3D-overlay decision pending)
   - P3: MP custom-action chain mapped + `RE-P3-PLAN.md` (write-ghost-controller design)
   - P4: kill event located + `RE-P4-PLAN.md` (position-delta detection + guest apply design)
   - P5: ship-type map + speed events (`RE-CANDIDATES.md`)
   - MP replication field map — `RE-NETCODE-ORACLE.md`
9. [x] `OVERNIGHT-REPORT.md` — morning summary (final)
10. [x] plan docs: `RE-P3-PLAN.md`, `RE-P4-PLAN.md`

**Instruments already ready for the next live test (not overnight — needs the user):**
- Netcode v0.3 session + event channel (kit shipped)
- `CullWatch` in the live plugin (10 Hz ghost-body lifecycle sampler; armed in the A-side ini)

**Resume instructions (if the chain stopped):** look at `analysis/` for the outputs above; the
first missing/empty artifact is where to continue. The scripts: `bf-coop/tools/corpus_features.py`
and `C:\Users\Administrator\ghidra_scripts\ExportVtables.java` (re-runnable, overwrite outputs).

**Safety:** offline file analysis only overnight. No game launches, no writes to game data.
