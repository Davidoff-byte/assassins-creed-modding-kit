# BF Co-op — capability assessment & build roadmap (2026-10-08)

What we can **properly build** with the proven stack, what is a focused **research push**, and
what is **out of reach** for a two-instance SP-exe mod. Ordered by value/feasibility.

## Proven foundations (already real)

- Netcode: UDP session handshake, 20 Hz state stream, acked event channel (C1 verified live,
  2 machines).
- Engine-native body driving (smooth matrix setter + notify chain), nearest-body picker,
  path replay (delayed trail), warp detection.
- Visual control: forge def-swap pipeline (TOC redirect + identity-hash patch + private EOF
  copies). Proven: assassin + Duncan Walpole on any adopted body.
- Persistence: despawn pin (private vtable, delete blocked) — bodies survive streaming;
  360 m cross-map journeys with zero losses.
- Instrumentation: CullWatch, StateProbe (reads the player's locomotion state), crash-dump
  triage, full decompiled corpus with an SQL index.

## Tier 1 — buildable now (each is days, all reuse proven pieces)

1. **Synced animations / locomotion mirror** *(in progress)*: map the player controller's
   state codes (walk/run/sprint/climb/vault/swim/crouch) via StateProbe, then write them to
   the ghost's controller (same class). Gives the partner matching animations including
   climbing.
2. **Session lifecycle**: spawn the ghost beside the player on join; clean release on leave;
   save/level fingerprint check (the hello packet already has an unused `save_fp` field) so
   mismatched worlds are detected and warned instead of looking broken.
3. **Partner marker + name tag**: rewrite the parked overlay as a stable mid-hook; floating
   tag over the ghost, configurable.
4. **Scene awareness (the interior problem)**: the bureau/interior sub-scenes use local
   coordinates; the ghost teleports to nonsense there. Send a scene id in the state packet
   and hide the ghost while the remote is in a sub-scene instead of misplacing it.
5. **Health/state HUD**: stream the partner's health; show on the marker; sync basic stances
   (combat/crouch/sit) as part of the state mirror.
6. **Emotes / gestures**: bind a key -> event packet -> ghost plays the mapped state.

## Tier 2 — focused research pushes (weeks; each unlocks a headline feature)

7. **True spawned companion (no hijack)**: finish the one mapped experiment — spawn an
   `Entity` with a real key pair (CRC32 class ids known, template catalog mapped), feed
   deserialize + registration. Then the companion is engine-created, owned by us: def-swap
   for the look, pin for persistence, despawn on leave. The "proper" architecture.
8. **Ship co-op (passenger mode)**: while the remote is aboard their ship, spawn/drive the
   ghost on the deck as crew (crew def-swap exists). Full ship physics/cannon sync is NOT
   in this item — passenger presence is.
9. **World interaction for the partner**: make the ghost noticed by the world — guards
   reacting, collisions. Requires giving the body real AI/world presence instead of pure
   matrix driving; several engine systems (crowd, nav, combat) must be tamed. High risk,
   high reward.

## Out of reach (with this approach, honestly)

- **Engine-level co-simulation** (two machines sharing one dynamic world: missions, AI,
  physics in lockstep). The SP engine has no netcode; we build presence + illusion, not
  a second simulated world.
- **Full interactive second player** (combat, looting, climbing with collision, driving
  the same systems as the local hero). That is effectively a from-scratch networked
  character controller over a reverse-engineered engine — a research programme, not a mod
  iteration.
- **Join-in-progress mission state sync / instancing** (engine internals, no hooks exist
  for this layer).

## Recommended order

1. Finish synced animations (state mirror) — makes the partner feel alive. *(in progress)*
2. Session lifecycle + save fingerprint + scene awareness — makes it feel *correct*.
3. Marker + name tag — makes it readable.
4. Spawned companion — makes it *ours* (no borrowed bodies ever).
5. Ship passenger mode — the AC4 co-op moment everyone wants.

## Netcode scope � "why not just write host/join P2P?"

The socket layer is ALREADY ours: P2P host/join over UDP (handshake, roles, session, 20 Hz
state, acked event channel) � written from scratch, verified on two machines. Upgrading it
is pure software: NAT punchthrough + rendezvous, relay fallback, reliable channel, crypto,
reconnect, versioning. Any of those can be built on request; none of them is the wall.

The wall is not the netcode - it is that the GAME has no synchronizable world model:

- Lockstep (both machines simulate the same world) requires determinism the engine does not
  have: multithreaded job systems, timing-dependent animation/physics/crowd streaming,
  per-process RNG. Not recoverable by modding.
- State replication (the way real multiplayer works) requires the engine to have entity
  identity, authority, interest management and remote proxies for EVERY subsystem
  (AI, combat, missions, ships, streaming). This engine has none of that: entities are raw
  pointers with no network ids, and only one player exists by design.

Therefore the only viable architecture is the one being built: two independent local worlds,
and we replicate the PARTNER (presentation) between them: body, look, motion, state,
animations, later combat - a Ghost-Recon-style remote proxy. World authority stays local,
so missions/AI/world events are never shared.

Practical implications:
- Netcode upgrades (internet P2P, reliability, crypto): buildable NOW, no engine knowledge.
- Proxy interactivity (animations, combat, reactions): built feature by feature on top of
  the mapped engine internals - each is bespoke and partial.
- True world co-simulation: out of scope for this engine (would be a rewrite of the runtime,
  not a mod).

## Combat co-op (host-authoritative) � the achievable "clear enemies together"

Not impossible - it is a tiered build. Architecture: host's world stays authoritative for
combat outcomes; the guest's own world provides the visuals; the two are kept in sync by
relaying combat EVENTS (not world state). Working title: "linked instances".

Build order (each stage is playable):

1. C3.1 Link matching: identify which local NPC corresponds to which remote NPC
   (type + world position + stderr). No engine support needed - body objects expose
   position and class; matching is ours.
2. C3.2 Damage relay: when the guest hits their local twin, read who they hit (the engine
   knows the player's current target - it drives lock-on/aim assist), send a damage event
   (position, type, amount) over the existing event channel. The host applies it to its
   matched NPC by calling ITS OWN damage path (corpus: NPC damage/take-hit functions).
   Host-side hits relay the same way to the guest.
3. C3.3 Death sync: the host resolves death (authoritative) -> relay kill event -> the
   guest invokes its own local kill path on the matched twin. Both sides see the same
   enemies fall.
4. C3.4 Guest health/death/respawn: plugin-side HP for the guest's proxy; enemies' attacks
   near the proxy relay damage to the guest (visual feedback + death/respawn managed by the
   plugin, respawn beside the host player).
5. C3.5 Enemies react to the guest (research): feed the guest proxy into the host's AI
   perception so guards target it like a real player. Engine perception system must be
   mapped; the payoff is symmetric combat.

What this is NOT: lockstep co-simulation (missions/AI/physics parity). Mission scripting
stays single-player; combat pockets (forts, camps, ships, streets) are where this shines.

Open RE list for combat: NPC damage function, NPC death/kill path, player current-target
field, health field per NPC, attack/hit event origins. All findable in the existing corpus
+ live probes.

## REVISION (post PS3 debug build) - what co-op is reachable now

The PS3 submission build (full DWARF + 467k symbols + AI GameTree XMLs, engine "Scimitar")
collapses blind-RE cost. Revised reachability:

REAL NOW (this week's level)
- Partner character: any model, follows everywhere, persistent, animated (state mirror,
  now with exact named state machines).

HIGH CONFIDENCE (weeks)
- Combat relay: both players damage/kill the SAME enemies; engine's own DamageEvent +
  CSrvNPCHealth (Life/MaxLife/KO/Incapacitated/IsGoingToDie) carry hit reactions/deaths.
  Forts, camps, street fights become genuinely co-op.
- Partner health/death/respawn (relayed damage, respawn beside host).
- Marker/name tag (named UIUtils helpers).
- Exact parkour/locomotion animations (climb states named).

PLAUSIBLE (pushes, now tractable)
- Enemies target the partner too (perception/sensor systems + GameTree configs).
- Partner as ship crew / passenger (naval combat stays host-side).
- Loot/chest and side-activity relays.
- AI/nav-driven partner movement (engine nav instead of matrix driver).

OUT (honest)
- Mission/cutscene/quest state sync (separate script worlds).
- One shared simulation (architecture stays: two worlds + replicated partner).
- Full native-like second player (research program, not an iteration).

KEY DEPENDENCY: PS3 -> PC symbol porter (fingerprint matcher). Start with health/combat/
anim families; verify every layout live (build revisions may differ).
