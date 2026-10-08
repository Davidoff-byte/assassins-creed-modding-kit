#include "games/ac/blackflag/coop/ghost_body.hpp"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <mutex>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/write.hpp"

namespace games::ac::blackflag::coop::ghost {
    namespace {
        // Character node class in AC4BFSP (see bf-coop/MODLOG.md 2026-10-06):
        //  +0x00 vtable 0x01E4CE90
        //  +0x10 4x4 matrix (row 0/1 = yaw basis, row 3 +0x40 = feet position)
        //  +0x66 child count (>=8 for humanoids, 1 for markers/props)
        //  +0x68 marker 0x04DD5F8C
        //  +0x7C -0.50 exactly for humanoids
        constexpr std::uintptr_t k_body_vtable  = 0x01E4CE90U;
        constexpr std::uint32_t  k_body_marker  = 0x04DD5F8CU;

        constexpr std::uintptr_t k_scan_lo = 0x30000000U; // where the class allocates
        constexpr std::uintptr_t k_scan_hi = 0x50000000U;
        constexpr std::size_t    k_scan_step = 8U << 20U; // bytes per frame

        constexpr float k_pick_min_dist = 2.5F;  // exclude the local player's own body
        constexpr float k_snap_dist     = 20.0F; // teleports are hard snaps
        constexpr float k_lerp          = 0.28F; // per-frame smoothing towards peer
        constexpr std::int64_t k_peer_timeout_ms = 2000;

        int   g_min_children = 16;   // real crowd bodies: 18-19; proxies: 8-14
        float g_max_dist     = 200.0F;
        bool  g_anim_drive   = false;
        bool  g_api_move     = false;

        // RPG-found: the character's canonical transform setter (copies the 4x4 matrix into
        // the body and runs the notify chain that updates scene/spatial/animation systems).
        // RVAs for the pinned AC4BFSP.exe build (base 0x400000).
        constexpr std::uintptr_t k_set_world_matrix_rva = 0x23C2D0;
        std::uintptr_t           g_exe_base = 0;

