// BFCoop nav drive implementation. NavTest is strictly one-shot and dev-gated: it never
// writes to game objects, only builds a NavigationTarget in OUR OWN scratch buffer and calls
// the engine's NavigateTo through an SEH-guarded thiscall trampoline (game thread only).
#include "games/ac/blackflag/coop/nav_drive.hpp"

#include <atomic>
#include <cstdint>
#include <cstring>

#include <Windows.h>

#include "core/logger.hpp"
#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

namespace games::ac::blackflag::coop::nav {
    namespace {
        // --- PC-verified navigation addresses (AC4BFSP.exe, base 0x400000) -----------------
        constexpr std::uintptr_t k_navigate_to_rva = 0x01385ED0; // 0x01785ED0 - 0x400000
        constexpr std::int32_t   k_speed_regular   = 4;          // NavigationSpeed_Regular
        constexpr std::int32_t   k_ctx_undefined   = -1;         // NavigationContextID_NOT_DEFINED

        constexpr std::uint32_t  k_health_vt    = 0x02712F60; // CSrvNPCHealth vtable
        constexpr std::uint32_t  k_nav_vt       = 0x026F4B70; // CSrvNavigation vtable (direct scan)
        constexpr std::uint32_t  k_nav_class_id = 0x6328D910; // crc32("CSrvNavigation")

        // Health instances live in this heap window (same as combat_sync's watch window).
        constexpr std::uintptr_t k_scan_lo   = 0x2E000000;
        constexpr std::uintptr_t k_scan_hi   = 0x56000000;
        constexpr std::size_t    k_scan_step = 8U << 20U; // 8 MB per tick while testing
        constexpr std::size_t    k_max_candidates = 4096;

        std::atomic<bool> g_test {false};
        bool              g_test_armed = false;
        bool              g_test_ran   = false;
        bool              g_scan_done  = false;
        std::uintptr_t    g_cursor     = k_scan_lo;
        int               g_next       = 0; // next candidate index to try
        std::uintptr_t    g_candidates[k_max_candidates] {};
        int               g_cand_count = 0;

        struct Diag {
            std::uintptr_t p20 = 0;
            std::uintptr_t p28 = 0;
            std::uint32_t  base = 0;
            std::uint16_t  size = 0;
            int            resolved = 0;
        };
        Diag g_diag {};
        int  g_fail_logs = 0;

        std::uintptr_t g_navs[16] {};
        float          g_navd[16] {};
        int            g_nav_count = 0;
        float          g_nav_x0[16] {};
        float          g_nav_y0[16] {};
        std::int64_t   g_pick_qpc = 0;
        bool           g_pick_wait = false;

        std::atomic<bool> g_have_template_pos {false}; // a real position-type target was captured

        // Per-nav templates: captures keyed by the CSrvNavigation instance that called, so an
        // NPC's own spatial frame (which the target carries) can be reused for its command.
        struct NavTpl {
            std::uint32_t self = 0;
            std::uint8_t  bytes[0xE0] {};
        };
        NavTpl g_tpl[32];
        int    g_tpl_next = 0;

        void template_store(std::uint32_t self, const void *t) {
            if (self == 0 || t == nullptr) {
                return;
            }
            for (auto &e : g_tpl) {
                if (e.self == self) {
                    std::memcpy(e.bytes, t, 0xE0);
                    return;
                }
            }
            auto &e = g_tpl[g_tpl_next % 32];
            g_tpl_next++;
            e.self = self;
            std::memcpy(e.bytes, t, 0xE0);
        }

        auto template_find(std::uint32_t self) -> const std::uint8_t * {
            for (const auto &e : g_tpl) {
                if (e.self != 0 && e.self == self) {
                    return e.bytes;
                }
            }
            return nullptr;
        }

        // Multi-issue sequencing (hold the command like an AI would).
        std::int64_t   g_multi_last_qpc = 0;
        int            g_multi_left     = 0;
        std::uintptr_t g_chosen_nav     = 0;
        bool           g_reissue_a      = false;
        constexpr int  k_reissue_count  = 5; // total retries after the first attempt

