#include "games/ac/rogue/hooks/player_probe.hpp"

#include <atomic>
#include <cmath>
#include <cstdint>
#include <string_view>
#include <utility>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::PlayerProbeHook;

        // Fixed RVAs for the pinned ACC.exe (MD5 a323729f…).
        constexpr std::uintptr_t k_ai_update_rva   = 0x107450; // Ai::AIUpdate (per-frame)
        constexpr std::uintptr_t k_index_slot_rva  = 0x32DE460;
        constexpr std::uintptr_t k_get_idx_rva     = 0x352C10;
        constexpr std::uintptr_t k_get_player_rva  = 0x346AA0;
        constexpr std::uintptr_t k_get_pos_rva     = 0x0D8600;
        constexpr std::uintptr_t k_ai_global_rva   = 0x329BD78; // DAT_14329bd78 (AI global)
        constexpr std::uintptr_t k_pos_flag        = 0x18;
        constexpr std::uintptr_t k_pos_ptr         = 0x40;
        constexpr std::uintptr_t k_pos_off         = 0x30;

        constexpr int k_max_actors = 24;
        constexpr std::uintptr_t k_scan_end = 0x1000;
        constexpr float k_match_eps = 2.0F;
        constexpr float k_near = 250.0F;

        std::uintptr_t g_index_slot = 0;
        std::uintptr_t g_ai_global_slot = 0;
        using GetIdxFn = int (*)();
        using GetObjFn = std::uintptr_t (*)(std::uint32_t);
        using GetPosFn = std::uintptr_t (*)(std::uintptr_t);
        GetIdxFn g_get_idx = nullptr;
        GetObjFn g_get_obj = nullptr;
        GetPosFn g_get_pos = nullptr;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<float>        g_log_hz {1.0F};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        mem::MidHook              g_hook;
