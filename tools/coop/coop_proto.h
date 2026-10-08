// AccCoop wire protocol — UDP messages between two AC Rogue clients.
//
// One datagram = one message. Little-endian, fixed layout, no padding. This header is the single
// source of truth shared by the in-game plugin (C++) and the M1 oracle (tools/fake_peer.py);
// tools/fake_peer.py --selftest asserts every layout below.
//
//   Envelope (16 B) then a payload:
//     Player   : Envelope + PlayerPayload                      (72 B total)
//     Entities : Envelope + EntityHeader + count*EntityState   (24 B + 28 B/entity)
//     Event    : Envelope + EventHeader                        (28 B)
#pragma once
#include <cstdint>
#include <cstring>

namespace acccoop {

constexpr uint32_t kMagic   = 0x50524341U; // 'A','C','R','P'
constexpr uint16_t kVersion = 1;
constexpr int kEnvelopeBytes = 16;
constexpr int kMaxEntities   = 512;

enum class MsgType : uint16_t {
    Player   = 1, // one client's own player state
    Entities = 2, // a host snapshot of replicated world entities
    Event    = 3, // a reliable discrete event (kill, board, ...)
};

enum class EventKind : uint16_t {
    Kill      = 1, // target NPC dies
    Knockout  = 2, // target NPC knocked out
    Damage    = 3, // target took damage (arg_f = amount)
    Alarm     = 4, // target became alerted
    BoardShip = 5, // target ship boarded
    EnterShip = 6, // actor entered ship
    ExitShip  = 7,
    Spawn     = 8, // entity spawned (id in target_id)
    Despawn   = 9,
};

// common per-entity flags
constexpr uint16_t kFlagValid    = 1U << 0;
constexpr uint16_t kFlagAlive    = 1U << 1;
constexpr uint16_t kFlagOnShip   = 1U << 2;
constexpr uint16_t kFlagCrouch   = 1U << 3;
constexpr uint16_t kFlagInCombat = 1U << 4;
constexpr uint16_t kFlagFrozen   = 1U << 5; // client: local AI suppressed for this entity

#pragma pack(push, 1)
struct Envelope
{
    uint32_t magic;      //  0
    uint16_t version;    //  4
    uint16_t type;       //  6  MsgType
    uint32_t seq;        //  8
    uint32_t client_id;  // 12
};
static_assert(sizeof(Envelope) == kEnvelopeBytes);

struct PlayerPayload
{
    float    px, py, pz;   // world position
    float    qx, qy, qz, qw; // orientation quaternion
    float    vx, vy, vz;   // units/s
    float    health;
    uint32_t anim_state;   // opaque, peer-defined
    uint32_t tick_ms;      // sender clock
    uint32_t ack_seq;      // newest remote seq seen
};
static_assert(sizeof(PlayerPayload) == 56);

struct EntityHeader
{
    uint16_t count;      // number of EntityState that follow
    uint16_t flags;      // reserved
    uint32_t host_tick;  // host clock for this snapshot
};
static_assert(sizeof(EntityHeader) == 8);

struct EntityState
{
    uint32_t id;         // stable cross-machine entity id (the identity problem)
    float    x, y, z;
    float    yaw;
    uint32_t anim_state;
    uint16_t flags;
    uint16_t pad;
};
static_assert(sizeof(EntityState) == 28);

struct EventHeader
{
    uint16_t kind;       // EventKind
    uint16_t arg;        // small integer arg
    uint32_t target_id;
    float    arg_f;
};
static_assert(sizeof(EventHeader) == 12);
#pragma pack(pop)

inline Envelope make_env(MsgType type, uint32_t client_id, uint32_t seq)
{
    Envelope e{};
    e.magic = kMagic;
    e.version = kVersion;
    e.type = static_cast<uint16_t>(type);
    e.client_id = client_id;
    e.seq = seq;
    return e;
}

inline bool header_ok(const void* buf, size_t len, Envelope& out)
{
    if (len < sizeof(Envelope)) return false;
    std::memcpy(&out, buf, sizeof(Envelope));
    return out.magic == kMagic && out.version == kVersion;
}

} // namespace acccoop