        auto qpc_freq() -> std::int64_t {
            static const std::int64_t freq = [] {
                LARGE_INTEGER f {};
                QueryPerformanceFrequency(&f);
                return f.QuadPart;
            }();
            return freq;
        }

        std::uintptr_t g_exe_base = 0;

        auto readable(std::uintptr_t addr, std::size_t size) -> bool {
            if (addr == 0 || size == 0) {
                return false;
            }
            std::uintptr_t end = addr + size - 1;
            if (end < addr) {
                return false;
            }
            std::uintptr_t p = addr;
            while (p <= end) {
                MEMORY_BASIC_INFORMATION mbi {};
                if (VirtualQuery(reinterpret_cast<LPCVOID>(p), &mbi, sizeof(mbi)) == 0) {
                    return false;
                }
                if (mbi.State != MEM_COMMIT ||
                    (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
                    return false;
                }
                const auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                const auto rs = static_cast<std::uintptr_t>(mbi.RegionSize);
                if (rs == 0 || ba + rs <= p) {
                    return false;
                }
                p = ba + rs;
            }
            return true;
        }

        template <typename T>
        auto at(std::uintptr_t a) -> T {
            return mem::read<T>(a);
        }

        // vt -> descriptor-getter stub -> descriptor -> class id (same scheme as classres.ps1).
        auto resolve_class_id(std::uintptr_t obj, std::uint32_t &id) -> bool {
            if (!readable(obj, 4)) {
                return false;
            }
            const auto vt = at<std::uint32_t>(obj);
            if (vt < 0x1800000U || vt > 0x2B00000U || !readable(vt + 0x14, 4)) {
                return false;
            }
            auto fn = at<std::uint32_t>(vt + 0x14);
            for (int hop = 0; hop < 4; hop++) {
                if (fn < 0x401000U || fn > 0x2B00000U || !readable(fn, 8)) {
                    return false;
                }
                if (at<std::uint8_t>(fn) == 0xE9) {
                    const auto rel = at<std::int32_t>(fn + 1);
                    fn = static_cast<std::uintptr_t>(
                        static_cast<std::int64_t>(fn) + 5 + static_cast<std::int64_t>(rel));
                    continue;
                }
                break;
            }
            std::uint32_t desc = 0;
            const auto    b0   = at<std::uint8_t>(fn);
            if (b0 == 0xA1) {
                const auto g = at<std::uint32_t>(fn + 1);
                if (g < 0x400000U || !readable(g, 4)) {
                    return false;
                }
                desc = at<std::uint32_t>(g);
            } else if (b0 == 0xB8) {
                desc = at<std::uint32_t>(fn + 1);
            } else if (b0 == 0x8B && at<std::uint8_t>(fn + 1) == 0x41 &&
                       at<std::uint8_t>(fn + 3) == 0xC3) {
                desc = at<std::uint32_t>(obj + at<std::uint8_t>(fn + 2));
            } else {
                return false;
            }
            if (desc < 0x400000U || !readable(desc + 0x14, 4)) {
                return false;
            }
            id = at<std::uint32_t>(desc + 0x14);
            return true;
        }

        // --- NavigationTarget scratch buffer (verified layout) -----------------------------
        alignas(16) std::uint8_t g_target[0xE0] {};

        void build_target(float x, float y, float z) {
            std::memset(g_target, 0, sizeof(g_target));
            const auto base = reinterpret_cast<std::uintptr_t>(g_target);
            mem::write<std::uint32_t>(base + 0x00, 1U); // TargetType_Position
            mem::write<float>(base + 0x10, x);
            mem::write<float>(base + 0x14, y);
            mem::write<float>(base + 0x18, z);
            mem::write<float>(base + 0x1C, 0.0F);
            mem::write<float>(base + 0x20, 0.5F); // reach distance
            for (int i = 0; i < 4; i++) {
                mem::write<std::uint32_t>(base + 0x40 + static_cast<std::uintptr_t>(i) * 4,
                                          0x80000000U); // "no spatial position" sentinel
            }
        }

        // --- fault capture + Validate precheck -------------------------------------------------
        std::uint32_t  g_exc_code = 0;
        std::uintptr_t g_exc_addr = 0;

        auto nav_exc_filter(LPEXCEPTION_POINTERS ep) -> int {
            g_exc_code = ep->ExceptionRecord->ExceptionCode;
            g_exc_addr = reinterpret_cast<std::uintptr_t>(ep->ExceptionRecord->ExceptionAddress);
            return EXCEPTION_EXECUTE_HANDLER;
        }

        // SEH-guarded thiscall. rc: 0 = accepted, 7 = invalid target, -1 = faulted.
        // boolB=1 matches every NavigateTo the engine itself performs (NavWatch: 60/60 calls
        // A=0 B=1) - it engages the vtable can-navigate precheck + command activation.
        auto nav_to(std::uintptr_t nav, const void *target, int bool_a) -> int {
            g_exc_code = 0;
            g_exc_addr = 0;
            __try {
                using Fn = int(__thiscall *)(void *, const void *, int, int, int, int);
                return reinterpret_cast<Fn>(g_exe_base + k_navigate_to_rva)(
                    reinterpret_cast<void *>(nav), target, static_cast<int>(k_speed_regular), bool_a,
                    1, static_cast<int>(k_ctx_undefined));
            } __except (nav_exc_filter(GetExceptionInformation())) {
                return -1;
            }
        }

        // Background NavigationTarget template captured from real engine calls (NavWatch).
        alignas(16) std::uint8_t g_template_pos[0xE0] {};

        // SEH-guarded NavigationTarget::Validate (@0x512160). 1 = valid, 0 = invalid, -1 = fault.
        auto pc_validate(std::uintptr_t target) -> int {
            __try {
                using Fn = unsigned char(__thiscall *)(void *);
                return static_cast<int>(reinterpret_cast<Fn>(g_exe_base + 0x112160)(
                    reinterpret_cast<void *>(target)));
            } __except (nav_exc_filter(GetExceptionInformation())) {
                return -1;
            }
        }

        // Build the call target from a captured engine target: prefers the CHOSEN nav's own
        // template (its spatial frame), falls back to the latest global type-1 capture.
        // Patches only type/position/reach.
        auto build_from_template(std::uintptr_t nav, float x, float y, float z) -> bool {
            const std::uint8_t *tpl = template_find(static_cast<std::uint32_t>(nav));
            if (tpl == nullptr) {
                if (!g_have_template_pos.load(std::memory_order_relaxed)) {
                    return false;
                }
                tpl = g_template_pos;
            }
            std::memcpy(g_target, tpl, sizeof(g_target));
            const auto base = reinterpret_cast<std::uintptr_t>(g_target);
            mem::write<std::uint32_t>(base + 0x00, 1U);
            mem::write<float>(base + 0x10, x);
            mem::write<float>(base + 0x14, y);
            mem::write<float>(base + 0x18, z);
            mem::write<float>(base + 0x20, 0.5F);
            return true;
        }

        // --- NavWatch: capture real NavigateTo traffic (read-only) ----------------------------
        constexpr std::uintptr_t k_pat_navto_rva     = 0x0021F180; // NPCNavigation::NavigateTo(target)
        constexpr std::uintptr_t k_pat_navto_ctx_rva = 0x00224410; // NPCNavigation::NavigateTo(target, ctx)
        constexpr int            k_watch_log_cap     = 60;
        constexpr int            k_watch_work_cap    = 500;

        std::atomic<int> g_watch_calls[3] {};
        mem::MidHook     g_watch_hook[3];

        void watch_capture(std::uint32_t self, std::uint32_t target) {
            if (target >= 0x10000U && readable(target, 0xE0)) {
                const auto ttype = at<std::uint32_t>(target);
                // Only genuine position targets (type 1) become templates: patching a type-2
                // capture into a type-1 call left engine-inconsistent fields (seen live).
                if (ttype == 1U) {
                    std::memcpy(g_template_pos, reinterpret_cast<const void *>(target), 0xE0);
                    g_have_template_pos.store(true, std::memory_order_relaxed);
                    template_store(self, reinterpret_cast<const void *>(target));
                }
            }
        }

        void watch_log(int idx, int n, std::uintptr_t self, std::uint32_t target, int speed, int a,
                       int b, int ctx, std::uint32_t caller) {
            const auto vt = readable(self, 4) ? at<std::uint32_t>(self) : 0U;
            const auto caller_rva =
                (g_exe_base != 0 && caller > g_exe_base) ? (caller - g_exe_base) : 0U;
            if (target >= 0x10000U && readable(target, 0x24)) {
                const auto ttype = at<std::uint32_t>(target);
                const auto x     = at<float>(target + 0x10);
                const auto y     = at<float>(target + 0x14);
                const auto z     = at<float>(target + 0x18);
                const auto reach = at<float>(target + 0x20);
                watch_capture(static_cast<std::uint32_t>(self), target);
                log::get()->info(
                    "NavWatch[{}]: #{} self=0x{:X} vt=0x{:X} type={} pos=({:.1f},{:.1f},{:.1f}) "
                    "reach={:.2f} speed={} A={} B={} ctx={} caller=+0x{:X}",
                    idx, n, self, vt, ttype, x, y, z, reach, speed, a, b, ctx, caller_rva);
            } else {
                log::get()->info(
                    "NavWatch[{}]: #{} self=0x{:X} vt=0x{:X} target=0x{:X} speed={} A={} B={} "
                    "ctx={} caller=+0x{:X}",
                    idx, n, self, vt, target, speed, a, b, ctx, caller_rva);
            }
        }

        // CSrvNavigation::NavigateTo(target, speed, boolA, boolB, ctx)
        struct WatchNavTo {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                const auto n = g_watch_calls[0].fetch_add(1, std::memory_order_relaxed);
                if (n >= k_watch_work_cap) {
                    return;
                }
                const auto stack  = static_cast<std::uintptr_t>(r.esp);
                const auto target = at<std::uint32_t>(stack + 4);
                if (n < k_watch_log_cap) {
                    watch_log(0, n, static_cast<std::uintptr_t>(r.ecx), target,
                              static_cast<int>(at<std::uint32_t>(stack + 8)),
                              static_cast<int>(at<std::uint32_t>(stack + 0xC)),
                              static_cast<int>(at<std::uint32_t>(stack + 0x10)),
                              static_cast<int>(at<std::uint32_t>(stack + 0x14)),
                              at<std::uint32_t>(stack));
                } else {
                    watch_capture(static_cast<std::uint32_t>(r.ecx), target);
                }
            }
        };

