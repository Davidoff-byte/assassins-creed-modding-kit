# Install

Both mods are for **Assassin's Creed Rogue (PC, Steam)**. Close the game first.

## One-Handed Sword (plugin)

1. Put an ASI loader — `dinput8.dll` — in the game folder if you don't already have one.
2. Copy the mod's `plugins` folder into the game folder (merge when asked).
3. Launch the game. Shay now fights one-handed.

You should end up with:

```
<game>\plugins\AC.Rogue.PatchFix.asi
<game>\plugins\AC.Rogue.PatchFix.ini
```

**Uninstall:** delete those two files.

## Hidden Dagger (DataPC.forge patch)

Needs **Python 3** (python.org; tick *Add python.exe to PATH*).

1. Run **`Install.bat`**.
2. Launch the game and start a fight — the left hand is empty.

If the game isn't in a default Steam folder, drag `DataPC.forge` onto `Install.bat`,
or run: `Install.bat "D:\path\to\Assassin's Creed Rogue\DataPC.forge"`

**Uninstall:** copy `DataPC.forge.bak_dagger` (created next to the game) over `DataPC.forge`.

## Notes

- Use the two together for a true single sword: the sword mod changes the moveset, the dagger mod removes the off-hand dagger.
- Single-player only.
- After a Steam "verify integrity" / repair, re-run the dagger installer.