#pragma clang diagnostic pop

        auto readable(std::uintptr_t addr, std::size_t size) -> bool {
            if (addr == 0 || addr < 0x10000) {
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
            if ((mbi.Protect & ok) == 0) {
                return false;
            }
            const auto end =
                reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
            return addr + size <= end;
        }

        auto player_position(float &x, float &y, float &z) -> bool {
            if (g_get_idx == nullptr || g_get_obj == nullptr || g_get_pos == nullptr ||
                g_index_slot == 0 || !readable(g_index_slot, 8) ||
                mem::read<std::uintptr_t>(g_index_slot) == 0) {
                return false;
            }
            const int idx = g_get_idx();
            if (idx < 0) {
                return false;
            }
            const auto player = g_get_obj(static_cast<std::uint32_t>(idx));
            if (!readable(player, 0x140)) {
                return false;
            }
            const auto ps = g_get_pos(player);
            if (!readable(ps, 0x50)) {
                return false;
            }
            std::uintptr_t base = 0;
            if (mem::read<std::uint64_t>(ps + k_pos_flag) == 0) {
                base = ps + 0x20;
            } else {
                const auto ptr = mem::read<std::uintptr_t>(ps + k_pos_ptr);
                if (ptr != 0 && readable(ptr, 0x40)) {
                    base = ptr + 0x20;
                }
            }
            if (!readable(base + k_pos_off, 12)) {
                return false;
            }
            x = mem::read<float>(base + k_pos_off);
            y = mem::read<float>(base + k_pos_off + 4);
            z = mem::read<float>(base + k_pos_off + 8);
            return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
        }

        // Enumerate actors from the AI global's partitions and find which actor (and which
        // offset inside it) holds the player's world position.
        auto probe() -> void {
            if (g_ai_global_slot == 0 || !readable(g_ai_global_slot, 8)) {
                return;
            }
            float px = 0.0F;
            float py = 0.0F;
            float pz = 0.0F;
            if (!player_position(px, py, pz)) {
                log::get()->info("PlayerProbe: player position unavailable");
                return;
            }
            const auto ai = mem::read<std::uintptr_t>(g_ai_global_slot);
            if (ai == 0) {
                log::get()->info("PlayerProbe: aiGlobal null");
                return;
            }
            int total = 0;
            int matches = 0;
            // Scan a region for any float triple matching the player's world position.
            const auto scan = [&](std::uintptr_t base, std::uintptr_t size, const char *tag,
                                  std::uintptr_t who, std::uintptr_t extra) -> int {
                int hits = 0;
                for (std::uintptr_t off = 0; off + 12 <= size; off += 4) {
                    const float ax = mem::read<float>(base + off);
                    const float ay = mem::read<float>(base + off + 4);
                    const float az = mem::read<float>(base + off + 8);
                    if (std::fabs(ax - px) < k_match_eps && std::fabs(ay - py) < k_match_eps &&
                        std::fabs(az - pz) < k_match_eps) {
                        ++hits;
                        log::get()->info(
                            "PlayerProbe: {} who=0x{:X} extra=0x{:X} off=0x{:X} pos=({:.1f},{:.1f},{:.1f})",
                            tag, who, extra, off, ax, ay, az);
                        if (hits >= 6) {
                            break;
                        }
                    }
                }
                return hits;
            };
            // Ground truth for an NPC actor: a component float triple close to the player
            // (nearby NPCs), tagged with the component's vtable so we can identify the class.
            const auto scan_near = [&](std::uintptr_t base, std::uintptr_t size, std::uintptr_t who,
                                       std::uintptr_t extra, std::uintptr_t vt) -> int {
                int hits = 0;
                for (std::uintptr_t off = 0; off + 12 <= size; off += 4) {
                    const float ax = mem::read<float>(base + off);
                    const float ay = mem::read<float>(base + off + 4);
                    const float az = mem::read<float>(base + off + 8);
                    if (!std::isfinite(ax) || !std::isfinite(ay) || !std::isfinite(az)) {
                        continue;
                    }
                    const float dx = ax - px;
                    const float dy = ay - py;
                    const float dz = az - pz;
                    if ((dx * dx) + (dy * dy) + (dz * dz) < k_near * k_near) {
                        ++hits;
                        log::get()->info(
                            "PlayerProbe: NEAR who=0x{:X} compIdx=0x{:X} vt=0x{:X} off=0x{:X} pos=({:.1f},{:.1f},{:.1f})",
                            who, extra, vt, off, ax, ay, az);
                        if (hits >= 3) {
                            break;
                        }
                    }
                }
                return hits;
            };
            int near_lines = 0;
            for (int part = 0; part < 8; ++part) {
                const auto chunk = ai + ((static_cast<std::uintptr_t>(part) + 7) * 0x10);
                if (!readable(chunk, 0x40)) {
                    continue;
                }
                const auto n = mem::read<std::uint16_t>(chunk + 0x0A);
                const auto data = mem::read<std::uintptr_t>(chunk);
                if (data == 0 || n == 0 || !readable(data, static_cast<std::size_t>(n) * 8)) {
                    continue;
                }
                total += n;
                const int lim = n < k_max_actors ? n : k_max_actors;
                for (int i = 0; i < lim; ++i) {
                    const auto actor = mem::read<std::uintptr_t>(data + (static_cast<std::size_t>(i) * 8));
                    if (!readable(actor, k_scan_end)) {
                        continue;
                    }
                    if (scan(actor, k_scan_end, "ACTOR", actor,
                             static_cast<std::uintptr_t>(part)) > 0) {
                        ++matches;
                    }
                    // Walk components at actor+0x3b0 and look for a near-player transform.
                    if (readable(actor + 0x3b0, 0x10)) {
                        const auto carr = mem::read<std::uintptr_t>(actor + 0x3b0);
                        const auto cn = mem::read<std::uint16_t>(actor + 0x3ba);
                        const int clim = cn < 64 ? cn : 64;
                        if (carr != 0 && clim > 0 &&
                            readable(carr, static_cast<std::size_t>(clim) * 8)) {
                            for (int j = 0; j < clim; ++j) {
                                const auto comp =
                                    mem::read<std::uintptr_t>(carr + (static_cast<std::size_t>(j) * 8));
                                if (!readable(comp, 0x200)) {
                                    continue;
                                }
                                const auto vt = mem::read<std::uintptr_t>(comp);
                                if (near_lines < 40) {
                                    near_lines += scan_near(comp, 0x200, actor,
                                                            static_cast<std::uintptr_t>(j), vt);
                                }
                            }
                        }
                    }
                }
            }
            log::get()->info("PlayerProbe: player=({:.1f},{:.1f},{:.1f}) actors={} matches={}",
                             px, py, pz, total, matches);
        }

        struct Sample {
            [[maybe_unused]] static constexpr std::string_view name = "PlayerProbe";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                const auto hz = g_log_hz.load(std::memory_order_relaxed);
                if (hz <= 0.0F) {
                    return;
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                const auto last = g_last_log.load(std::memory_order_relaxed);
                if (freq <= 0 ||
                    now.QuadPart - last <
                        static_cast<std::int64_t>(static_cast<double>(freq) / hz)) {
                    return;
                }
                g_last_log.store(now.QuadPart, std::memory_order_relaxed);
                probe();
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
        log::get()->trace("PlayerProbe: log {:.1f} Hz", cfg.log_hz.get());
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("PlayerProbe: GetModuleHandle failed");
            return false;
        }
        g_index_slot     = base + k_index_slot_rva;
        g_ai_global_slot = base + k_ai_global_rva;
        g_get_idx        = reinterpret_cast<GetIdxFn>(base + k_get_idx_rva);
        g_get_obj        = reinterpret_cast<GetObjFn>(base + k_get_player_rva);
        g_get_pos        = reinterpret_cast<GetPosFn>(base + k_get_pos_rva);

        auto hook = mem::make_hook<Sample>(base + k_ai_update_rva);
        if (!hook) {
            log::get()->error("PlayerProbe: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("PlayerProbe: installed");
        return true;
    }
} // namespace hooks
