# BFCoop — Assassin's Creed IV Black Flag shared-world co-op (single-player exe)

Goal (user, 2026-10-05): **two players, free-roam co-op in one world, parkour together in Havana.**
**End goal (user, 2026-10-06): the real thing — full campaign co-op.** Two players share one
Caribbean: on foot and under sail, in cities and at sea, with shared events (combat, boardings,
loot, objectives) and mission progress — not just a visible ghost. The C-ladder below is the road
from here to there.
Connection: **LAN via Radmin VPN**. Target exe: **`AC4BFSP.exe`** (the single-player/campaign exe).

## Current status (2026-10-08, after the full review + C1 build)

**Netcode (the user's "build the netcode"): C1 session + event channel = code-complete, built, deployed
(2026-10-08).** Handshake (Hello/Welcome, host role, 5 s timeout re-handshake, guest 5 s re-hello),
reliable-ish events (250 ms resend ×8, cumulative ack via `PlayerPayload.ack_seq`, dedupe by
`event_id`), `PlayerName`/`IsHost` config. Kit **v0.3** shipped (`dist/AC4BF-Coop-v0.3.zip`). Live
two-machine verify = next test day. Local loopback recipe: `dist/README-FOR-A.txt` bottom.

**Full-RE corpus started (2026-10-08):** mass decompile of `AC4BFSP.exe` (135,105 functions) into
`C:\Users\Administrator\bf4_re\sp_src` (resumable), MP exe queued; `gamedb` installed — after
indexing, every function/string/call-graph answer is instant.

**Solid ground (evidence-backed, keep):**
- **B0-B2 done + verified on TWO REAL MACHINES (Radmin VPN).** Position/facing read, UDP, two-machine
  link live (`peer=1 fresh=1`), both players saw each other's ghost in-game.
- **B3 = visible but UNSATISFIABLE as-is.** The hijacked crowd body works visually but gets
  streamed/culled ("body lost, rescanning"), fights the driver between packets, and re-picks ->
  the partner "teleports between strangers" (the user's verdict: "a haunting. unsustainable").
- **B4 read side = solved + wired** (`anim_state` packed over the wire; BhvAssassin family mapped).
  Play side (animations on the ghost) = pending, target `BhvGenericNPC` (`0x026E2820`).
- **The spawn system = fully mapped** (class ids via CRC32 of names, the mass creator + keys +
  registration; see RE-NOTES CURRENT TRUTH). **Runtime entity creation = CLOSED** (the engine
  creates characters only at world load; mid-game creation chokes the renderer — proven by ~6
  approaches + repeated audio-continues freezes). Do not retry it.
- **The hash hunt = CLOSED** (108M+ string tests; the ids are runtime keys).
- **All game data extracted** (~90k named files, `D:\bf4_extract`) via QuickBMS + scimitar_alt.bms;
  the mod reimport pipeline is proven (same-size swaps; backup at `D:\bf4_mod\backup`).

**The single open problem = THE BODY (the haunting).** Leading fix = **persist-hijack**: detach a
hijacked body from the world's streaming/cull registration so it survives forever and is driven
permanently. Supporting data yes (scene-registration marker fields, observed streaming loss);
mechanism UNPROVEN (which system frees them) — next live experiment = pin it down.

## Priority ladder (user spec, 2026-10-07 — build in THIS order)

| # | Deliverable | Why / oracle |
|---|---|---|
| **P1** | **Persistent partner body** (persist-hijack) | Kills the haunting — a fixed body driven forever, no re-picks. Oracle: hijack a body, clear the cull linkage, cross a zone boundary — the body survives. |
| **P2** | **Unique look + marker** | Assassin look via the mod pipeline (target-hunt for the right variant; the game ships `CHR_G_M_Assassin` etc.) + a HUD tag over the body (D3D overlay + world->screen projection). Oracle: partner = the distinctive hooded figure with a floating tag. |
| **P3** | **Parkour together** (the user's #1) | Position sync is exact; the gap = animations (B4 play side). Oracle: both vault/climb the same wall, the ghost animates. |
| **P4** | **Kill sync (host-authoritative)** | One authority: the host detects kills -> broadcasts (NPC type/position) -> the guest kills the match (same mission = same NPCs). Oracle: A kills a guard, B sees the same guard drop. |
| **P5** | **Ship fights** | Later; the host's ship + a ghost representation. |

The deeper C-ladder (session identity, replication breadth, mission sync) = the horizon; the
user-facing acceptance = P1-P5. A true hosted world = OUT OF SCOPE (no netcode in the SP engine;
this is host-authoritative two instances and must be described that way).

## Project B — assassin-body spawn (2026-10-06 — 2026-10-07) — **CLOSED / carried into P1+P2**

The ghost must be a sustained body (ideally assassin-class). Full history in MODLOG 2026-10-07 late.

- **What we learned (banked):** the spawn system end-to-end (class ids = CRC32 of names; mass
  creator + key system + keyed registration; the "Entity" class = full bodies; `FUN_005fd730` =
  parts; all verified from the engine's own 580-call census).
- **What stayed closed:** runtime entity creation (the engine creates characters only at world
  load; mid-game creation chokes the renderer — repeated audio-continues freezes; proven).
- **What survived as the real path:** (1) **persist-hijack** — a hijacked body detached from
  streaming = the sustained partner body (P1); (2) **the mod pipeline** — extracted assets +
  reimport = the look, no runtime calls (P2). The direct-spawn attempts are DO NOT RETRY.

## The end goal, in phases (C-ladder — the horizon)

The user-facing acceptance = P1-P5 above; the C-ladder = the long-term breadth. Same rule: nothing
is done without an oracle. **Frame = host-authoritative two instances** (no engine netcode).

| # | Deliverable | Oracle |
|---|---|---|
| **C1** | Session & identity — handshake with version + save fingerprint, stable player identity, reconnect | both logs show the same identity across a rejoin — **implemented 2026-10-08 (built); oracle pending** |
| **C2** | Character replication v2 — locomotion state + parkour as custom-action enter/exit events (BF MP scheme); remote animation linkage | both vault/climb the same wall in sync (=B4) |
| **C3** | Ship replication — the partner's ship hull + basic state driven on the shared sea | both sail together; his ship moves as he steers |
| **C4** | Interest & world-object replication — bounded set of nearby ships/items/quest objects (MP relevant/irrelevant pattern) | same ship boarded by both; same chest state |
| **C5** | Shared-event authority — ownership rules (local-authoritative bodies/ships; host or symmetric for contested combat/AI) + reconciliation | both see the same kill / boarding outcome |
| **C6** | Mission & progress sync — mission phase tracking + save policy (host-save as session truth; resume from checkpoint on desync) | both complete a mission step; can resume together after quitting |
| **C7** | Seamless transitions & polish — city↔sea transitions, out-of-map handling, desync repair, performance budget | an evening across sea + city + a mission with no restarts |

**Scale (order of magnitude; one agent-session ≈ 0.3-1M tokens):** C1-C3 ≈ 15-40 sessions;
C4-C6 ≈ 100-300; C7 ≈ 20-40. Tens of millions of tokens for a great shared-sea-and-city co-op;
hundreds of millions for the full campaign experience. The binding constraints are human test
cycles and unknown-unknowns, not tokens — budget 2-3× any estimate.

## Route

Port the proven **ACCoop** replication layer (built for AC Rogue) to Black Flag:
- native **ASI plugin** (AC.PatchFix framework: SafetyHook + pattern/RVA + registry),
- peer state over **UDP** on a Radmin VPN LAN,
- **`AC4BFMP.exe`** (Black Flag's shipped multiplayer exe, already partly reversed) as the
  **design oracle** for how AnvilNext represents and drives a networked avatar.

Rogue and Black Flag are the same engine ("scimitar"); Rogue is effectively BF **minus the MP
binary**. So the ACCoop findings transfer, and BF additionally gives us the MP reference Rogue lacked.

## Why Black Flag (vs Rogue)

| | Black Flag | Rogue |
|---|---|---|
| Single-player exe | `AC4BFSP.exe` (x86, 43 MB) | `ACC.exe` (x64) |
| Multiplayer exe | **`AC4BFMP.exe`** ✓ (oracle) | *(none)* |
| Named anchors | `g_MainPlayerPosition`, `PlayerSpawnEvent`, `SpawnPlayerParams` | fewer |

## Phased plan (each phase has an oracle; nothing is "done" without one)

| # | Deliverable | Oracle | Needs |
|---|---|---|---|
| **B0** | Recon: exe pinned, Ghidra analysed, engine anchors mapped | anchors found | this doc |
| **B1** | Read the local player transform each frame (plugin) | in-game values track walking | B0 |
| **B2** | UDP transport between two clients | plugin log shows `peer=1` on both sides (loopback verified: 2,839/2,839 packets) | 2nd machine (pending) |
| **B3** | **Remote avatar exists** at the peer transform | ✔ done — hijacked crowd body driven from packets; the user watched it circle them | B2 loopback |
| **B4** | Action/anim-state sync (locomotion + parkour) | two players vault/climb the same wall | B3 |
| **B5** | Havana tandem-parkour test | run/leap/climb together, recording looks right | B4 |

## The identity of the hard part

B3 is the gate (same as Rogue). The lead is `AC4BFMP.exe`: it ships `NetPlayer`,
`S2C_SetMoveReplicationMode`, `M2R_ReplicateEnterCustomActionState`, `SpawnPlayerParams`, `avatarID`
— i.e. a working example of a networked AnvilNext character. We reverse how BF MP **represents and
spawns** a networked avatar, then reproduce it in the SP exe.

## Risks

| Risk | Sev | Mitigation |
|---|---|---|
| **The haunting (hijacked body is streamed away / re-picked)** | **CRITICAL (the current blocker)** | **P1 persist-hijack**: detach the body from the streaming/cull registration; oracle = the body survives a zone crossing. If the detach proves impossible, fall back to a pooled-body scheme (multiple pinned bodies near the peer). |
| Second, drivable avatar (B3) | solved as a *visible* body | hijack + per-frame drive, user-confirmed; but see the haunting row above — visible ≠ sustained. |
| Runtime entity creation (spawn route) | **CLOSED — do not retry** | engine creates characters only at world load; mid-game creation chokes the renderer (repeated freezes). |
| Ghost looks like the protagonist (outfit/model) | med | mod pipeline proven (extract -> edit -> reimport, same-size only); target = a chosen crowd variant -> assassin; the game ships generic assassin models/textures. |
| Partner marker/HUD | low-med | D3D overlay + world->screen projection via the readable camera matrices. |
| Ghost UDP ports on this PC (bind 10048) | low | dead session keeps the port; reboot or fresh LocalPort + mirror. |
| Cross-machine entity identity (kills/events) | med | both players run the same mission/save -> NPCs match; match kills by type+position; 64-bit entity ids exist. |
| Parkour animation sync (B4 play) | high | discrete custom-action events (BF MP's scheme); accept coarse motion first. |
| Launch wedge (unkillable game exe) | med | one launch per boot; quit cleanly; crash-isolated hooks; the machine accumulates instability after many forced kills — reboot after crashes. |
| Effort | high | phased; P1/P2 are low-risk and independently useful. |

## Safety

Offline/LAN only; AC4 has no anti-cheat and we touch no online servers. Never run BF MP online /
never mod its live PvP (reverse it offline only). Back up saves first. Ship code only; no game files
or decompiled output. Ask before driving input or publishing.

## Design v1.1 (current, 2026-10-06)

- **Read:** player feet via `mgr(0x02ABE588) -> +0x4C -> holder -> camobj -> +0x68 -> block ->
  +0x174 -> provider`; feet = `provider+0x110`, facing = `provider+0x100`. (The camera ring is the
  camera; `block+0x50` is the eye = feet + ~1.2 m.)
- **Write:** the character node (class vtable `0x01E4CE90`, **0x100 bytes**) — matrix translation at
  `+0x40` (feet) plus yaw rows `+0x10`/`+0x20`. Writing it teleports the character
  (user-confirmed); per-frame in-process writes win the render; the AI takes over when writes stop.
- **Body pick:** same class + marker `+0x68` + `f7c == -0.50` + **children >= 16**; nearest to the
  *peer's* position (pulled in from up to 200 m); never within 2.5 m of the local player.
- **Loop:** the `Ai::UpdateCamera` hook runs every frame: publish local feet (throttled 20 Hz), poll
  the peer, steer the ghost (lerp 0.28/frame, hard snap past 20 m); a stale (>2 s) or `(0,0,0)`
  peer sample releases the body.
- **Config (live-reloads):** `[Coop]` Enabled / RemoteIp1..4 / RemotePort / LocalPort / ClientId /
  SendHz / BodyDrive / BodyMinChildren / BodyMaxDist.
- **Gotchas:** the game pauses on focus loss (scans must wait for real movement); PrintWindow
  screenshots are stale for this game (use user reports / CopyFromScreen); PowerShell aliases
  (`rd`, `rp`, `rm`, `dir`) have broken several helper scripts; WOW64 breakpoints arrive as
  `0x4000001F`, not `0x80000003`; the puppet node is exactly 0x100 bytes — fields past it belong to
  neighbours.
- **Tools:** the kept set is documented in `tools/README.md` (core: `bp-capture-param2.ps1`,
  `fake_peer_send.ps1`, `drag-body-test.ps1`, the diff/snapshot pair for the model work).
