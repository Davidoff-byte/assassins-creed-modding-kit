#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
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
    // CombatTweaks: runtime edits to the live FightSettings counter block.
    //
    // The block is the *held* parry (`TimeButtonHeldForParry`); raising it makes a held
    // press stop becoming a block, so the button only ever attempts a counter.
    // The block lives in heap memory (address changes per launch), so it is found by
    // scanning for the distinctive float run
    //   [MaxWaitTimeForDefenceCounter=0.3, TimeButtonHeldForParry=0.2, TimeCounterInputIsValid=0.2]
    // preceded by [CounterSlowMotionDuration=0.3, Intensity=0.04, AdjustedDuration=0.012,
    // AdjustedDurationShellshocked=0.8].
    struct CombatTweaksHook {};

    inline constexpr std::array<float, 7> k_counter_block_pattern = {
        0.3F,
        0.04F,
        0.012F,
        0.8F,
        0.3F, // MaxWaitTimeForDefenceCounter
        0.2F, // TimeButtonHeldForParry   (index 5)
        0.2F, // TimeCounterInputIsValid  (index 6)
    };
    inline constexpr std::size_t k_idx_time_button_held  = 5;
    inline constexpr std::size_t k_idx_counter_input_val = 6;
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::CombatTweaksHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CombatTweaks";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            // Disable the block: raise TimeButtonHeldForParry so a held press never blocks.
            ini_field<bool, default_parser<bool>> no_block {"Gameplay", "NoBlock", false};
            ini_field<float, default_parser<float>> block_hold_seconds {"Gameplay",
                                                                        "BlockHoldSeconds",
                                                                        999.0F};
            // Optional: rewrite TimeCounterInputIsValid (input-buffer window). <0 = leave alone.
            ini_field<float, default_parser<float>> counter_input_valid {"Gameplay",
                                                                         "CounterInputValid",
                                                                         -1.0F};
            // AI aggression: multiply the fight action/decision delays for the active pacing
            // tiers. 1.0 = vanilla; lower = faster/more aggressive (e.g. 0.35).
            ini_field<float, default_parser<float>> ai_aggression {"Gameplay", "AIAggression", 1.0F};
            // Make the kill-streak delays huge so chained kills don't carry on.
            ini_field<bool, default_parser<bool>> no_chain_kills {"Gameplay", "NoChainKills", false};

            static constexpr std::size_t field_count = 5;
            static constexpr auto        field_ptrs  = std::tuple {&Config::no_block,
                                                                  &Config::block_hold_seconds,
                                                                  &Config::counter_input_valid,
                                                                  &Config::ai_aggression,
                                                                  &Config::no_chain_kills};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
