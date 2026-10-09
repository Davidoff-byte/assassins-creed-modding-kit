// BFCoop combat sync implementation (P4).
//
// TX (detection): poll live CSrvNPCHealth instances (vtable 0x02712F60).
//   LIFE u16 @ +0x5C, MAX u16 @ +0x5E, flags u32 @ +0x60 (bit 0x01000000 = dead).
//   Any LIFE decrease = damage event; LIFE -> 0xFFFF + flag = death; vtable change = recycle.
//   NPC position: obj+0x20/+0x28 hold the services-container pointer P; a body sweep
//   (body vt 0x01E4CE90, feet at +0x40) caches pointer -> body position for matching.
//
// RX (application): match by position (<= 3 m) + max HP, then raw writes (SEH-guarded):
//   damage -> LIFE := LIFE - dmg (kill if it would drop to <= 0);
//   kill   -> LIFE := 0xFFFF + flags |= 0x01000000  (verified: a watched guard drops dead).
//
// Echo guards: (a) local applies are noted in a small recent-write ring so the watcher
// does not re-relay them; (b) an incoming event is skipped when the local object already
// shows the effect (life <= life_after / already dead).
//
// Offline single-player co-op only; all writes go to the same fields the game itself uses.
#include "games/ac/blackflag/coop/combat_sync.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <unordered_map>
#include <vector>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep
#include "core/mem/write.hpp"

#include "games/ac/blackflag/coop/coop_proto.hpp"

namespace games::ac::blackflag::coop::combat {
    namespace {
        constexpr std::uint32_t k_health_vt  = 0x02712F60; // CSrvNPCHealth first-interface vtable
        constexpr std::uint32_t k_body_vt    = 0x01E4CE90; // crowd/character body vtable
        constexpr std::uintptr_t k_life_off  = 0x5C;
        constexpr std::uintptr_t k_max_off   = 0x5E;
        constexpr std::uintptr_t k_flags_off = 0x60;
        constexpr std::uint32_t k_dead_flag  = 0x01000000U;

        constexpr std::uintptr_t k_scan_lo = 0x2E000000; // health-service heap window
        constexpr std::uintptr_t k_scan_hi = 0x56000000;
        constexpr std::uintptr_t k_slice   = 0x800000;   // 8 MB scanned per tick
        constexpr int            k_max_tracked = 256;

        constexpr std::uintptr_t k_body_lo    = 0x30000000; // body heap window
        constexpr std::uintptr_t k_body_hi    = 0x50000000;
        constexpr std::uintptr_t k_body_slice = 0x800000;

        constexpr float k_match_radius = 3.0F;

        std::atomic<bool> g_enabled {false};
        std::atomic<bool> g_kill_test {false};
        std::uintptr_t    g_cursor      = k_scan_lo;
        std::uintptr_t    g_body_cursor = k_body_lo;
        std::int64_t      g_qpc_freq    = 0;
        std::int64_t      g_last_tick   = 0;
        int               g_events      = 0;
        bool              g_kill_done   = false;

        std::vector<std::uintptr_t> g_objs;
        std::vector<std::uint16_t>  g_life;

        // Pointer -> body position cache (filled by the body sweep).
        std::unordered_map<std::uintptr_t, std::array<float, 3>> g_ptr_pos;

        // Recent local applies (echo guard): object + value + timestamp.
        struct Applied {
            std::uintptr_t obj;
            std::uint16_t  value;
            std::int64_t   qpc;
        };
        std::vector<Applied> g_applied;

#pragma pack(push, 1)
        struct NpcCombatPayload {
            float         px;
            float         py;
            float         pz;
            std::uint16_t life_before;
            std::uint16_t life_after;
            std::uint16_t max_hp;
            std::uint8_t  ev; // 0 = damage, 1 = kill
            std::uint8_t  pad;
        };
#pragma pack(pop)
        static_assert(sizeof(NpcCombatPayload) == 20);

        template<typename T>
        auto safe_read(std::uintptr_t addr) -> T {
            __try {
                return *reinterpret_cast<const T *>(addr);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return T {};
            }
        }

        template<typename T>
        auto safe_write(std::uintptr_t addr, T value) -> bool {
            __try {
                return mem::write<T>(addr, value);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return false;
            }
        }

        auto note_applied(std::uintptr_t obj, std::uint16_t value) -> void {
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            if (g_applied.size() > 32) {
                g_applied.erase(g_applied.begin());
            }
            g_applied.push_back({obj, value, now.QuadPart});
        }

