// BFCoop combat sync (P4): watch NPC health objects for damage/death (TX), relay the
// outcome over the event channel, and apply matching damage/kills locally (RX).
//
// Verified live 2026-10-08:
//   LIFE u16 @ +0x5C, MAX u16 @ +0x5E, flags u32 @ +0x60 (bit 0x01000000 = dead).
//   A visible kill = LIFE := 0xFFFF + flags |= 0x01000000 (two raw writes; user-watched).
#pragma once

#include <cstdint>

#include "games/ac/blackflag/coop/coop_net.hpp"

namespace games::ac::blackflag::coop::combat {
    // [Coop] CombatSync - enable the watch + relay + apply primitives.
    void set_enabled(bool on);

    // [Coop] CombatKillTest - dev one-shot: kill the first tracked NPC via the proven writes.
    void set_kill_test(bool on);

    // Called once per frame from the PlayerTransform hook (game thread). Internally
    // rate-limited (5 Hz logic, incremental scans). The heavy scans only run in-world.
    void tick(bool in_world);

    // Handle one received coop event (call from the net drain loop). Applies NPC combat
    // events to the local world (position + max-HP matching).
    void on_event(const CoopEvent &ev);

    struct Status {
        bool enabled = false;
        int  tracked = 0;
        int  events  = 0;
    };
    auto status() -> Status;
} // namespace games::ac::blackflag::coop::combat