        // SEH-guarded thiscall: body->SetWorldMatrix(local_matrix). Pure helper.
        // The engine function ends with `ret 8` - it takes TWO stack args (the second is
        // unused in its body; omitting it corrupts the stack).
        static int set_world_matrix_helper(std::uintptr_t body, const float *matrix) {
            __try {
                using Fn = void(__thiscall *)(void *, const void *, std::uint32_t);
                reinterpret_cast<Fn>(g_exe_base + k_set_world_matrix_rva)(
                    reinterpret_cast<void *>(body), matrix, 0U);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        bool           g_enabled     = false;
        std::mutex     g_drive_mtx; // serialises the game-thread tick against config setters
        std::uintptr_t g_body        = 0;
        float          g_x = 0.0F;
        float          g_y = 0.0F;
        float          g_z = 0.0F;
        bool           g_have_pos    = false;
        std::uintptr_t g_cursor      = k_scan_lo;
        bool           g_searching   = false;
        std::uintptr_t g_best        = 0;
        float          g_best_d      = 1.0e9F;
        std::uintptr_t g_skip[8]     = {};
        int            g_skip_next   = 0;
        int            g_resist      = 0;
        int            g_body_fail   = 0; // consecutive failed validation frames
        std::uintptr_t g_fake_vt     = 0; // private vtable used to block the body's deletion
        constexpr int  k_path_len    = 90; // ~1.5 s of peer history at 60 fps
        float          g_path_x[k_path_len] = {};
        float          g_path_y[k_path_len] = {};
        float          g_path_z[k_path_len] = {};
        int            g_path_head = 0;
        int            g_path_fill = 0;
        std::uint32_t  g_peer_tick   = 0;
        std::int64_t   g_peer_seen   = 0;
        bool           g_peer_fresh  = false;
        std::int64_t   g_qpc_freq    = 0;
        int            g_log_counter = 0;
        int            g_anim_log    = 0;
        float          g_last_lx     = 0.0F;
        float          g_last_ly     = 0.0F;

        auto now_ms() -> std::int64_t {
            if (g_qpc_freq == 0) {
                LARGE_INTEGER f {};
                QueryPerformanceFrequency(&f);
                g_qpc_freq = f.QuadPart;
            }
            LARGE_INTEGER n {};
            QueryPerformanceCounter(&n);
            return (n.QuadPart * 1000) / g_qpc_freq;
        }

        auto readable(std::uintptr_t addr, std::size_t size) -> bool {
            if (addr == 0 || addr < 0x10000U) {
                return false;
            }
            MEMORY_BASIC_INFORMATION mbi {};
            if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                return false;
            }
            if (mbi.State != MEM_COMMIT) {
                return false;
            }
            constexpr DWORD ok = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                                 PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                                 PAGE_EXECUTE_WRITECOPY;
            if ((mbi.Protect & ok) == 0 || (mbi.Protect & PAGE_GUARD) != 0) {
                return false;
            }
            const auto end = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
            return addr + size <= end;
        }

        auto region_ok(const MEMORY_BASIC_INFORMATION &mbi) -> bool {
            if (mbi.State != MEM_COMMIT) {
                return false;
            }
            constexpr DWORD ok = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                                 PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                                 PAGE_EXECUTE_WRITECOPY;
            return (mbi.Protect & ok) != 0 && (mbi.Protect & PAGE_GUARD) == 0;
        }

        // Validates a candidate object. When want_dist is set, the object must also be
        // at least k_pick_min_dist from the local player (selection only; a body we are
        // already driving may of course come closer).
        auto valid_body(std::uintptr_t addr, float lx, float ly, bool want_dist, float *out_dist) -> bool {
            if (!readable(addr, 0x90)) {
                return false;
            }
            const auto vt = mem::read<std::uint32_t>(addr);
            if (vt != k_body_vtable && vt != static_cast<std::uint32_t>(g_fake_vt)) {
                return false;
            }
            if (mem::read<std::uint32_t>(addr + 0x68) != k_body_marker) {
                return false;
            }
            if (std::fabs(mem::read<float>(addr + 0x7C) + 0.5F) > 0.02F) {
                return false;
            }
            if (mem::read<std::uint16_t>(addr + 0x66) < static_cast<std::uint16_t>(g_min_children)) {
                return false;
            }
            const auto x = mem::read<float>(addr + 0x40);
            const auto y = mem::read<float>(addr + 0x44);
            const auto z = mem::read<float>(addr + 0x48);
            if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
                return false;
            }
            if (std::fabs(x) > 9000.0F || std::fabs(y) > 9000.0F || z < -200.0F || z > 300.0F) {
                return false;
            }
            const auto dx = x - lx;
            const auto dy = y - ly;
            const auto d  = std::sqrt(dx * dx + dy * dy);
            if (out_dist != nullptr) {
                *out_dist = d;
            }
            if (want_dist && d < k_pick_min_dist) {
                return false;
            }
            return true;
        }

        auto is_skipped(std::uintptr_t p) -> bool {
            for (const auto s : g_skip) {
                if (s == p) {
                    return true;
                }
            }
            return false;
        }

        void skip_body(std::uintptr_t p) {
            g_skip[g_skip_next] = p;
            g_skip_next         = (g_skip_next + 1) % 8;
        }

        // Give the ghost's body a private copy of its vtable with the deleting
        // destructor (slot 0) replaced by a harmless stub, so the engine's
        // streaming cannot destroy the body while we drive it. All other slots
        // stay identical, so every other virtual behaviour is unchanged.
        auto ensure_pin() -> void {
            if (g_fake_vt != 0) {
                return;
            }
            void *mem = VirtualAlloc(nullptr, 0x1000, MEM_COMMIT | MEM_RESERVE,
                                     PAGE_EXECUTE_READWRITE);
            if (mem == nullptr) {
                return;
            }
            const auto base = reinterpret_cast<std::uintptr_t>(mem);
            // stub: mov eax, ecx ; ret 4   (scalar deleting destructor ABI)
            const std::uint8_t stub[] = {0x8B, 0xC1, 0xC2, 0x04, 0x00};
            auto *const        dst    = reinterpret_cast<std::uint8_t *>(base + 0x400);
            for (std::size_t k = 0; k < sizeof(stub); k++) {
                dst[k] = stub[k];
            }
            auto *vt = reinterpret_cast<std::uint32_t *>(base);
            // The class may use slots beyond the exported six, and the real table
            // sits in dense .rdata - copy a wide span so every call lands on the
            // same target the original table would have provided.
            constexpr std::uintptr_t k_copy_slots = 64;
            for (std::uintptr_t i = 1; i < k_copy_slots; i++) {
                vt[i] = mem::read<std::uint32_t>(k_body_vtable + i * 4);
            }
            vt[0]     = static_cast<std::uint32_t>(base + 0x400);
            g_fake_vt = base;
            // The table and stub never change after setup: drop write access.
            DWORD old_protect = 0;
            VirtualProtect(mem, 0x1000, PAGE_EXECUTE_READ, &old_protect);
            log::get()->info("GhostBody: despawn pin armed (private vt at 0x{:X})", g_fake_vt);
        }

