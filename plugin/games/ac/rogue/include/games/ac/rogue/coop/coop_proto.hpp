// AccCoop wire protocol (plugin copy). Keep in lockstep with
// acc-coop/common/coop_proto.h and acc-coop/tools/fake_peer.py.
#pragma once

#include <cstdint>
#include <cstring>

namespace games::ac::rogue::coop {

constexpr std::uint32_t kMagic   = 0x50524341U; // 'A','C','R','P'
constexpr std::uint16_t kVersion = 1;
constexpr int           kEnvelopeBytes = 16;

enum class MsgType : std::uint16_t {
    Player   = 1,
    Entities = 2,
    Event    = 3,
};

constexpr std::uint16_t kFlagValid    = 1U << 0;
constexpr std::uint16_t kFlagAlive    = 1U << 1;
constexpr std::uint16_t kFlagOnShip   = 1U << 2;
constexpr std::uint16_t kFlagCrouch   = 1U << 3;
constexpr std::uint16_t kFlagInCombat = 1U << 4;

#pragma pack(push, 1)
struct Envelope {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t type;
    std::uint32_t seq;
    std::uint32_t client_id;
};
static_assert(sizeof(Envelope) == 16);

struct PlayerPayload {
    float         px;
    float         py;
    float         pz;
    float         qx;
    float         qy;
    float         qz;
    float         qw;
    float         vx;
    float         vy;
    float         vz;
    float         health;
    std::uint32_t anim_state;
    std::uint32_t tick_ms;
    std::uint32_t ack_seq;
};
static_assert(sizeof(PlayerPayload) == 56);
#pragma pack(pop)

static_assert(sizeof(Envelope) + sizeof(PlayerPayload) == 72);

} // namespace games::ac::rogue::coop
