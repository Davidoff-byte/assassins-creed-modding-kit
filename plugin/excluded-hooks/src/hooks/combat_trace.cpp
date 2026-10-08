#include "games/ac/rogue/hooks/combat_trace.hpp"

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <string_view>
#include <utility>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag          = games::ac::rogue::CombatTraceHook;
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        constexpr std::size_t k_count = 15;

        constexpr std::array<std::string_view, k_count> k_names = {
            "PAR",  "CFA",  "GRB", "WSET", "POSE_A", "POSE_B", "FA1", "FA2",
            "FA3",  "FA4",  "FA5", "FA6",  "FA7",    "FA8",    "FA9",
        };

        constexpr std::array<PatternField, k_count> k_fields = {
            &Addrs::combat_parry,         &Addrs::combat_counter_fail, &Addrs::combat_grab_countered,
            &Addrs::combat_weapon_setup,  &Addrs::combat_pose_a,       &Addrs::combat_pose_b,
            &Addrs::combat_fa1,           &Addrs::combat_fa2,          &Addrs::combat_fa3,
            &Addrs::combat_fa4,           &Addrs::combat_fa5,          &Addrs::combat_fa6,
            &Addrs::combat_fa7,           &Addrs::combat_fa8,          &Addrs::combat_fa9,
        };

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::array<mem::MidHook, k_count>               g_hooks;
        std::array<std::atomic<std::uint64_t>, k_count> g_counts {};
#pragma clang diagnostic pop

        auto now_ms() -> std::uint64_t {
            using namespace std::chrono;
            return static_cast<std::uint64_t>(
                duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
        }

        template<std::size_t I>
        struct TraceFn {
            [[maybe_unused]] static constexpr std::string_view name = "CombatTrace";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                if (!games::ac::rogue::registry().config<Tag>().combat_trace.get()) {
                    return;
                }
                const auto n = g_counts[I].fetch_add(1, std::memory_order_relaxed);
                if (n > 40000) {
                    return;
                }
                log::get()->info("CT {} #{} t={} rcx={:X} rdx={:X} r8={:X} r9={:X}",
                                 k_names[I], n, now_ms(), regs.rcx, regs.rdx, regs.r8, regs.r9);
            }
        };

        template<std::size_t I>
        void install_one(const Addrs &addrs) {
            const auto addr = (addrs.*k_fields[I]).value_or(0);
            if (addr == 0) {
                log::get()->warn("CombatTrace: {} pattern missing", k_names[I]);
                return;
            }
            if (auto h = mem::make_hook<TraceFn<I>>(addr)) {
                g_hooks[I] = std::move(*h);
            } else {
                log::get()->error("CombatTrace: {} hook failed: {}", k_names[I], h.error());
            }
        }

        template<std::size_t... Is>
        void install_all(const Addrs &addrs, std::index_sequence<Is...> /*unused*/) {
            (install_one<Is>(addrs), ...);
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        log::get()->info("CombatTrace: {}", cfg.combat_trace.get() ? "enabled" : "disabled");
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        install_all(addrs, std::make_index_sequence<k_count> {});
        on_reload(games::ac::rogue::registry().config<Tag>());
        return true;
    }
} // namespace hooks
