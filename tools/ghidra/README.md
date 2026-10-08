# Ghidra scripts

Reusable headless Ghidra scripts (Java) written while decompiling **ACC.exe** (AC Rogue, x64) and
**AC4BFSP.exe / AC4BFMP.exe** (Black Flag, x86). They are run with `-noanalysis -postScript` against
an already-analyzed project.

Run pattern (example):

```sh
# Windows
analyzeHeadless.bat C:\ghidra-proj AC4BFSP -process AC4BFSP.exe -noanalysis ^
    -postScript DecompileList.java targets.txt out_dir
# Linux/macOS
$GHIDRA_HOME/support/analyzeHeadless ~/ghidra-proj AC4BFSP -process AC4BFSP.exe -noanalysis \
    -postScript DecompileList.java targets.txt out_dir
```

Set `GHIDRA_HEADLESS_MAXMEM=20G` for the big x86 exes (the 43 MB `AC4BFSP.exe` OOMs at 8 GB).

## The useful ones

| Script | What it does |
|---|---|
| `DumpAll*.java`, `DumpAllDecomp.java`, `ExportAllDecomp.java` | Full-tree decompile to chunked `.c` files (this is how we indexed everything with `gamedb`). |
| `DecompileList.java`, `DecompileMany.java`, `DecompileFuncs.java`, `DecompileSlots.java` | Decompile a list of addresses / slots to text. |
| `CallersList.java`, `CallersOfBFSP.java`, `CallList.java`, `RefsTo*.java` | Caller / reference dumps for a target address. |
| `FindStrings.java`, `ExportStringsWithRefs.java` | String search with xrefs (engine feature names, message names…). |
| `GetBytes.java`, `GetBytes2/3.java` | Raw byte dumps around an address (signature hunting). |
| `DumpVT.java`, `ExportVtables.java`, `FindVtables.java`, `FindClassPtr.java`, `FindPawnVtable.java` | Vtable / class-descriptor discovery — the main identification tool on these engines (RTTI is stripped/partial). |
| `FindAnchors.java`, `FindSymbols.java`, `ExportDataSymbols.java` | Anchor/global hunting. |
| `DumpInstr.java`, `GhidraDump.java`, `DumpFuncs.java` | Misc dump helpers. |

## What's not in here

The **outputs** (`.txt` decompilation dumps, string tables, function lists) are not included — they
are large, game-derived and easy to regenerate. The naming convention in the scripts matches the
project phase names used in `docs/blackflag-coop/MODLOG.md` (`*14`, `*15`, `ActionNN…`) if you want
to follow the trail.
