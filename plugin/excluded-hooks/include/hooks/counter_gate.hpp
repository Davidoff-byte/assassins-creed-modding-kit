#pragma once

#include <cstdint>

#include <array>
#include <optional>
#include <string_view>
#include <tuple>

#include "core/hooks/registry/config_base.hpp"
#include "core/hooks/registry/dep_list.hpp"
#include "core/hooks/registry/hook_traits.hpp"
#include "core/hooks/registry/ini_field.hpp"
#include "core/hooks/registry/parsers.hpp"

#include "games/ac/rogue/game_data.hpp"
#include "games/ac/rogue/hooks/counter_probe.hpp" // probe_int_parser

namespace games::ac::rogue {
    // CounterGate: turn the broad counter window into a short one.
    //
    // When an enemy attacks, the fight manager opens the counter window
    // (fight-manager +0x1138 = 1) for the whole attack (~1.5-2.7 s), and +0x1008
    // gates whether a counter is accepted (1 = block, 0 = counter; forcing 1 makes
    // every tap a block — verified live). This hook keeps +0x1008 = 1 for
    // CounterGateDelayMs after the window opens, then releases it, so only a late
    // press actually counters.
    struct CounterGateHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::CounterGateHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CounterGate";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 1> {
            &Addrs::counter_can,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> counter_gate {"Gameplay", "CounterGate", false};
            // How long after the window opens the counter stays refused (block).
            ini_field<int, games::ac::rogue::probe_int_parser> counter_gate_delay_ms {
                "Gameplay",
                "CounterGateDelayMs",
                1200};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::counter_gate,
                                                                  &Config::counter_gate_delay_ms};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