        // Restore the normal vtable so a released body can be cleaned up normally.
        auto unpin_body() -> void {
            if (g_body == 0 || g_fake_vt == 0 || !readable(g_body, 4)) {
                return;
            }
            if (mem::read<std::uint32_t>(g_body) == static_cast<std::uint32_t>(g_fake_vt)) {
                mem::write<std::uint32_t>(g_body, k_body_vtable);
                log::get()->info("GhostBody: despawn pin released for 0x{:X}", g_body);
            }
        }

        // Incremental scan for the humanoid body nearest to the peer position
        // (tx,ty); (lx,ly) is the local player, whose own body is always excluded.
        // The sweep runs to the end of the range and only then returns the
        // globally nearest candidate, so a pick is never a far-away first hit.
        auto scan_step(float tx, float ty, float lx, float ly, float *out_dist) -> std::uintptr_t {
            if (!g_searching) {
                g_searching = true;
                g_cursor    = k_scan_lo;
                g_best      = 0;
                g_best_d    = 1.0e9F;
            }
            std::size_t budget = k_scan_step;

            LARGE_INTEGER t0 {};
            QueryPerformanceCounter(&t0);
            constexpr std::int64_t k_scan_time_numer = 1; // 2 ms of game time max per tick
            constexpr std::int64_t k_scan_time_denom = 500;

            while (budget > 0 && g_cursor < k_scan_hi) {
                if (g_qpc_freq > 0) {
                    LARGE_INTEGER tn {};
                    QueryPerformanceCounter(&tn);
                    if ((tn.QuadPart - t0.QuadPart) * k_scan_time_denom >
                        g_qpc_freq * k_scan_time_numer) {
                        break; // hand the frame back to the game
                    }
                }
                MEMORY_BASIC_INFORMATION mbi {};
                if (VirtualQuery(reinterpret_cast<LPCVOID>(g_cursor), &mbi, sizeof(mbi)) == 0) {
                    g_cursor += 0x1000;
                    continue;
                }
                const auto base = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                const auto end  = base + mbi.RegionSize;
                if (!region_ok(mbi)) {
                    g_cursor = end;
                    continue;
                }
                auto p    = g_cursor > base ? g_cursor : base;
                auto stop = end;
                if (stop > p + budget) {
                    stop = p + budget;
                }
                for (; p + 4 <= stop; p += 4) {
                    if (mem::read<std::uint32_t>(p) == k_body_vtable) {
                        if (is_skipped(p)) {
                            continue;
                        }
                        float local_dist = 0.0F;
                        if (!valid_body(p, lx, ly, true, &local_dist)) {
                            continue;
                        }
                        const auto bx = mem::read<float>(p + 0x40);
                        const auto by = mem::read<float>(p + 0x44);
                        const auto ddx = bx - tx;
                        const auto ddy = by - ty;
                        const auto d   = std::sqrt(ddx * ddx + ddy * ddy);
                        if (d > g_max_dist) {
                            continue;
                        }
                        if (d < g_best_d) {
                            g_best   = p;
                            g_best_d = d;
                        }
                    }
                }
                budget -= stop - (g_cursor > base ? g_cursor : base);
                g_cursor = stop;
            }

            if (g_cursor >= k_scan_hi) { // full sweep complete
                g_searching = false;
                const auto b = g_best;
                if (b != 0) {
                    *out_dist = g_best_d;
                }
                g_best = 0;
                return b;
            }
            return 0; // sweep still in progress
        }
    } // namespace

