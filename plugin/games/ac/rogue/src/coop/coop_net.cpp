#include "games/ac/rogue/coop/coop_net.hpp"

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>

#include <WinSock2.h>
#include <ws2tcpip.h>
#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "games/ac/rogue/coop/coop_proto.hpp"

#pragma comment(lib, "ws2_32.lib")

namespace games::ac::rogue::coop {
    namespace {
        constexpr int k_max_recv_per_poll = 16;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::mutex        g_mtx;
        SOCKET            g_sock = INVALID_SOCKET;
        sockaddr_in       g_dst {};
        bool              g_enabled = false;
        std::uint32_t     g_client_id = 1;
        std::uint32_t     g_seq = 0;
        float             g_send_hz = 20.0F;
        std::int64_t      g_send_interval = 0;
        std::int64_t      g_last_send = 0;
        std::int64_t      g_qpc_freq = 0;
        bool              g_wsa = false;
        RemotePlayer      g_remote;
        std::atomic<bool> g_remote_valid {false};
#pragma clang diagnostic pop

        void close_locked() {
            if (g_sock != INVALID_SOCKET) {
                closesocket(g_sock);
                g_sock = INVALID_SOCKET;
            }
            g_enabled = false;
        }

        struct Wire {
            Envelope      env;
            PlayerPayload p;
        };
        static_assert(sizeof(Wire) == 72);
    } // namespace

    void shutdown() {
        std::lock_guard lock(g_mtx);
        close_locked();
        g_remote_valid.store(false, std::memory_order_relaxed);
    }

    void configure(const NetConfig &cfg) {
        std::lock_guard lock(g_mtx);
        close_locked();
        g_remote_valid.store(false, std::memory_order_relaxed);

        if (!cfg.enabled) {
            log::get()->info("CoopNet: disabled");
            return;
        }
        if (!g_wsa) {
            WSADATA wsa {};
            if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
                log::get()->error("CoopNet: WSAStartup failed");
                return;
            }
            g_wsa = true;
        }
        if (g_qpc_freq == 0) {
            LARGE_INTEGER f {};
            QueryPerformanceFrequency(&f);
            g_qpc_freq = f.QuadPart;
        }

        const SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (s == INVALID_SOCKET) {
            log::get()->error("CoopNet: socket() failed: {}", WSAGetLastError());
            return;
        }

        sockaddr_in bind_addr {};
        bind_addr.sin_family      = AF_INET;
        bind_addr.sin_port        = htons(cfg.local_port);
        bind_addr.sin_addr.s_addr = INADDR_ANY;
        if (bind(s, reinterpret_cast<sockaddr *>(&bind_addr), sizeof(bind_addr)) == SOCKET_ERROR) {
            log::get()->error("CoopNet: bind udp/{} failed: {}", cfg.local_port, WSAGetLastError());
            closesocket(s);
            return;
        }
        u_long nonblock = 1; // NOLINT(misc-const-correctness)
        ioctlsocket(s, FIONBIO, &nonblock);

        sockaddr_in dst {};
        dst.sin_family = AF_INET;
        dst.sin_port   = htons(cfg.remote_port);
        if (InetPtonA(AF_INET, cfg.remote_host.c_str(), &dst.sin_addr) != 1) {
            log::get()->error("CoopNet: bad RemoteHost '{}'", cfg.remote_host);
            closesocket(s);
            return;
        }

        g_sock          = s;
        g_dst           = dst;
        g_client_id     = cfg.client_id;
        g_send_hz       = cfg.send_hz > 0.0F ? cfg.send_hz : 20.0F;
        g_send_interval = static_cast<std::int64_t>(static_cast<double>(g_qpc_freq) / g_send_hz);
        g_last_send     = 0;
        g_enabled       = true;
        log::get()->info("CoopNet: udp/{} -> {}:{} as client {}, {:.0f} Hz",
                         cfg.local_port,
                         cfg.remote_host,
                         cfg.remote_port,
                         cfg.client_id,
                         g_send_hz);
    }

    void publish(float px, float py, float pz,
                 float qx, float qy, float qz, float qw,
                 std::uint32_t anim_state) {
        std::lock_guard lock(g_mtx);
        if (!g_enabled || g_sock == INVALID_SOCKET) {
            return;
        }
        LARGE_INTEGER now {};
        QueryPerformanceCounter(&now);
        if (g_last_send != 0 && now.QuadPart - g_last_send < g_send_interval) {
            return;
        }
        g_last_send = now.QuadPart;

        Wire msg {};
        msg.env.magic     = kMagic;
        msg.env.version   = kVersion;
        msg.env.type      = static_cast<std::uint16_t>(MsgType::Player);
        msg.env.seq       = ++g_seq;
        msg.env.client_id = g_client_id;
        msg.p.px = px;
        msg.p.py = py;
        msg.p.pz = pz;
        msg.p.qx = qx;
        msg.p.qy = qy;
        msg.p.qz = qz;
        msg.p.qw = qw;
        msg.p.health     = 100.0F;
        msg.p.anim_state = anim_state;
        msg.p.tick_ms    = g_qpc_freq > 0
                               ? static_cast<std::uint32_t>((now.QuadPart * 1000) / g_qpc_freq)
                               : 0;
        msg.p.ack_seq = 0;

        sendto(g_sock,
               reinterpret_cast<const char *>(&msg),
               sizeof(msg),
               0,
               reinterpret_cast<sockaddr *>(&g_dst),
               sizeof(g_dst));
    }

    void poll() {
        std::lock_guard lock(g_mtx);
        if (!g_enabled || g_sock == INVALID_SOCKET) {
            return;
        }
        for (int i = 0; i < k_max_recv_per_poll; ++i) {
            std::uint8_t buf[512];
            const int n = recvfrom(g_sock,
                                   reinterpret_cast<char *>(buf),
                                   sizeof(buf),
                                   0,
                                   nullptr,
                                   nullptr);
            if (n <= 0) {
                break;
            }
            if (n < static_cast<int>(sizeof(Envelope))) {
                continue;
            }
            Envelope env {};
            std::memcpy(&env, buf, sizeof(env));
            if (env.magic != kMagic || env.version != kVersion) {
                continue;
            }
            if (env.type == static_cast<std::uint16_t>(MsgType::Player) &&
                n >= static_cast<int>(sizeof(Envelope) + sizeof(PlayerPayload))) {
                PlayerPayload p {};
                std::memcpy(&p, buf + sizeof(Envelope), sizeof(p));
                g_remote.valid     = true;
                g_remote.client_id = env.client_id;
                g_remote.px = p.px;
                g_remote.py = p.py;
                g_remote.pz = p.pz;
                g_remote.qx = p.qx;
                g_remote.qy = p.qy;
                g_remote.qz = p.qz;
                g_remote.qw = p.qw;
                g_remote.tick_ms = p.tick_ms;
                g_remote_valid.store(true, std::memory_order_relaxed);
            }
        }
    }

    auto latest_remote() -> RemotePlayer {
        std::lock_guard lock(g_mtx);
        return g_remote;
    }
} // namespace games::ac::rogue::coop
