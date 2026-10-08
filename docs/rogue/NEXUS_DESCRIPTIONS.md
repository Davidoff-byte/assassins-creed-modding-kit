# Nexus "Full description" copy

Use **Import description** to paste these as markdown.

---

## One-Handed Sword

### Description

Shay fights with a one-handed sword moveset.

AC Rogue equips him with "sword and dagger" sets that use the dual-wield animations. This plugin remaps the player's fight type to single-sword, so the equipped weapon is used with the one-handed moveset — attacks, counters and finishers.

### Installation instructions

1. Close the game.
2. Make sure an ASI loader (`dinput8.dll`) is in the game folder.
3. Copy the `plugins` folder from the zip into the game folder (merge when asked).
4. Launch the game.

You should end up with `plugins\AC.Rogue.PatchFix.asi` and `plugins\AC.Rogue.PatchFix.ini`.

**Uninstall:** delete those two files.

**Toggle:** in `plugins\AC.Rogue.PatchFix.ini`, set `[Gameplay] OneHandedSword=true` (or `false` for the original animations). No reinstall.

### Main features

- One-handed sword moveset for the player (attacks, counters, finishers).
- Toggle in the INI, no reinstall.
- Also ships the base AC.PatchFix display features it is built on: ultrawide/aspect-ratio support, FOV correction, FPS unlock, full display-mode list, UI scaling, language unlock.

### Requirements

- Assassin's Creed Rogue (PC).
- Ultimate ASI Loader (`dinput8.dll`) — not included.

### Credits

- **PlayDay** — [AC.PatchFix](https://github.com/playday3008/AC.PatchFix) (MIT): the plugin this release is a modified build of. The one-handed-sword remap is the addition.
- **ThirteenAG** — [Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader) (MIT): loads the plugin.

---

## Hidden Dagger

### Description

Hides Shay's off-hand dagger, so the sword + dagger set reads as a true single sword.

Every sword set's off-hand weapon entity has its visibility flags turned off, so the dagger is never drawn. The sword, its stats and the animations are untouched.

### Installation instructions

1. Close the game.
2. Run **`Install.bat`** (needs Python 3).
3. Launch the game and start a fight — the left hand is empty.

If the game isn't in a default Steam folder: `Install.bat "D:\path\to\Assassin's Creed Rogue\DataPC.forge"`

**Uninstall:** copy `DataPC.forge.bak_dagger` (created next to the game) over `DataPC.forge`.

### Main features

- Hides the off-hand dagger on all sword sets.
- Nothing else is changed.
- Pairs with the **One-Handed Sword** plugin for a true single sword.

### Requirements

- Assassin's Creed Rogue (PC).
- Python 3 (installer only).
- Game closed during install.

### Credits

- **Kamzik123** — [AnvilToolkit](https://www.nexusmods.com/assassinscreed/mods/30): the community toolkit for AnvilNext `.forge` packages.
- Uses the game's own `lzo.dll` for compression. No game files are shipped.