        auto was_applied(std::uintptr_t obj, std::uint16_t value) -> bool {
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            for (const auto &a : g_applied) {
                if (a.obj == obj && a.value == value && (now.QuadPart - a.qpc) < g_qpc_freq * 3) {
                    return true;
                }
            }
            return false;
        }

        // --- RX primitives (proven writes) ---------------------------------------------
        auto apply_kill(std::uintptr_t obj) -> bool {
            const auto flags = safe_read<std::uint32_t>(obj + k_flags_off);
            const auto ok1   = safe_write<std::uint16_t>(obj + k_life_off, static_cast<std::uint16_t>(0xFFFF));
            const auto ok2   = safe_write<std::uint32_t>(obj + k_flags_off, flags | k_dead_flag);
            return ok1 && ok2;
        }

        auto apply_damage(std::uintptr_t obj, int dmg) -> bool {
            const auto life = safe_read<std::uint16_t>(obj + k_life_off);
            if (life == 0xFFFF || dmg <= 0) {
                return false;
            }
            const auto next = static_cast<int>(life) - dmg;
            if (next <= 0) {
                return apply_kill(obj);
            }
            return safe_write<std::uint16_t>(obj + k_life_off, static_cast<std::uint16_t>(next));
        }

        // --- position resolution (obj -> body position via the pointer cache) ----------
        auto resolve_pos(std::uintptr_t obj, float *out) -> bool {
            const std::uint32_t cand[2] = {safe_read<std::uint32_t>(obj + 0x20),
                                           safe_read<std::uint32_t>(obj + 0x28)};
            for (const auto p : cand) {
                if (p < 0x10000000U) {
                    continue;
                }
                const auto it = g_ptr_pos.find(p);
                if (it != g_ptr_pos.end()) {
                    out[0] = it->second[0];
                    out[1] = it->second[1];
                    out[2] = it->second[2];
                    return true;
                }
            }
            return false;
        }

