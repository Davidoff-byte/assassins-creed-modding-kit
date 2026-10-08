#include "games/ac/rogue/hooks/debug_spawn.hpp"

#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <string_view>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::DebugSpawnHook;

        // Fixed RVAs for the pinned ACC.exe (MD5 a323729f…), image base 0x140000000.
        constexpr std::uintptr_t k_hook_rva       = 0x46B6F0;  // Ai::SpawningManagerUpdate (per-frame)
        constexpr std::uintptr_t k_ready_slot_rva = 0x32DE460; // DAT_1432de460 (ready gate)
        constexpr std::uintptr_t k_get_idx_rva    = 0x352C10;  // active player index
        constexpr std::uintptr_t k_get_player_rva = 0x346AA0;  // player object by index
        constexpr std::uintptr_t k_get_pos_rva    = 0x0D8600;  // PlayerPosition struct
        constexpr std::uintptr_t k_dude_mgr_rva   = 0x329DE70; // DAT_14329de70 (debug-dude manager)

        // Debug-cheat spawn handlers (see RE-NOTES §10). Each: create a 0x40-byte debug-dude
        // object, set its type, register it with the manager. Menu calls them with arg 1.
        constexpr std::array<std::uintptr_t, 4> k_spawn_rvas {
            0x1E91D50, // 0 = Follow Dude  (type 0)
            0x1E91EC0, // 1 = RedBall Dude (type 1)
            0x1E91F00, // 2 = Still Dude   (type 3)
            0x1E91D90, // 3 = Fight Dude   (type 4)
        };
        constexpr std::array<const char *, 4> k_spawn_names {"Follow", "RedBall", "Still", "Fight"};

        // PlayerPosition struct offsets (RE-NOTES §7).
        constexpr std::uintptr_t k_pos_flag = 0x18;
        constexpr std::uintptr_t k_pos_ptr  = 0x40;
        constexpr std::uintptr_t k_pos_off  = 0x30;

        using SpawnFn  = void (*)(int);
        using GetIdxFn = int (*)();
        using GetObjFn = std::uintptr_t (*)(std::uint32_t);
        using GetPosFn = std::uintptr_t (*)(std::uintptr_t);

        std::array<SpawnFn, 4> g_spawn_fns {};
        std::uintptr_t  g_ready_slot = 0;
        std::uintptr_t  g_dude_mgr   = 0;
        GetIdxFn        g_get_idx = nullptr;
        GetObjFn        g_get_obj = nullptr;
        GetPosFn        g_get_pos = nullptr;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<bool>         g_enabled {false};
        std::atomic<int>          g_kind {-1};
        std::atomic<bool>         g_spawned {false};
        std::atomic<float>        g_log_hz {1.0F};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        std::int64_t              g_in_game_since = 0;
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

        auto in_game() -> bool {
            if (g_get_idx == nullptr || g_get_obj == nullptr || g_get_pos == nullptr ||
                g_ready_slot == 0 || !readable(g_ready_slot, 8) ||
                mem::read<std::uintptr_t>(g_ready_slot) == 0) {
                return false;
            }
            const int idx = g_get_idx();
            if (idx < 0) {
                return false;
            }
            const auto player = g_get_obj(static_cast<std::uint32_t>(idx));
            if (!readable(player, 0x80)) {
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
            const float x = mem::read<float>(base + k_pos_off);
            const float y = mem::read<float>(base + k_pos_off + 4);
            const float z = mem::read<float>(base + k_pos_off + 8);
            return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) &&
                   std::fabs(x) < 1.0e7F && std::fabs(y) < 1.0e7F && std::fabs(z) < 1.0e7F;
        }

        // Live count of registered debug dudes: manager->+0x0A (u16), see FUN_14016b0d0.
        auto dude_count() -> int {
            if (g_dude_mgr == 0 || !readable(g_dude_mgr, 8)) {
                return -1;
            }
            const auto mgr = mem::read<std::uintptr_t>(g_dude_mgr);
            if (mgr == 0 || !readable(mgr + 0x0A, 2)) {
                return -1;
            }
            return mem::read<std::uint16_t>(mgr + 0x0A);
        }

        struct Probe {
            [[maybe_unused]] static constexpr std::string_view name = "DebugSpawn";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                if (!g_enabled.load(std::memory_order_relaxed)) {
                    return;
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);

                if (!in_game()) {
                    g_in_game_since = 0;
                    g_spawned.store(false, std::memory_order_relaxed); // re-arm for a new level
                    return;
                }
                // Debounce: require a full second of continuous in-game before firing, so the
                // menu/loading flicker cannot spam spawns.
                if (g_in_game_since == 0) {
                    g_in_game_since = now.QuadPart;
                    return;
                }
                if (!g_spawned.load(std::memory_order_relaxed) && freq > 0 &&
                    now.QuadPart - g_in_game_since >= freq) {
                    const int before = dude_count();
                    const int kind = g_kind.load(std::memory_order_relaxed);
                    if (kind < 0) {
                        for (std::size_t k = 0; k < g_spawn_fns.size(); ++k) {
                            if (g_spawn_fns[k] != nullptr) {
                                g_spawn_fns[k](1);
                                log::get()->info("DebugSpawn: {} dude spawned (count {})",
                                                 k_spawn_names[k], dude_count());
                            }
                        }
                    } else if (kind < static_cast<int>(g_spawn_fns.size()) &&
                               g_spawn_fns[static_cast<std::size_t>(kind)] != nullptr) {
                        g_spawn_fns[static_cast<std::size_t>(kind)](1);
                        log::get()->info("DebugSpawn: {} dude spawned (count {})",
                                         k_spawn_names[static_cast<std::size_t>(kind)], dude_count());
                    }
                    g_spawned.store(true, std::memory_order_relaxed);
                    log::get()->info("DebugSpawn: spawn pass done in-game (manager count {} -> {})",
                                     before, dude_count());
                }

                const auto hz = g_log_hz.load(std::memory_order_relaxed);
                if (hz <= 0.0F) {
                    return;
                }
                const auto last = g_last_log.load(std::memory_order_relaxed);
                if (freq <= 0 ||
                    now.QuadPart - last <
                        static_cast<std::int64_t>(static_cast<double>(freq) / hz)) {
                    return;
                }
                g_last_log.store(now.QuadPart, std::memory_order_relaxed);
                log::get()->info("DebugSpawn: in-game spawned={} dudes={}",
                                 g_spawned.load(), dude_count());
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_enabled.store(cfg.enabled.get(), std::memory_order_relaxed);
        g_kind.store(static_cast<int>(cfg.kind.get()), std::memory_order_relaxed);
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
        log::get()->trace("DebugSpawn: enabled={} kind={} log {:.1f} Hz",
                          cfg.enabled.get(), static_cast<int>(cfg.kind.get()), cfg.log_hz.get());
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("DebugSpawn: GetModuleHandle failed");
            return false;
        }
        for (std::size_t k = 0; k < k_spawn_rvas.size(); ++k) {
            g_spawn_fns[k] = reinterpret_cast<SpawnFn>(base + k_spawn_rvas[k]);
        }
        g_ready_slot = base + k_ready_slot_rva;
        g_dude_mgr   = base + k_dude_mgr_rva;
        g_get_idx    = reinterpret_cast<GetIdxFn>(base + k_get_idx_rva);
        g_get_obj    = reinterpret_cast<GetObjFn>(base + k_get_player_rva);
        g_get_pos    = reinterpret_cast<GetPosFn>(base + k_get_pos_rva);

        auto hook = mem::make_hook<Probe>(base + k_hook_rva);
        if (!hook) {
            log::get()->error("DebugSpawn: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("DebugSpawn: installed (followFn 0x{:X})",
                         reinterpret_cast<std::uintptr_t>(g_spawn_fns[0]));
        return true;
    }
} // namespace hooks
