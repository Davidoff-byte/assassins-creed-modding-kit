#include "games/ac/blackflag/coop/coop_net.hpp"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <set>
#include <string>
#include <vector>

#include <WinSock2.h>
#include <ws2tcpip.h>
#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "games/ac/blackflag/coop/coop_proto.hpp"

#pragma comment(lib, "ws2_32.lib")

namespace games::ac::blackflag::coop {
    namespace {
        constexpr int k_max_recv_per_poll = 16;

        // C1 handshake cadence.
        constexpr std::int64_t k_hello_interval_ms   = 500;
        constexpr std::int64_t k_hello_resync_ms     = 5000; // guest keepalive once established
        constexpr std::int64_t k_welcome_interval_ms = 250;
        // Event channel: resend an unacked event every 250 ms, give up after 8 sends.
        constexpr std::int64_t  k_event_resend_ms  = 250;
        constexpr std::uint32_t k_event_max_sends  = 8;
        constexpr std::int64_t  k_peer_timeout_ms  = 5000;
        constexpr std::size_t   k_outbox_max       = 32;
        constexpr std::size_t   k_inbox_max        = 256;
        constexpr std::size_t   k_event_data_max   = sizeof(EventPayload::data);
        constexpr std::size_t   k_recv_id_keep     = 64;

        struct OutboxEntry {
            std::uint32_t id      = 0;
            std::uint16_t kind    = 0;
            std::uint16_t len     = 0;
            std::uint8_t  data[40] {};
            std::int64_t  last_send_ms = 0;
            std::uint32_t sends        = 0;
        };

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::mutex        g_mtx;
        SOCKET            g_sock = INVALID_SOCKET;
        sockaddr_in       g_dst {};
        std::uint16_t     g_local_port = 0;
        std::uint16_t     g_remote_port = 0;
        std::string       g_remote_host;
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

        // --- C1 session state ---
        bool          g_is_host      = false;
        std::string   g_player_name  = "player";
        std::uint32_t g_session_id   = 0;
        bool          g_established  = false;
        std::uint32_t g_peer_id      = 0;
        std::string   g_peer_name;
        std::int64_t  g_last_rx_ms      = 0;
        std::int64_t  g_last_hello_ms   = 0;
        std::int64_t  g_last_welcome_ms = 0;
        bool          g_warned_role     = false;

        // --- event channel ---
        std::uint32_t           g_next_event_id = 1;  // next id we assign
        std::uint32_t           g_ack_contig    = 0;  // all event ids <= this were received (cum-ack)
        std::set<std::uint32_t> g_recv_ids;           // out-of-order ids above the contiguous mark
        std::vector<OutboxEntry> g_outbox;            // unacked, waiting for retransmit
        std::vector<CoopEvent>   g_inbox;             // received, waiting for drain_events()
#pragma clang diagnostic pop

        auto now_ms() -> std::int64_t {
            LARGE_INTEGER c {};
            QueryPerformanceCounter(&c);
            if (g_qpc_freq <= 0) {
                return 0;
            }
            return (c.QuadPart * 1000) / g_qpc_freq;
        }

        // Bind-retry: if the UDP port is transiently held (a dead game process may
        // keep it for minutes), remember the desired config and retry in the
        // background instead of staying offline until the next ini poke.
        bool         g_retry_pending = false;
        std::int64_t g_retry_at_ms   = 0;
        NetConfig    g_retry_cfg {};

        void configure_locked(const NetConfig &cfg); // fwd - defined below

        void maybe_retry_bind_locked() {
            if (!g_retry_pending || g_qpc_freq <= 0 || now_ms() < g_retry_at_ms) {
                return;
            }
            configure_locked(g_retry_cfg);
        }

        auto bounded_len(const char *s, std::size_t cap) -> std::size_t {
            std::size_t n = 0;
            while (n < cap && s[n] != '\0') {
                ++n;
            }
            return n;
        }

        void close_locked() {
            if (g_sock != INVALID_SOCKET) {
                closesocket(g_sock);
                g_sock = INVALID_SOCKET;
            }
            g_enabled       = false;
            g_local_port    = 0;
            g_remote_port   = 0;
            g_remote_host.clear();
            g_established   = false;
            g_peer_id       = 0;
            g_peer_name.clear();
            g_session_id    = 0;
            g_last_rx_ms    = 0;
            g_last_hello_ms = 0;
            g_last_welcome_ms = 0;
            g_warned_role   = false;
            g_next_event_id = 1;
            g_ack_contig    = 0;
            g_recv_ids.clear();
            g_outbox.clear();
            g_inbox.clear();
        }

        struct Wire {
            Envelope      env;
            PlayerPayload p;
        };
        static_assert(sizeof(Wire) == 72);