        // --- incremental scans ---------------------------------------------------------
        auto scan_slice() -> void {
            static std::uint8_t buf[0x10004];
            const auto end = (g_cursor + k_slice < k_scan_hi) ? (g_cursor + k_slice) : k_scan_hi;
            std::uintptr_t p = g_cursor;
            MEMORY_BASIC_INFORMATION mbi {};
            while (p < end) {
                if (VirtualQuery(reinterpret_cast<LPCVOID>(p), &mbi, sizeof(mbi)) == 0) {
                    p += 0x1000;
                    continue;
                }
                auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                auto sz = static_cast<std::uintptr_t>(mbi.RegionSize);
                if (ba < p) {
                    sz -= (p - ba);
                    ba = p;
                }
                if (sz == 0) {
                    p += 0x1000;
                    continue;
                }
                if (mbi.State != MEM_COMMIT) {
                    p = ba + sz;
                    continue;
                }
                const auto stop = (ba + sz < end) ? (ba + sz) : end;
                for (std::uintptr_t c = ba; c < stop; c += 0x10000) {
                    const auto want = static_cast<SIZE_T>(std::min<std::uintptr_t>(0x10004, stop - c));
                    SIZE_T got = 0;
                    if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(c), buf, want, &got) ||
                        got < 4) {
                        continue;
                    }
                    for (SIZE_T i = 0; i + 4 <= got; i += 4) {
                        std::uint32_t v = 0;
                        std::memcpy(&v, buf + i, 4);
                        if (v != k_health_vt) {
                            continue;
                        }
                        if (g_objs.size() >= k_max_tracked) {
                            g_cursor = end;
                            return;
                        }
                        const auto obj  = c + i;
                        const auto life = safe_read<std::uint16_t>(obj + k_life_off);
                        const auto maxl = safe_read<std::uint16_t>(obj + k_max_off);
                        if (maxl < 1 || maxl > 2000 || life > maxl) {
                            continue; // look-alike data, not a service object
                        }
                        bool dup = false;
                        for (const auto o : g_objs) {
                            if (o == obj) {
                                dup = true;
                                break;
                            }
                        }
                        if (!dup) {
                            g_objs.push_back(obj);
                            g_life.push_back(life);
                            log::get()->info("CombatSync: track 0x{:X} life={} max={}", obj, life, maxl);
                        }
                    }
                }
                p = ba + sz;
            }
            g_cursor = end;
            if (g_cursor >= k_scan_hi) {
                g_cursor = k_scan_lo;
            }
        }

        auto body_sweep_slice() -> void {
            static std::uint8_t buf[0x10000 + 4];
            static std::uint8_t body_buf[0x200];
            const auto end =
                (g_body_cursor + k_body_slice < k_body_hi) ? (g_body_cursor + k_body_slice) : k_body_hi;
            std::uintptr_t p = g_body_cursor;
            MEMORY_BASIC_INFORMATION mbi {};
            while (p < end) {
                if (VirtualQuery(reinterpret_cast<LPCVOID>(p), &mbi, sizeof(mbi)) == 0) {
                    p += 0x1000;
                    continue;
                }
                auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                auto sz = static_cast<std::uintptr_t>(mbi.RegionSize);
                if (ba < p) {
                    sz -= (p - ba);
                    ba = p;
                }
                if (sz == 0) {
                    p += 0x1000;
                    continue;
                }
                if (mbi.State != MEM_COMMIT) {
                    p = ba + sz;
                    continue;
                }
                const auto stop = (ba + sz < end) ? (ba + sz) : end;
                for (std::uintptr_t c = ba; c < stop; c += 0x10000) {
                    const auto want = static_cast<SIZE_T>(std::min<std::uintptr_t>(0x10004, stop - c));
                    SIZE_T got = 0;
                    if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(c), buf, want, &got) ||
                        got < 4) {
                        continue;
                    }
                    for (SIZE_T i = 0; i + 4 <= got; i += 4) {
                        std::uint32_t v = 0;
                        std::memcpy(&v, buf + i, 4);
                        if (v != k_body_vt) {
                            continue;
                        }
                        const auto body = c + i;
                        if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(body),
                                               body_buf, sizeof(body_buf), &got) ||
                            got < 0x180) {
                            continue;
                        }
                        std::array<float, 3> pos {};
                        std::memcpy(&pos[0], body_buf + 0x40, 4);
                        std::memcpy(&pos[1], body_buf + 0x44, 4);
                        std::memcpy(&pos[2], body_buf + 0x48, 4);
                        if (!std::isfinite(pos[0]) || !std::isfinite(pos[1]) || !std::isfinite(pos[2])) {
                            continue;
                        }
                        // remember every heap-pointer-looking u32 in the body header (no validation
                        // reads here - reading arbitrary candidates fault-stormed the VEH handler)
                        for (std::size_t o = 0; o + 4 <= 0x1C0; o += 4) {
                            std::uint32_t q = 0;
                            std::memcpy(&q, body_buf + o, 4);
                            if (q < 0x10000000U || q >= 0x7FFF0000U) {
                                continue;
                            }
                            g_ptr_pos[q] = pos;
                        }
                    }
                }
                p = ba + sz;
            }
            g_body_cursor = end;
            if (g_body_cursor >= k_body_hi) {
                g_body_cursor = k_body_lo;
            }
        }
    } // namespace

    void set_enabled(bool on) {
        g_enabled.store(on, std::memory_order_relaxed);
        if (on && g_qpc_freq == 0) {
            LARGE_INTEGER f {};
            QueryPerformanceFrequency(&f);
            g_qpc_freq = f.QuadPart;
            log::get()->info("CombatSync: enabled (relay ready)");
        }
    }

    void set_kill_test(bool on) {
        g_kill_test.store(on, std::memory_order_relaxed);
    }

    void tick(bool in_world) {
        if (!g_enabled.load(std::memory_order_relaxed)) {
            return;
        }
        LARGE_INTEGER now {};
        QueryPerformanceCounter(&now);
        if (g_qpc_freq <= 0 || (g_last_tick != 0 && now.QuadPart - g_last_tick < g_qpc_freq / 5)) {
            return; // 5 Hz
        }
        g_last_tick = now.QuadPart;

        // Heavy scans run only once the player is actually in the world - nothing at
        // menus/loading screens (keeps load-time activity at zero).
        if (in_world) {
            scan_slice();
            body_sweep_slice();
        }

        for (std::size_t i = 0; i < g_objs.size();) {
            const auto obj = g_objs[i];
            if (safe_read<std::uint32_t>(obj) != k_health_vt) {
                log::get()->info("CombatSync: recycle 0x{:X}", obj);
                g_objs[i] = g_objs.back();
                g_objs.pop_back();
                g_life[i] = g_life.back();
                g_life.pop_back();
                continue;
            }
            const auto life  = safe_read<std::uint16_t>(obj + k_life_off);
            const auto maxl  = safe_read<std::uint16_t>(obj + k_max_off);
            const auto flags = safe_read<std::uint32_t>(obj + k_flags_off);
            const auto prev  = g_life[i];
            if (life != prev) {
                g_events++;
                const bool dead = (life == 0xFFFF) && ((flags & k_dead_flag) != 0);
                float      pos[3];
                const bool have_pos = resolve_pos(obj, pos);
                if (dead) {
                    log::get()->info("CombatSync: DEATH 0x{:X} life {}->65535 flags=0x{:X}", obj, prev,
                                     flags);
                } else if (life < prev) {
                    log::get()->info("CombatSync: DAMAGE 0x{:X} life {}->{} dmg={} flags=0x{:X}", obj,
                                     prev, life, prev - life, flags);
                } else {
                    log::get()->info("CombatSync: LIFEUP 0x{:X} life {}->{} flags=0x{:X}", obj, prev,
                                     life, flags);
                }
                // ----- TX: relay genuine local changes (skip our own RX applies) -----
                const bool interesting = dead || (life < prev);
                if (interesting && have_pos && !was_applied(obj, life)) {
                    NpcCombatPayload pl {};
                    pl.px = pos[0];
                    pl.py = pos[1];
                    pl.pz = pos[2];
                    pl.life_before = prev;
                    pl.life_after  = life;
                    pl.max_hp      = maxl;
                    pl.ev          = dead ? 1 : 0;
                    if (send_event(static_cast<std::uint16_t>(EventKind::NpcCombat), &pl, sizeof(pl))) {
                        log::get()->info("CombatSync: TX {} npc@({:.1f},{:.1f},{:.1f}) {}->{}",
                                         dead ? "kill" : "damage", pos[0], pos[1], pos[2], prev, life);
                    }
                } else if (interesting && !have_pos) {
                    log::get()->info("CombatSync: TX skipped (no position for 0x{:X})", obj);
                }
                g_life[i] = life;
            }
            ++i;
        }

        if (g_kill_test.load(std::memory_order_relaxed) && !g_kill_done && !g_objs.empty()) {
            g_kill_done = true;
            const auto obj = g_objs[0];
            const auto ok  = apply_kill(obj);
            if (ok) {
                note_applied(obj, 0xFFFF);
            }
            log::get()->info("CombatSync: KILL TEST obj=0x{:X} write-kill ok={}", obj, ok);
        }
    }

    void on_event(const CoopEvent &ev) {
        if (!g_enabled.load(std::memory_order_relaxed)) {
            return;
        }
        if (ev.kind != static_cast<std::uint16_t>(EventKind::NpcCombat) ||
            ev.len < static_cast<std::uint16_t>(sizeof(NpcCombatPayload))) {
            return;
        }
        NpcCombatPayload pl {};
        std::memcpy(&pl, ev.data, sizeof(pl));

        std::uintptr_t best   = 0;
        float          best_d = k_match_radius;
        for (const auto obj : g_objs) {
            if (safe_read<std::uint16_t>(obj + k_max_off) != pl.max_hp) {
                continue;
            }
            float pos[3];
            if (!resolve_pos(obj, pos)) {
                continue;
            }
            const auto dx = pos[0] - pl.px;
            const auto dy = pos[1] - pl.py;
            const auto dz = pos[2] - pl.pz;
            const auto d  = std::sqrt((dx * dx) + (dy * dy) + (dz * dz));
            if (d < best_d) {
                best_d = d;
                best   = obj;
            }
        }
        if (best == 0) {
            log::get()->info("CombatSync: RX no match (pos {:.1f},{:.1f},{:.1f} maxHP {})", pl.px, pl.py,
                             pl.pz, pl.max_hp);
            return;
        }

        const auto local_life = safe_read<std::uint16_t>(best + k_life_off);
        if (pl.ev == 1 || pl.life_after == 0xFFFF) {
            if (local_life == 0xFFFF) {
                return; // already dead
            }
            const auto ok = apply_kill(best);
            if (ok) {
                note_applied(best, 0xFFFF);
            }
            log::get()->info("CombatSync: RX KILL 0x{:X} (d={:.1f}) ok={}", best, best_d, ok);
        } else {
            const int dmg = static_cast<int>(pl.life_before) - static_cast<int>(pl.life_after);
            if (dmg <= 0 || local_life <= pl.life_after) {
                return; // already at/under the relayed value
            }
            const auto ok = apply_damage(best, dmg);
            if (ok) {
                note_applied(best, local_life > dmg ? static_cast<std::uint16_t>(local_life - dmg)
                                                    : static_cast<std::uint16_t>(0xFFFF));
            }
            log::get()->info("CombatSync: RX DAMAGE 0x{:X} dmg={} (d={:.1f}) ok={}", best, dmg, best_d,
                             ok);
        }
    }

    auto status() -> Status {
        Status s;
        s.enabled = g_enabled.load(std::memory_order_relaxed);
        s.tracked = static_cast<int>(g_objs.size());
        s.events  = g_events;
        return s;
    }
} // namespace games::ac::blackflag::coop::combat
