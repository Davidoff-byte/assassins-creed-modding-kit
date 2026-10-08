#include "games/ac/rogue/hooks/hijack_avatar.hpp"

#include <atomic>
#include <cstdint>
#include <string_view>
#include <utility>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/rogue/coop/coop_net.hpp"
#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::HijackAvatarHook;

        // Fixed RVAs for the pinned ACC.exe (MD5 a323729f…).
        constexpr std::uintptr_t k_ai_update_rva  = 0x107450;
        constexpr std::uintptr_t k_index_slot_rva = 0x32DE460;
        constexpr std::uintptr_t k_get_idx_rva    = 0x352C10;
        constexpr std::uintptr_t k_get_player_rva = 0x346AA0;
        constexpr std::uintptr_t k_ai_global_rva  = 0x329BD78;

        // Found by the A4 probe: an actor's world position is three floats at actor+0x800.
        constexpr std::uintptr_t k_actor_pos = 0x800;
        constexpr std::uintptr_t k_position_slot = 0x810; // bytes we validate before writing

        std::uintptr_t g_index_slot = 0;
        std::uintptr_t g_ai_global_slot = 0;
        using GetIdxFn = int (*)();
        using GetObjFn = std::uintptr_t (*)(std::uint32_t);
        GetIdxFn g_get_idx = nullptr;
        GetObjFn g_get_obj = nullptr;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<bool>         g_enabled {true};
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

        struct Sample {
            [[maybe_unused]] static constexpr std::string_view name = "HijackAvatar";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                if (!g_enabled.load(std::memory_order_relaxed)) {
                    return;
                }
                using namespace games::ac::rogue::coop;
                const auto remote = latest_remote();
                if (!remote.valid) {
                    return;
                }
                if (g_get_idx == nullptr || g_get_obj == nullptr || g_ai_global_slot == 0 ||
                    !readable(g_ai_global_slot, 8)) {
                    return;
                }
                const auto ai = mem::read<std::uintptr_t>(g_ai_global_slot);
                if (ai == 0) {
                    return;
                }
                const auto player = g_get_obj(static_cast<std::uint32_t>(g_get_idx()));

                // Donor: first actor in partition 1 that is not the player and has a transform.
                const auto chunk = ai + ((static_cast<std::uintptr_t>(1) + 7) * 0x10);
                if (!readable(chunk, 0x40)) {
                    return;
                }
                const auto n = mem::read<std::uint16_t>(chunk + 0x0A);
                const auto data = mem::read<std::uintptr_t>(chunk);
                if (data == 0 || n == 0 || !readable(data, static_cast<std::size_t>(n) * 8)) {
                    return;
                }
                std::uintptr_t donor = 0;
                for (std::uint16_t i = 0; i < n; ++i) {
                    const auto actor = mem::read<std::uintptr_t>(data + (static_cast<std::size_t>(i) * 8));
                    if (actor != 0 && actor != player && readable(actor, k_position_slot)) {
                        donor = actor;
                        break;
                    }
                }
                if (donor == 0) {
                    return;
                }
                mem::write<float>(donor + k_actor_pos, remote.px);
                mem::write<float>(donor + k_actor_pos + 4, remote.py);
                mem::write<float>(donor + k_actor_pos + 8, remote.pz);

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
                log::get()->info("HijackAvatar: donor=0x{:X} -> peer=({:.1f},{:.1f},{:.1f})",
                                 donor, remote.px, remote.py, remote.pz);
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_enabled.store(cfg.enabled.get(), std::memory_order_relaxed);
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
        log::get()->trace("HijackAvatar: enabled={}", cfg.enabled.get());
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("HijackAvatar: GetModuleHandle failed");
            return false;
        }
        g_index_slot     = base + k_index_slot_rva;
        g_get_idx        = reinterpret_cast<GetIdxFn>(base + k_get_idx_rva);
        g_get_obj        = reinterpret_cast<GetObjFn>(base + k_get_player_rva);
        g_ai_global_slot = base + k_ai_global_rva;

        auto hook = mem::make_hook<Sample>(base + k_ai_update_rva);
        if (!hook) {
            log::get()->error("HijackAvatar: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("HijackAvatar: installed");
        return true;
    }
} // namespace hooks