        void send_raw_locked(std::uint16_t type, const void *payload, std::uint16_t len) {
            if (g_sock == INVALID_SOCKET) {
                return;
            }
            if (len > 64) {
                len = 64;
            }
            std::uint8_t buf[sizeof(Envelope) + 64] {};
            Envelope env {};
            env.magic     = kMagic;
            env.version   = kVersion;
            env.type      = type;
            env.seq       = ++g_seq;
            env.client_id = g_client_id;
            std::memcpy(buf, &env, sizeof(env));
            if (payload != nullptr && len > 0) {
                std::memcpy(buf + sizeof(Envelope), payload, len);
            }
            sendto(g_sock,
                   reinterpret_cast<const char *>(buf),
                   static_cast<int>(sizeof(Envelope) + len),
                   0,
                   reinterpret_cast<sockaddr *>(&g_dst),
                   sizeof(g_dst));
        }

        void send_hello_locked() {
            HelloPayload h {};
            h.proto_ver = kVersion;
            h.save_fp   = 0;
            const std::size_t n = std::min(g_player_name.size(), sizeof(h.name) - 1);
            std::memcpy(h.name, g_player_name.data(), n);
            send_raw_locked(static_cast<std::uint16_t>(MsgType::Hello), &h, sizeof(h));
            g_last_hello_ms = now_ms();
        }

        void send_welcome_locked() {
            WelcomePayload w {};
            w.session_id = g_session_id;
            w.host_id    = g_client_id;
            w.save_fp    = 0;
            const std::size_t n = std::min(g_player_name.size(), sizeof(w.host_name) - 1);
            std::memcpy(w.host_name, g_player_name.data(), n);
            send_raw_locked(static_cast<std::uint16_t>(MsgType::Welcome), &w, sizeof(w));
            g_last_welcome_ms = now_ms();
        }

        void send_event_locked(const OutboxEntry &e) {
            EventPayload p {};
            p.kind     = e.kind;
            p.data_len = e.len;
            p.event_id = e.id;
            if (e.len > 0) {
                std::memcpy(p.data, e.data, e.len);
            }
            send_raw_locked(static_cast<std::uint16_t>(MsgType::Event), &p, sizeof(p));
        }

        // Handshake keepalive + event retransmits. Must hold g_mtx.
        void housekeeping_locked() {
            if (!g_enabled || g_sock == INVALID_SOCKET) {
                return;
            }
            const std::int64_t t = now_ms();

            // Peer timeout: drop back to handshaking; the next Hello/Welcome re-establishes.
            if (g_last_rx_ms != 0 && t - g_last_rx_ms > k_peer_timeout_ms) {
                if (g_established) {
                    log::get()->warn("CoopNet: peer timeout after {} ms, re-handshaking",
                                     t - g_last_rx_ms);
                }
                g_established = false;
                if (g_remote.valid) {
                    g_remote.valid = false;
                    g_remote_valid.store(false, std::memory_order_relaxed);
                }
                g_ack_contig = 0;
                g_recv_ids.clear();
                g_outbox.clear(); // a dead peer must not pin the outbox forever
                g_last_rx_ms = t; // wait another full timeout before re-warning
            }

            // Guest: keep asking to join until welcomed; then re-hello periodically so a
            // restarted host re-establishes without touching the guest.
            if (!g_is_host) {
                const bool due = !g_established
                                     ? (g_last_hello_ms == 0 ||
                                        t - g_last_hello_ms >= k_hello_interval_ms)
                                     : (t - g_last_hello_ms >= k_hello_resync_ms);
                if (due) {
                    send_hello_locked();
                }
            }

            // Retransmit unacked events.
            for (auto it = g_outbox.begin(); it != g_outbox.end();) {
                OutboxEntry &e = *it;
                if (t - e.last_send_ms >= k_event_resend_ms) {
                    if (e.sends >= k_event_max_sends) {
                        log::get()->warn("CoopNet: event {} (kind {}) unacked after {} sends, giving up",
                                         e.id, e.kind, e.sends);
                        it = g_outbox.erase(it);
                        continue;
                    }
                    send_event_locked(e);
                    e.last_send_ms = t;
                    ++e.sends;
                }
                ++it;
            }
        }
    } // namespace

    void shutdown() {
        std::lock_guard lock(g_mtx);
        close_locked();
        g_retry_pending = false;
        g_remote_valid.store(false, std::memory_order_relaxed);
    }

    void configure(const NetConfig &cfg) {
        std::lock_guard lock(g_mtx);
        configure_locked(cfg);
    }

