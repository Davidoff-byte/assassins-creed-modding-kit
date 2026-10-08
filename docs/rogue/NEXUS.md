# Nexus Mods posting guide

Two separate releases. Everything below is ready to paste.

---

## Release 1 — One-Handed Sword

- **Title:** One-Handed Sword
- **Category:** Miscellaneous → Gameplay
- **Tags:** Gameplay, Combat, Animations, Sword
- **Game version:** Assassin's Creed Rogue (PC, Steam)
- **Version:** 1.0
- **Zip:** `dist/OneHandedSword-1.0.zip`
- **Contents:** `plugins/AC.Rogue.PatchFix.asi`, `plugins/AC.Rogue.PatchFix.ini`,
  `README.md`, `LICENSE.txt`

**Summary (the bio):**
> Shay fights with a one-handed sword moveset instead of the sword-and-dagger
> dual-wield.

**Description:** paste the body of `ac-rogue-single-sword/README.md`.

**Requirements / notes to list:**
- Ultimate ASI Loader (`dinput8.dll`) — not included.
- Game closed while installing.
- Single-player only.

---

## Release 2 — Hidden Dagger

- **Title:** Hidden Dagger
- **Category:** Miscellaneous → Gameplay
- **Tags:** Gameplay, Combat, Weapon, Immersion
- **Game version:** Assassin's Creed Rogue (PC, Steam)
- **Version:** 1.0
- **Zip:** `dist/HiddenDagger-1.0.zip`
- **Contents:** `Install.bat`, `hide_dagger.py`, `README.md`

**Summary (the bio):**
> Hides Shay's off-hand dagger so the sword set reads as a true single sword.

**Description:** paste the body of `ac-rogue-hidden-dagger/README.md`.

**Requirements / notes to list:**
- Python 3 (installer only).
- Game closed while installing.
- Modifies your own `DataPC.forge`; re-run after a game verify/repair.

---

## Building the zips

From the project root:

```powershell
$d = "dist"
New-Item -ItemType Directory -Force $d | Out-Null
Compress-Archive -Force "ac-rogue-single-sword\plugins","ac-rogue-single-sword\README.md","ac-rogue-single-sword\LICENSE.txt" "$d\OneHandedSword-1.0.zip"
Compress-Archive -Force "ac-rogue-hidden-dagger\Install.bat","ac-rogue-hidden-dagger\hide_dagger.py","ac-rogue-hidden-dagger\README.md" "$d\HiddenDagger-1.0.zip"
```

The sword zip is laid out as it installs (`plugins/...`): unpacking it into the
game folder is the whole install.

## Pre-upload checklist

- [ ] Game closed; both changes tested in game.
- [ ] No game files, decompiled code or third-party binaries bundled
      (`dist/` checked with `um publish check`).
- [ ] `LICENSE.txt` (upstream MIT, AC.PatchFix / PlayDay) included in the sword zip.
- [ ] Credits the ASI loader (Ultimate ASI Loader) and AC.PatchFix.
- [ ] Single-player warning present.
- [ ] Uninstall steps in each README (sword: delete the plugin; dagger: restore
      `DataPC.forge.bak_dagger`).

## Not included (parked)

The one-handed **sound** fix (replacing the dual-wield weapon sound set with the
single-sword one) is a `DataPC.forge` edit and is **not** part of these
releases. It can be packaged later the same way as the dagger patch if wanted.
