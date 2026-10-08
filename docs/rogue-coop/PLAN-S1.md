# AccCoop — Stage S1: see each other + flawless tandem movement

**Locked objective (2026-10-04):** a remote avatar that reproduces the peer's movement accurately
enough that two players can run, free-run and climb/parkour *together* and trust what they see.
No kill-sync, no AI, no ships until this is good.

## The trap that decides this stage

Parkour is **root-motion + animation-state driven**, not simple position+velocity:

- A vault/leap/swing moves Shay because the *animation* moves the character root. If we replicate
  only the final position, the remote avatar will **glide or teleport** through moves that should
  look animated — the opposite of "flawless".
- Therefore this stage is **two problems**, not one:
  1. **Transform fidelity** — get the peer's *body* transform (not the camera), smooth and timely.
  2. **Action/animation-state fidelity** — reproduce *what move* the peer is doing so the remote
     avatar animates it, not just arrives at the destination.

## We must sync the *body*, not the camera

M2 currently reads the **camera** (already proven). For a remote body avatar the camera is wrong:
it trails the player, pitches independently, and detaches during parkour/cinematics. We need the
**player actor/root transform** (feet position + facing). Finding it is pure Rogue RE; it is the
first task and does not need Black Flag.

## Sub-milestones (each has an oracle; nothing is "done" without one)

| # | Deliverable | Oracle | Needs |
|---|---|---|---|
| **A1** | Player **body/root** world transform (pos + yaw) read each frame | in-game values track walking *and* stay correct when the camera moves/pitches | Rogue RE |
| **A2** | Transport quality: 30–60 Hz samples, sequence/ack, duplicate-drop | loopback capture shows monotonic seq, low loss | none (have it partly) |
| **A3** | Remote playback: **interpolation buffer** (~100 ms) + extrapolation on loss + smoothing | offline Python rig reproduces a recorded walk with no jitter/rubber-band; then in-game with a debug marker | none (buildable now) |
| **A4** | A **remote avatar exists** at the received transform | a second character stands/moves where the peer is | **Black Flag ref + Rogue spawn RE** |
| **A5** | **Action/animation-state** sync (locomotion + parkour moves) | two players vault/climb the same wall and the avatars match | Rogue anim RE + BF |
| **A6** | Tandem parkour test | run/leap/climb together, recording looks right | both machines |

## Design notes

- **Transport (A2/A3):** keep the proven UDP packet. Add per-entity seq + ack; render the remote
  ~2 snapshots in the past and interpolate; extrapolate ≤ ~150 ms on loss; clamp corrections so a
  jump never snaps visibly. This is textbook and I can build/test it **without the game** (S1 rig).
- **Avatar (A4):** spawn/reuse an AnvilNext character and set its world transform each frame. This
  is the highest-risk task; Black Flag's `AC4BFMP.exe` is a shipped example of an MP avatar. Rogue
  candidates: `Ai::SpawningManagerUpdate` (`FUN_14046b6f0`), `SpawnEntityOperator`,
  `GetCharacterEntityOperator`, `AnimatedEntityComponent`.
- **Animation (A5):** ideally replicate a compact **action/anim id** and have the remote avatar
  play it; fallback is a coarse locomotion state (idle/walk/run/sprint/swim/climb/fall) + a slide.
  Parkour that looks right probably needs the real action id — accept "rough" if we can't get it.

## Honest expectation

- **A1–A3 (transform + transport):** high confidence, mostly BF-independent, testable now.
- **A4 (avatar):** the real gate; medium confidence, BF helps a lot.
- **A5 (parkour animation):** the difference between "flawless" and "okay"; medium–low, and the
  honest cap on "as perfectly as possible". If we can't drive the remote avatar's parkour anims,
  the fallback is a smooth, correctly-placed body that slides — it'll *read* well from a distance
  and poorly up close during complex moves.

## Order

A1 → A2/A3 (can run in parallel; A2/A3 need no game) → A4 (BF) → A5 → A6.