    void set_params(int min_children, float max_dist) {
        std::lock_guard lock(g_drive_mtx);
        if (min_children > 0) {
            g_min_children = min_children;
        }
        if (max_dist > 1.0F) {
            g_max_dist = max_dist;
        }
        log::get()->info("GhostBody: params minChildren={} maxDist={:.0f}", g_min_children, g_max_dist);
    }

    void set_enabled(bool on) {
        std::lock_guard lock(g_drive_mtx);
        if (g_enabled != on) {
            log::get()->info("GhostBody: {}", on ? "enabled" : "disabled");
        }
        g_enabled = on;
        if (!on) {
            unpin_body();
            g_body      = 0;
            g_have_pos  = false;
            g_searching = false;
        }
    }

    void set_anim_drive(bool on) {
        std::lock_guard lock(g_drive_mtx);
        if (g_anim_drive != on) {
            log::get()->info("GhostBody: anim drive {}", on ? "on" : "off");
        }
        g_anim_drive = on;
    }

    void set_api_move(bool on) {
        std::lock_guard lock(g_drive_mtx);
        if (g_api_move != on) {
            log::get()->info("GhostBody: api move {}", on ? "on" : "off");
        }
        g_api_move = on;
    }

    void tick(float lx, float ly, float lz, const RemotePlayer &remote) {
        std::lock_guard lock(g_drive_mtx);
        if (!g_enabled) {
            return;
        }
        g_last_lx = lx;
        g_last_ly = ly;

        // Peer freshness: consider it live only while packets keep arriving.
        if (remote.valid) {
            if (remote.tick_ms != g_peer_tick) {
                g_peer_tick = remote.tick_ms;
                g_peer_seen = now_ms();
            }
            g_peer_fresh = (now_ms() - g_peer_seen) < k_peer_timeout_ms;
        } else {
            g_peer_fresh = false;
        }
        if (!g_peer_fresh || !remote.valid) {
            return;
        }
        if (std::fabs(remote.px) + std::fabs(remote.py) < 1.0F) {
            return; // peer is not in-world yet
        }
        if (!std::isfinite(remote.px) || !std::isfinite(remote.py) || !std::isfinite(remote.pz) ||
            !std::isfinite(remote.qx) || !std::isfinite(remote.qy) || !std::isfinite(remote.qz) ||
            !std::isfinite(remote.qw)) {
            return; // drop malformed samples before they can reach the engine setter
        }

        // Body selection / validation.
        if (g_body != 0 && !valid_body(g_body, lx, ly, false, nullptr)) {
            if (++g_body_fail < 20) {
                return; // hold through one-frame glitches and streaming hiccups
            }
            const auto vt  = readable(g_body, 4) ? mem::read<std::uint32_t>(g_body) : 0U;
            const auto ch  = readable(g_body + 0x66, 2) ? mem::read<std::uint16_t>(g_body + 0x66) : 0;
            const auto f7c = readable(g_body + 0x7C, 4) ? mem::read<float>(g_body + 0x7C) : 0.0F;
            const auto bx  = readable(g_body + 0x40, 8) ? mem::read<float>(g_body + 0x40) : 0.0F;
            const auto by  = readable(g_body + 0x44, 4) ? mem::read<float>(g_body + 0x44) : 0.0F;
            const auto bz  = readable(g_body + 0x48, 4) ? mem::read<float>(g_body + 0x48) : 0.0F;
            log::get()->info(
                "GhostBody: body 0x{:X} lost (vt=0x{:X} ch={} f7c={:.2f} pos=({:.0f},{:.0f},{:.0f})), rescanning",
                g_body, vt, ch, f7c, bx, by, bz);
            g_body_fail = 0;
            g_resist    = 0;
            g_body      = 0;
            g_have_pos  = false;
            g_searching = false;
        } else if (g_body != 0) {
            g_body_fail = 0;
        }
        if (g_body == 0) {
            float d      = 0.0F;
            const auto b = scan_step(remote.px, remote.py, lx, ly, &d);
            if (b == 0) {
                return; // still searching
            }
            g_body     = b;
            g_have_pos = false;
            log::get()->info("GhostBody: picked body 0x{:X} at {:.1f} m from peer", g_body, d);
            ensure_pin();
            if (g_fake_vt != 0 && readable(g_body, 4)) {
                mem::write<std::uint32_t>(g_body, static_cast<std::uint32_t>(g_fake_vt));
            }
        }

        // Path replay: record the peer's recent path and drive the ghost along the
        // same route with a short delay, so climbs and corners are traced instead
        // of cut through as a straight line.
        g_path_x[g_path_head] = remote.px;
        g_path_y[g_path_head] = remote.py;
        g_path_z[g_path_head] = remote.pz;
        g_path_head           = (g_path_head + 1) % k_path_len;
        if (g_path_fill < k_path_len) {
            g_path_fill++;
        }
        float tx = remote.px;
        float ty = remote.py;
        float tz = remote.pz;
        if (g_path_fill >= k_path_len) {
            tx = g_path_x[g_path_head];
            ty = g_path_y[g_path_head];
            tz = g_path_z[g_path_head];
        }

        // Smooth towards the (delayed) peer position.
        if (!g_have_pos) {
            g_x        = tx;
            g_y        = ty;
            g_z        = tz;
            g_have_pos = true;
        } else {
            const auto dx = tx - g_x;
            const auto dy = ty - g_y;
            const auto dz = tz - g_z;
            if (dx * dx + dy * dy + dz * dz > k_snap_dist * k_snap_dist) {
                g_x = remote.px;
                g_y = remote.py;
                g_z = remote.pz;
                // Fast-forward the replay buffer to the new location so the delayed
                // path can never drag the ghost back towards the old one.
                for (int i = 0; i < k_path_len; i++) {
                    g_path_x[i] = remote.px;
                    g_path_y[i] = remote.py;
                    g_path_z[i] = remote.pz;
                }
                g_path_head = 0;
                g_path_fill = k_path_len;
            } else {
                g_x += dx * k_lerp;
                g_y += dy * k_lerp;
                g_z += dz * k_lerp;
            }
        }

        // Write the transform.
        // Yaw from the peer's quaternion (rotation about Z).
        const auto qx = remote.qx;
        const auto qy = remote.qy;
        const auto qz = remote.qz;
        const auto qw = remote.qw;
        const auto yaw = std::atan2(2.0F * (qw * qz + qx * qy), 1.0F - 2.0F * (qy * qy + qz * qz));
        const auto c   = std::cos(yaw);
        const auto s   = std::sin(yaw);

        if (g_api_move) {
            // Route through the engine's own transform setter (notify chain: scene/spatial/
            // animation systems learn about the move -> no stale "distant" state).
            if (g_exe_base == 0) {
                g_exe_base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
            }
            if (!readable(g_body + 0x10, 0x40)) {
                return; // body vanished mid-tick; next tick rescans
            }
            // The engine setter uses movaps on the matrix: the buffer MUST be 16-byte aligned.
            alignas(16) float m[16];
            std::memcpy(m, reinterpret_cast<const void *>(g_body + 0x10), sizeof(m));
            m[0]  = c;
            m[1]  = s;
            m[2]  = 0.0F;
            m[3]  = 0.0F;
            m[4]  = -s;
            m[5]  = c;
            m[6]  = 0.0F;
            m[7]  = 0.0F;
            m[12] = g_x;
            m[13] = g_y;
            m[14] = g_z;
            m[15] = 1.0F;
            static bool logged_fail = false;
            const int   rc          = set_world_matrix_helper(g_body, m);
            if (rc != 0 && !logged_fail) {
                logged_fail = true;
                log::get()->warn("GhostBody: SetWorldMatrix failed rc=0x{:X}", rc);
            }
        } else {
            // Raw matrix writes (legacy path).
            auto *const pos = reinterpret_cast<float *>(g_body + 0x40);
            pos[0]          = g_x;
            pos[1]          = g_y;
            pos[2]          = g_z;
            auto *const r0 = reinterpret_cast<float *>(g_body + 0x10);
            auto *const r1 = reinterpret_cast<float *>(g_body + 0x20);
            r0[0] = c;
            r0[1] = s;
            r0[2] = 0.0F;
            r0[3] = 0.0F;
            r1[0] = -s;
            r1[1] = c;
            r1[2] = 0.0F;
            r1[3] = 0.0F;
        }

        // If the body's own logic (post anchoring, schedule warps) keeps snapping
        // it away from where we parked it, the ghost will visibly bounce. Count
        // those frames and, after ~1.5 s of resistance, drop the body for another.
        {
            if (readable(g_body + 0x40, 8)) {
                const auto bx = mem::read<float>(g_body + 0x40);
                const auto by = mem::read<float>(g_body + 0x44);
                const auto rx = bx - g_x;
                const auto ry = by - g_y;
                if (rx * rx + ry * ry > 49.0F) { // more than 7 m from our target
                    if (++g_resist > 90) {
                        log::get()->info("GhostBody: body 0x{:X} keeps snapping away, dropping", g_body);
                        unpin_body();
                        skip_body(g_body);
                        g_body      = 0;
                        g_have_pos  = false;
                        g_searching = false;
                        g_resist    = 0;
                        return;
                    }
                } else {
                    g_resist = 0;
                }
            }
        }

        // P3: replay the peer's packed action state onto the body's controller.
        // Layout matches the B4 read side (player ctl = node+0xE8; same class here):
        //   +0x8E0 phase (u8) · +0x8D8 hang (u8) · flags bit0 of +0x138 / bit1 of +0x8D0.
        // The NPC's own AI may fight these writes; the live test decides.
        if (g_anim_drive && remote.anim_state != 0) {
            const auto ctl = mem::read<std::uintptr_t>(g_body + 0xE8);
            if (ctl >= 0x10000 && readable(ctl + 0x8E4, 4) && readable(ctl + 0x138, 4)) {
                const auto phase = static_cast<std::uint8_t>((remote.anim_state >> 16) & 0xFFU);
                const auto hang  = static_cast<std::uint8_t>(remote.anim_state & 0xFFU);
                const auto fl    = static_cast<std::uint32_t>((remote.anim_state >> 8) & 0x3U);
                mem::write<std::uint8_t>(ctl + 0x8D8, hang);
                mem::write<std::uint8_t>(ctl + 0x8E0, phase);
                auto f138 = mem::read<std::uint32_t>(ctl + 0x138);
                f138      = (f138 & ~1U) | (fl & 1U);
                mem::write<std::uint32_t>(ctl + 0x138, f138);
                auto f8d0 = mem::read<std::uint32_t>(ctl + 0x8D0);
                f8d0      = (f8d0 & ~1U) | ((fl >> 1) & 1U);
                mem::write<std::uint32_t>(ctl + 0x8D0, f8d0);
                if (++g_anim_log >= 600) { // ~10 s
                    g_anim_log = 0;
                    log::get()->info("GhostBody: anim drive ctl=0x{:X} phase={} hang={} fl={}",
                                     ctl, phase, hang, fl);
                }
            }
        }

        // Occasional diagnostics; drop the body if it gets streamed away.
        if (++g_log_counter >= 300) { // ~5 s at 60 fps
            g_log_counter = 0;
            const auto bx  = mem::read<float>(g_body + 0x40);
            const auto by  = mem::read<float>(g_body + 0x44);
            const auto ddx = bx - remote.px;
            const auto ddy = by - remote.py;
            const auto errd = std::sqrt(ddx * ddx + ddy * ddy);
            log::get()->info("GhostBody: body 0x{:X} set=({:.1f},{:.1f},{:.1f}) peer=({:.1f},{:.1f},{:.1f}) err={:.2f} m",
                             g_body, g_x, g_y, g_z, remote.px, remote.py, remote.pz, errd);
            if (errd > 400.0F) {
                log::get()->info("GhostBody: body 0x{:X} streamed away (err={:.0f}), rescanning", g_body, errd);
                g_body      = 0;
                g_have_pos  = false;
                g_searching = false;
            }
        }
    }

    auto status() -> Status {
        Status s;
        s.enabled    = g_enabled;
        s.have_body  = g_body != 0;
        s.body       = g_body;
        s.peer_fresh = g_peer_fresh;
        if (s.have_body) {
            const auto dx = g_x - g_last_lx;
            const auto dy = g_y - g_last_ly;
            s.dist        = std::sqrt(dx * dx + dy * dy);
        }
        return s;
    }
} // namespace games::ac::blackflag::coop::ghost
