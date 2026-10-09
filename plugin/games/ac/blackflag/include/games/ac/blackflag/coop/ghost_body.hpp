// BFCoop ghost body: steers one local humanoid character from the peer's network
// sample, so the other player appears as a walking person in this world.
// Driven from the PlayerTransform hook once per frame (game thread).
#pragma once

#include <cstdint>

#include "games/ac/blackflag/coop/coop_net.hpp"

namespace games::ac::blackflag::coop::ghost {
    // Enable/disable (config: [Coop] BodyDrive).
    void set_enabled(bool on);

    // P3: replay the peer's packed action state (phase/hang/flags) onto the ghost
    // body's controller each frame (config: [Coop] AnimDrive). Read side = B4.
    void set_anim_drive(bool on);

    // Dev/RE: read-only probe of the ghost body's animation objects (config: [Coop] AnimProbe).
    // Logs the body+0xE8 target's class + memory windows and any field changes while driven.
    void set_anim_probe(bool on);

    // P1 fix: move the body through the engine's own transform setter (notify chain)
    // instead of raw matrix writes (config: [Coop] ApiMove).
    void set_api_move(bool on);

    // Picker tuning (config: BodyMinChildren / BodyMaxDist).
    // min_children == 0 keeps defaults. Real crowd bodies have 18-19 children;
    // inactive proxies have 8-14 and never render.
    void set_params(int min_children, float max_dist);

    // Called every frame from the PlayerTransform hook (game thread).
    // (lx, ly, lz) is the local player's feet position; used to pick a body near
    // the player and to never grab the local player's own object.
    void tick(float lx, float ly, float lz, const RemotePlayer &remote);

    struct Status {
        bool           enabled    = false;
        bool           have_body  = false;
        std::uintptr_t body       = 0;
        float          dist       = 0.0F; // body distance to the local player
        bool           peer_fresh = false;
    };
    auto status() -> Status;
} // namespace games::ac::blackflag::coop::ghost