        // NPCNavigation::NavigateTo(target)
        struct WatchPatTo {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                const auto n = g_watch_calls[1].fetch_add(1, std::memory_order_relaxed);
                if (n >= k_watch_work_cap) {
                    return;
                }
                const auto stack  = static_cast<std::uintptr_t>(r.esp);
                const auto target = at<std::uint32_t>(stack + 4);
                if (n < k_watch_log_cap) {
                    watch_log(1, n, static_cast<std::uintptr_t>(r.ecx), target, -1, -1, -1, -1,
                              at<std::uint32_t>(stack));
                } else {
                    watch_capture(static_cast<std::uint32_t>(r.ecx), target);
                }
            }
        };

        // NPCNavigation::NavigateTo(target, ctx)
        struct WatchPatToCtx {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                const auto n = g_watch_calls[2].fetch_add(1, std::memory_order_relaxed);
                if (n >= k_watch_work_cap) {
                    return;
                }
                const auto stack  = static_cast<std::uintptr_t>(r.esp);
                const auto target = at<std::uint32_t>(stack + 4);
                if (n < k_watch_log_cap) {
                    watch_log(2, n, static_cast<std::uintptr_t>(r.ecx), target, -1, -1, -1,
                              static_cast<int>(at<std::uint32_t>(stack + 8)),
                              at<std::uint32_t>(stack));
                } else {
                    watch_capture(static_cast<std::uint32_t>(r.ecx), target);
                }
            }
        };

        // health -> +0x20/+0x28 -> P -> vec@+0x70/+0x68 -> service with class id CSrvNavigation.
        // Fills g_diag for failure logging.
        auto nav_from_health(std::uintptr_t h, std::uintptr_t &nav_out, std::uintptr_t &p_out)
            -> bool {
            g_diag = Diag {};
            if (!readable(h + 0x20, 0x10)) {
                return false;
            }
            g_diag.p20 = at<std::uint32_t>(h + 0x20);
            g_diag.p28 = at<std::uint32_t>(h + 0x28);
            for (int io = 0; io < 2; io++) {
                const auto P = (io == 0) ? g_diag.p20 : g_diag.p28;
                if (P < 0x10000U || !readable(P + 0x68, 0x14)) {
                    continue;
                }
                for (int vo = 0; vo < 2; vo++) {
                    const auto base =
                        at<std::uint32_t>(P + 0x70 - static_cast<std::uintptr_t>(vo) * 8);
                    const auto size =
                        at<std::uint16_t>(P + 0x76 - static_cast<std::uintptr_t>(vo) * 8);
                    if (base < 0x10000U || size < 2 || size > 200) {
                        continue;
                    }
                    if (!readable(base, static_cast<std::size_t>(size) * 4)) {
                        continue;
                    }
                    if (g_diag.base == 0) {
                        g_diag.base = base;
                        g_diag.size = size;
                    }
                    for (std::uint32_t i = 0; i < size; i++) {
                        const auto svc = at<std::uint32_t>(base + i * 4);
                        if (svc < 0x10000U || !readable(svc, 4)) {
                            continue;
                        }
                        std::uint32_t id = 0;
                        if (resolve_class_id(svc, id)) {
                            g_diag.resolved++;
                            if (id == k_nav_class_id) {
                                nav_out = svc;
                                p_out   = P;
                                return true;
                            }
                        }
                    }
                }
            }
            return false;
        }

        // Incremental heap slice scan for CSrvNavigation instances (direct vt match) - finds
        // EVERY navigating NPC including walking civilians, unlike the old health-anchor chain
        // (guards only - and guards stand still).
        void scan_for_health() {
            static std::uint8_t buf[0x10004];
            const auto end = (g_cursor + k_scan_step < k_scan_hi) ? g_cursor + k_scan_step
                                                                  : k_scan_hi;
            std::uintptr_t p = g_cursor;
            MEMORY_BASIC_INFORMATION mbi {};
            while (p < end && g_cand_count < static_cast<int>(k_max_candidates)) {
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
                if (sz == 0 || mbi.State != MEM_COMMIT) {
                    p = (sz == 0) ? p + 0x1000 : ba + sz;
                    continue;
                }
                const auto stop = (ba + sz < end) ? (ba + sz) : end;
                for (std::uintptr_t c = ba; c < stop; c += 0x10000) {
                    const auto remain = stop - c;
                    const auto want   = static_cast<SIZE_T>(remain < 0x10004 ? remain : 0x10004);
                    SIZE_T got = 0;
                    if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(c), buf,
                                           want, &got) ||
                        got < 4) {
                        continue;
                    }
                    for (SIZE_T i = 0; i + 4 <= got; i += 4) {
                        std::uint32_t v = 0;
                        std::memcpy(&v, buf + i, 4);
                        if (v != k_nav_vt) {
                            continue;
                        }
                        const auto obj = c + i;
                        if (readable(obj + 0x10C, 12)) {
                            g_candidates[g_cand_count++] = obj;
                        }
                        if (g_cand_count >= static_cast<int>(k_max_candidates)) {
                            break;
                        }
                    }
                }
                p = ba + sz;
            }
            g_cursor = end;
        }

        void fire_attempt(float px, float py, float pz, bool first) {
            const bool templ = build_from_template(g_chosen_nav, px, py, pz);
            if (!templ) {
                build_target(px, py, pz);
            }
            if (first) {
                const auto taddr = reinterpret_cast<std::uintptr_t>(g_target);
                const auto vrc   = pc_validate(taddr);
                log::get()->info("NavTest: target ready (template={} validate={})", templ ? 1 : 0,
                                 vrc);
            }
            const int  a  = g_reissue_a ? 1 : 0;
            const auto rc = nav_to(g_chosen_nav, g_target, a);
            float ex = 0.0F;
            float ey = 0.0F;
            float ez = 0.0F;
            if (readable(g_chosen_nav + 0x10C, 12)) {
                ex = at<float>(g_chosen_nav + 0x10C);
                ey = at<float>(g_chosen_nav + 0x110);
                ez = at<float>(g_chosen_nav + 0x114);
            }
            const auto dx = ex - px;
            const auto dy = ey - py;
            const auto d  = std::sqrt(dx * dx + dy * dy);
            if (rc == -1) {
                log::get()->warn(
                    "NavTest: attempt A={} rc=-1 FAULT code=0x{:X} at exe+0x{:X} "
                    "ent=({:.1f},{:.1f},{:.1f})",
                    a, g_exc_code, g_exc_addr - g_exe_base, ex, ey, ez);
            } else {
                log::get()->info("NavTest: attempt A={} rc={} ent=({:.1f},{:.1f},{:.1f}) dist={:.1f}",
                                 a, rc, ex, ey, ez, d);
            }
            g_reissue_a = !g_reissue_a;
            if (first) {
                g_multi_left = k_reissue_count;
            } else {
                g_multi_left--;
            }
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            g_multi_last_qpc = now.QuadPart;
            if (g_multi_left <= 0 || rc == -1) {
                g_test_ran = true;
            }
        }

        void run_test(float px, float py, float pz) {
            // Keep growing the candidate pool across ticks (8 MB/frame) until we have enough
            // or the window is exhausted. Some anchors don't expose a nav service (seen live),
            // so walk every candidate instead of trusting the first-found one.
            if (!g_scan_done) {
                scan_for_health();
                if (g_cand_count >= static_cast<int>(k_max_candidates) || g_cursor >= k_scan_hi) {
                    g_scan_done = true;
                }
            }
            while (g_next < g_cand_count && g_nav_count < 16) {
                const auto nav = g_candidates[g_next++];
                float      ex  = 0.0F;
                float      ey  = 0.0F;
                if (readable(nav + 0x10C, 12)) {
                    ex = at<float>(nav + 0x10C);
                    ey = at<float>(nav + 0x110);
                }
                const auto dx = ex - px;
                const auto dy = ey - py;
                const auto d  = std::sqrt(dx * dx + dy * dy);
                if (d > 60.0F) {
                    continue; // only nearby NPCs matter for the visual test
                }
                g_navs[g_nav_count] = nav;
                g_navd[g_nav_count] = d;
                g_nav_count++;
                log::get()->info("NavTest: nav 0x{:X} ent=({:.1f},{:.1f}) d={:.1f}m", nav, ex, ey, d);
            }
            if (g_nav_count == 0) {
                if (g_scan_done) {
                    log::get()->warn(
                        "NavTest: {} candidates scanned, none resolved a CSrvNavigation",
                        g_cand_count);
                    g_test_ran = true;
                }
                return;
            }
            if (!g_scan_done && g_nav_count < 8) {
                return; // keep collecting navs next tick for a better pick
            }
            // Phase B: pick the NPC that is ALREADY MOVING (its nav statechart is in a
            // navigation-capable state - idle NPCs return rc=3 to the precheck). Record a
            // first position sample, wait ~0.7 s, take the second; speed = displacement.
            if (!g_pick_wait) {
                for (int i = 0; i < g_nav_count; i++) {
                    if (readable(g_navs[i] + 0x10C, 12)) {
                        g_nav_x0[i] = at<float>(g_navs[i] + 0x10C);
                        g_nav_y0[i] = at<float>(g_navs[i] + 0x110);
                    }
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                g_pick_qpc  = now.QuadPart;
                g_pick_wait = true;
                return;
            }
            {
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                if (now.QuadPart - g_pick_qpc < qpc_freq() * 7 / 10) {
                    return; // wait for the second sample
                }
            }
            int   best     = 0;
            float best_spd = -1.0F;
            for (int i = 0; i < g_nav_count; i++) {
                float x1 = g_nav_x0[i];
                float y1 = g_nav_y0[i];
                if (readable(g_navs[i] + 0x10C, 12)) {
                    x1 = at<float>(g_navs[i] + 0x10C);
                    y1 = at<float>(g_navs[i] + 0x110);
                }
                const auto dx = x1 - g_nav_x0[i];
                const auto dy = y1 - g_nav_y0[i];
                const auto spd = std::sqrt(dx * dx + dy * dy) / 0.7F;
                log::get()->info("NavTest: pick nav 0x{:X} d={:.1f}m spd={:.2f}m/s", g_navs[i],
                                 g_navd[i], spd);
                if (spd > best_spd) {
                    best_spd = spd;
                    best     = i;
                }
            }
            if (best_spd < 0.30F) {
                // nobody moving - fall back to the closest
                for (int i = 1; i < g_nav_count; i++) {
                    if (g_navd[i] < g_navd[best]) {
                        best = i;
                    }
                }
                log::get()->info("NavTest: no mover found, using closest (d={:.1f}m)", g_navd[best]);
            } else {
                log::get()->info("NavTest: chosen MOVING nav=0x{:X} spd={:.2f}m/s d={:.1f}m", g_navs[best],
                                 best_spd, g_navd[best]);
            }
            g_chosen_nav = g_navs[best];
            fire_attempt(px, py, pz, true);
        }
    } // namespace

    void set_test(bool on) {
        if (on) {
            if (!g_test.exchange(true)) {
                g_test_armed = true;
                g_test_ran   = false;
                g_scan_done  = false;
                g_cand_count = 0;
                g_next       = 0;
                g_fail_logs  = 0;
                g_nav_count  = 0;
                g_chosen_nav = 0;
                g_pick_wait  = false;
                g_pick_qpc   = 0;
                g_multi_left = 0;
                g_multi_last_qpc = 0;
                g_reissue_a  = false;
                g_cursor     = k_scan_lo;
                log::get()->info(
                    "NavTest: armed (CSrvNPCHealth -> CSrvNavigation -> NavigateTo(player))");
            }
        } else {
            g_test.store(false);
            log::get()->info("NavTest: off");
        }
    }

    void install_watch(std::uintptr_t exe_base) {
        g_exe_base = exe_base;
        auto h0 = mem::make_hook<WatchNavTo>(exe_base + k_navigate_to_rva);
        if (h0) {
            g_watch_hook[0] = std::move(*h0);
            log::get()->info("NavWatch: CSrvNavigation::NavigateTo hooked @0x{:X}",
                             exe_base + k_navigate_to_rva);
        } else {
            log::get()->error("NavWatch: NavigateTo hook failed: {}", h0.error());
        }
        auto h1 = mem::make_hook<WatchPatTo>(exe_base + k_pat_navto_rva);
        if (h1) {
            g_watch_hook[1] = std::move(*h1);
            log::get()->info("NavWatch: NPCNavigation::NavigateTo hooked @0x{:X}",
                             exe_base + k_pat_navto_rva);
        } else {
            log::get()->error("NavWatch: NPCNavigation::NavigateTo hook failed: {}", h1.error());
        }
        auto h2 = mem::make_hook<WatchPatToCtx>(exe_base + k_pat_navto_ctx_rva);
        if (h2) {
            g_watch_hook[2] = std::move(*h2);
            log::get()->info("NavWatch: NPCNavigation::NavigateTo(ctx) hooked @0x{:X}",
                             exe_base + k_pat_navto_ctx_rva);
        } else {
            log::get()->error("NavWatch: NPCNavigation::NavigateTo(ctx) hook failed: {}",
                              h2.error());
        }
    }

    void tick(float px, float py, float pz) {
        if (!g_test.load(std::memory_order_relaxed) || !g_test_armed || g_test_ran) {
            return;
        }
        if (g_exe_base == 0) {
            g_exe_base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        }
        if (g_exe_base == 0) {
            return;
        }
        if (g_chosen_nav != 0) {
            // Hold the command: re-issue every ~1.5 s until the sequence ends.
            if (g_multi_left > 0) {
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                if (g_multi_last_qpc != 0 &&
                    now.QuadPart - g_multi_last_qpc >= qpc_freq() * 3 / 2) {
                    fire_attempt(px, py, pz, false);
                }
            } else {
                g_test_ran = true;
            }
            return;
        }
        run_test(px, py, pz);
    }
} // namespace games::ac::blackflag::coop::nav
