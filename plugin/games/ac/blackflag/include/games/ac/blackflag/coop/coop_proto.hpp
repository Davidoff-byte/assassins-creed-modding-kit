// AccCoop wire protocol (plugin copy). Keep in lockstep with
// acc-coop/common/coop_proto.h and acc-coop/tools/fake_peer.py.
#pragma once

#include <cstdint>
#include <cstring>

namespace games::ac::blackflag::coop {

constexpr std::uint32_t kMagic   = 0x50524341U; // 'A','C','R','P'
constexpr std::uint16_t kVersion = 1;
constexpr int           kEnvelopeBytes = 16;

enum class MsgType : std::uint16_t {
    Player   = 1,
    Entities = 2,
    Event    = 3,
    Hello    = 4,
    Welcome  = 5,
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

// --- C1 session (host/join handshake) ---

struct HelloPayload {
    std::uint16_t proto_ver;
    std::uint16_t reserved;
    std::uint32_t save_fp; // reserved: both players must run the same mission/save (0 = unchecked)
    char          name[32];
};
static_assert(sizeof(HelloPayload) == 40);

struct WelcomePayload {
    std::uint32_t session_id;
    std::uint32_t host_id;
    std::uint32_t save_fp;
    char          host_name[32];
};
static_assert(sizeof(WelcomePayload) == 44);

// --- event channel (parkour actions, kills, markers; reliable-ish with resend + ack) ---

enum class EventKind : std::uint16_t {
    Action = 1, // parkour/custom-action enter/exit (P3)
    Kill   = 2, // NPC killed (P4; host-authoritative)
    Marker = 3, // identity/name refresh (P2)
    Ping   = 4,
    NpcCombat = 5, // NPC damage/kill relay (P4): payload = NpcCombatPayload (20 B)
};

struct EventPayload {
    std::uint16_t kind;
    std::uint16_t data_len;
    std::uint32_t event_id;
    std::uint8_t  data[40];
};
static_assert(sizeof(EventPayload) == 48);

} // namespace games::ac::blackflag::coop
