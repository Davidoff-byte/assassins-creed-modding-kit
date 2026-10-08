# Released mods (AC Rogue)

Both are complete, self-contained packages for **Assassin's Creed Rogue (PC, Steam)**. Each zip
contains the mod plus its README; the game must be closed while installing. Neither ships any game
files — they edit or hook *your own* copy.

| File | What it does |
|---|---|
| `OneHandedSword-1.0.zip` | Shay fights with the one-handed sword moveset (plugin: remaps the weapon class; toggle in the INI). Ships our modified `AC.PatchFix` build with the upstream display features. |
| `HiddenDagger-1.0.zip` | Hides the off-hand dagger on all sword sets (pure `.forge` data edit; Python installer edits your own `DataPC.forge`, backup kept). |

Install notes: `OneHandedSword` needs an ASI loader (`dinput8.dll`, Ultimate ASI Loader) in the
game folder. `HiddenDagger` needs Python 3 only.

The full story of how these were built (forge tooling, the weapon-class chain, the data-pipeline
proof) is in `docs/rogue/MODLOG.md`; the combat/stealth research that didn't ship is in
`docs/rogue/COMBAT_STEALTH_RESEARCH.md`.