    namespace {
        void configure_locked(const NetConfig &cfg) {

        // Same endpoint: keep the live socket. A quick close()->bind() on the same UDP port
        // intermittently fails on this machine with WSAEADDRINUSE (10048).
        if (g_enabled && g_sock != INVALID_SOCKET && cfg.enabled &&
            cfg.local_port == g_local_port && cfg.remote_port == g_remote_port &&
            cfg.remote_host == g_remote_host) {
            g_client_id     = cfg.client_id;
            g_send_hz       = cfg.send_hz > 0.0F ? cfg.send_hz : 20.0F;
            g_send_interval = static_cast<std::int64_t>(static_cast<double>(g_qpc_freq) / g_send_hz);
            g_is_host       = cfg.is_host;
            g_player_name   = cfg.player_name.empty() ? std::string("player") : cfg.player_name;
            log::get()->info("CoopNet: endpoint unchanged, keeping udp/{}", cfg.local_port);
            g_retry_pending = false;
            return;
        }

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
        BOOL reuse                = TRUE;
        setsockopt(s, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char *>(&reuse),
                   sizeof(reuse));
        if (bind(s, reinterpret_cast<sockaddr *>(&bind_addr), sizeof(bind_addr)) == SOCKET_ERROR) {
            log::get()->warn("CoopNet: bind udp/{} failed: {} (retrying in 2 s)",
                             cfg.local_port, WSAGetLastError());
            closesocket(s);
            g_retry_cfg     = cfg;
            g_retry_pending = true;
            g_retry_at_ms   = now_ms() + 2000;
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
        g_local_port    = cfg.local_port;
        g_remote_port   = cfg.remote_port;
        g_remote_host   = cfg.remote_host;

        // C1: role + identity.
        g_is_host     = cfg.is_host;
        g_player_name = cfg.player_name.empty() ? std::string("player") : cfg.player_name;
        if (g_is_host) {
            LARGE_INTEGER c {};
            QueryPerformanceCounter(&c);
            g_session_id = (static_cast<std::uint32_t>(c.QuadPart) ^
                            static_cast<std::uint32_t>(GetTickCount64()) ^
                            (static_cast<std::uint32_t>(std::rand()) << 16)) |
                           1U;
        }

        g_retry_pending = false;
        log::get()->info("CoopNet: udp/{} -> {}:{} as {} '{}' ({}), {:.0f} Hz",
                         cfg.local_port,
                         cfg.remote_host,
                         cfg.remote_port,
                         g_is_host ? "host" : "guest",
                         g_player_name,
                         g_client_id,
                         g_send_hz);
        }
    } // namespace

    void publish(float px, float py, float pz,
                 float qx, float qy, float qz, float qw,
                 std::uint32_t anim_state) {
        std::lock_guard lock(g_mtx);
        maybe_retry_bind_locked();
        if (!g_enabled || g_sock == INVALID_SOCKET) {
            return;
        }
        housekeeping_locked();

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
        msg.p.ack_seq    = g_ack_contig; // cum-ack for the peer's event stream

        sendto(g_sock,
               reinterpret_cast<const char *>(&msg),
               sizeof(msg),
               0,
               reinterpret_cast<sockaddr *>(&g_dst),
               sizeof(g_dst));
    }

    void poll() {
        std::lock_guard lock(g_mtx);
        maybe_retry_bind_locked();
        if (!g_enabled || g_sock == INVALID_SOCKET) {
            return;
        }
        const std::int64_t t = now_ms();

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
            if (env.client_id == g_client_id) {
                continue; // ignore our own loopback traffic
            }
            g_last_rx_ms = t;

            // --- C1 handshake ---
            if (env.type == static_cast<std::uint16_t>(MsgType::Hello) &&
                n >= static_cast<int>(sizeof(Envelope) + sizeof(HelloPayload))) {
                if (!g_is_host) {
                    if (!g_warned_role) {
                        log::get()->warn("CoopNet: received Hello but this instance is not the host "
                                         "(set IsHost=true on exactly one machine)");
                        g_warned_role = true;
                    }
                    continue;
                }
                HelloPayload h {};
                std::memcpy(&h, buf + sizeof(Envelope), sizeof(h));
                g_peer_id   = env.client_id;
                g_peer_name = std::string(h.name, bounded_len(h.name, sizeof(h.name)));
                if (!g_established) {
                    log::get()->info("CoopNet: session established (host), peer '{}' #{}",
                                     g_peer_name, g_peer_id);
                }
                g_established = true;
                g_last_rx_ms  = t;
                if (t - g_last_welcome_ms >= k_welcome_interval_ms) {
                    send_welcome_locked();
                }
                continue;
            }
            if (env.type == static_cast<std::uint16_t>(MsgType::Welcome) &&
                n >= static_cast<int>(sizeof(Envelope) + sizeof(WelcomePayload))) {
                if (g_is_host) {
                    if (!g_warned_role) {
                        log::get()->warn("CoopNet: received Welcome but this instance is the host "
                                         "(set IsHost=false on the joining machine)");
                        g_warned_role = true;
                    }
                    continue;
                }
                WelcomePayload w {};
                std::memcpy(&w, buf + sizeof(Envelope), sizeof(w));
                g_session_id = w.session_id;
                g_peer_id    = w.host_id;
                g_peer_name  = std::string(w.host_name, bounded_len(w.host_name, sizeof(w.host_name)));
                if (!g_established) {
                    log::get()->info("CoopNet: session established (guest), host '{}' #{}, session 0x{:08X}",
                                     g_peer_name, g_peer_id, g_session_id);
                }
                g_established = true;
                continue;
            }

            // --- player samples ---
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
                g_remote.anim_state = p.anim_state;
                g_remote_valid.store(true, std::memory_order_relaxed);

                // Player samples carry the peer's cum-ack for our event stream.
                if (p.ack_seq > 0) {
                    for (auto it = g_outbox.begin(); it != g_outbox.end();) {
                        if (it->id <= p.ack_seq) {
                            it = g_outbox.erase(it);
                        } else {
                            ++it;
                        }
                    }
                }
                continue;
            }

