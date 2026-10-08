#include "games/ac/rogue/hooks/counter_window.hpp"

#include <cstddef>
#include <cstdint>

#include <array>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::CounterWindowHook;

        // Counter phases, in dispatch order, and the id each classifier compares against.
        constexpr std::array<std::uint32_t, 4> k_phase_ids = {0x1F6, 0x1F7, 0x1F8, 0x1F9};

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::array<std::uintptr_t, 4> g_phase_imm {};
#pragma clang diagnostic pop

        auto phase_bit(std::size_t i) -> int {
            return 1 << static_cast<int>(i);
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        const bool enabled = cfg.counter_window.get();
        const int  mask    = cfg.counter_window_phases.get();
        int        kept    = 0;

        for (std::size_t i = 0; i < k_phase_ids.size(); ++i) {
            if (g_phase_imm[i] == 0) {
                continue;
            }
            // When the feature is off, always restore the original id (vanilla).
            const bool          allow = !enabled || ((mask & phase_bit(i)) != 0);
            const std::uint32_t value =
                allow ? k_phase_ids[i] : games::ac::rogue::k_counter_phase_disabled;
            if (!mem::write<std::uint32_t>(g_phase_imm[i], value)) {
                log::get()->error("CounterWindow: failed to write phase 0x{:X} at 0x{:X}",
                                  k_phase_ids[i],
                                  g_phase_imm[i]);
                continue;
            }
            if (allow) {
                ++kept;
            }
        }
        log::get()->info("CounterWindow: {} ({} of 4 phases counterable, mask=0x{:X})",
                         enabled ? "enabled" : "disabled",
                         enabled ? kept : 4,
                         enabled ? mask : 0xF);
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        g_phase_imm[0] = addrs.counter_phase_1f6.value();
        g_phase_imm[1] = addrs.counter_phase_1f7.value();
        g_phase_imm[2] = addrs.counter_phase_1f8.value();
        g_phase_imm[3] = addrs.counter_phase_1f9.value();
        log::get()->trace("CounterWindow: imm 1F6=0x{:X} 1F7=0x{:X} 1F8=0x{:X} 1F9=0x{:X}",
                          g_phase_imm[0],
                          g_phase_imm[1],
                          g_phase_imm[2],
                          g_phase_imm[3]);
        on_reload(games::ac::rogue::registry().config<Tag>());
        return true;
    }
} // namespace hooks
