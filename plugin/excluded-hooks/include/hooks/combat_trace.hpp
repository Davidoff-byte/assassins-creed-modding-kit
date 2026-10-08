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

namespace games::ac::rogue {
    // Read-only combat trace: logs entry calls to a set of combat functions. Off by default.
    struct CombatTraceHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::CombatTraceHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CombatTrace";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 1> {
            &Addrs::combat_parry,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 14> {
            &Addrs::combat_counter_fail,    &Addrs::combat_grab_countered,
            &Addrs::combat_weapon_setup,    &Addrs::combat_pose_a,
            &Addrs::combat_pose_b,          &Addrs::combat_fa1,
            &Addrs::combat_fa2,             &Addrs::combat_fa3,
            &Addrs::combat_fa4,             &Addrs::combat_fa5,
            &Addrs::combat_fa6,             &Addrs::combat_fa7,
            &Addrs::combat_fa8,             &Addrs::combat_fa9,
        };

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> combat_trace {"Debug", "CombatTrace", false};

            static constexpr std::size_t field_count = 1;
            static constexpr auto        field_ptrs  = std::tuple {&Config::combat_trace};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
