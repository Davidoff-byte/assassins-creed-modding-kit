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
    // AIAggression: extreme enemy aggression.
    //
    // The fight-action availability gate FUN_14183b970(actor, action) decides
    // whether a fight action may start (returns 2 or 3 = allowed). The enemy AI is
    // throttled through it. This hook detours that function and returns "allowed"
    // for NPC actors only, so enemies commit to attacks/blocks far more often while
    // the player's own availability checks stay untouched.
    struct AIAggressionHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::AIAggressionHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "AIAggression";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 1> {
            &Addrs::ai_action_avail,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> extreme_aggression {"Gameplay",
                                                                      "ExtremeAggression",
                                                                      true};
            ini_field<bool, default_parser<bool>> trace {"Gameplay", "ExtremeAggressionTrace", false};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::extreme_aggression,
                                                                   &Config::trace};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