            // --- events ---
            if (env.type == static_cast<std::uint16_t>(MsgType::Event) &&
                n >= static_cast<int>(sizeof(Envelope) + sizeof(EventPayload))) {
                EventPayload ep {};
                std::memcpy(&ep, buf + sizeof(Envelope), sizeof(ep));
                const std::uint16_t dlen = ep.data_len > k_event_data_max
                                               ? static_cast<std::uint16_t>(k_event_data_max)
                                               : ep.data_len;
                const bool dup = ep.event_id <= g_ack_contig ||
                                 g_recv_ids.find(ep.event_id) != g_recv_ids.end();
                if (dup) {
                    continue;
                }
                g_recv_ids.insert(ep.event_id);
                while (g_recv_ids.find(g_ack_contig + 1) != g_recv_ids.end()) {
                    ++g_ack_contig;
                }
                const std::uint32_t floor = g_ack_contig > k_recv_id_keep
                                                ? g_ack_contig - static_cast<std::uint32_t>(k_recv_id_keep)
                                                : 0;
                for (auto it = g_recv_ids.begin(); it != g_recv_ids.end();) {
                    if (*it <= floor) {
                        it = g_recv_ids.erase(it);
                    } else {
                        break;
                    }
                }
                if (g_inbox.size() >= k_inbox_max) {
                    log::get()->warn("CoopNet: inbox full ({}), dropped event {} kind {}",
                                     g_inbox.size(), ep.event_id, ep.kind);
                    continue;
                }
                CoopEvent ce {};
                ce.kind     = ep.kind;
                ce.len      = dlen;
                ce.event_id = ep.event_id;
                ce.from     = env.client_id;
                if (dlen > 0) {
                    std::memcpy(ce.data, ep.data, dlen);
                }
                g_inbox.push_back(ce);
                continue;
            }
        }

        housekeeping_locked();
    }

    auto latest_remote() -> RemotePlayer {
        std::lock_guard lock(g_mtx);
        return g_remote;
    }

    auto session() -> SessionInfo {
        std::lock_guard lock(g_mtx);
        SessionInfo s {};
        s.enabled     = g_enabled;
        s.is_host     = g_is_host;
        s.established = g_established;
        s.session_id  = g_session_id;
        s.peer_id     = g_peer_id;
        s.peer_name   = g_peer_name;
        s.self_id     = g_client_id;
        return s;
    }

    auto send_event(std::uint16_t kind, const void *data, std::uint16_t len) -> bool {
        std::lock_guard lock(g_mtx);
        if (!g_enabled || g_sock == INVALID_SOCKET) {
            return false;
        }
        if (len > k_event_data_max) {
            log::get()->warn("CoopNet: event kind {} data too large ({} > {}), truncated",
                             kind, len, k_event_data_max);
            len = static_cast<std::uint16_t>(k_event_data_max);
        }
        if (g_outbox.size() >= k_outbox_max) {
            log::get()->warn("CoopNet: outbox full ({}), dropping event kind {}", g_outbox.size(), kind);
            return false;
        }
        OutboxEntry e {};
        e.id   = g_next_event_id++;
        e.kind = kind;
        e.len  = len;
        if (data != nullptr && len > 0) {
            std::memcpy(e.data, data, len);
        }
        send_event_locked(e);
        e.last_send_ms = now_ms();
        e.sends        = 1;
        g_outbox.push_back(e);
        return true;
    }

    auto drain_events(std::vector<CoopEvent> &out) -> std::size_t {
        std::lock_guard lock(g_mtx);
        const std::size_t n = g_inbox.size();
        if (n == 0) {
            return 0;
        }
        out.insert(out.end(), g_inbox.begin(), g_inbox.end());
        g_inbox.clear();
        return n;
    }
} // namespace games::ac::blackflag::coop
