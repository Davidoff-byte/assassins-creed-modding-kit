// AccCoop UDP transport: publishes the local player sample and receives the peer's.
// All functions are called from the game thread (the PlayerTransform callback) except
// configure(), which the config watcher thread calls on reload.
#pragma once

#include <cstdint>
#include <string>

namespace games::ac::rogue::coop {

struct NetConfig {
    bool          enabled     = false;
    std::string   remote_host = "127.0.0.1";
    std::uint16_t remote_port = 27700;
    std::uint16_t local_port  = 27700;
    std::uint32_t client_id   = 1;
    float         send_hz     = 20.0F;
};

struct RemotePlayer {
    bool          valid     = false;
    std::uint32_t client_id = 0;
    float         px = 0.0F;
    float         py = 0.0F;
    float         pz = 0.0F;
    float         qx = 0.0F;
    float         qy = 0.0F;
    float         qz = 0.0F;
    float         qw = 1.0F;
    std::uint32_t tick_ms = 0;
};

// (Re)binds the socket and resolves the destination. Safe to call repeatedly; an
// empty/disabled config closes any existing socket.
void configure(const NetConfig &cfg);
void shutdown();

// Sends the local sample, throttled to NetConfig::send_hz. No-op when disabled.
// anim_state packs the locomotion/parkour state (0 idle,1 walk,2 jog,3 sprint,4 climb).
void publish(float px, float py, float pz,
             float qx, float qy, float qz, float qw,
             std::uint32_t anim_state);

// Non-blocking receive; updates latest_remote().
void poll();

[[nodiscard]] auto latest_remote() -> RemotePlayer;

} // namespace games::ac::rogue::coop
