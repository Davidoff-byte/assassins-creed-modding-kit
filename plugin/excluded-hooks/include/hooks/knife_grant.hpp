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
    // KnifeGrant: keep Shay stocked with throwing knives.
    //
    // The HUD/ammo quantity accessors FUN_1410f7460(id, actor) (current) and
    // FUN_1410f73d0(actor, id) (max) are detoured; for the configured item id they
    // report a large stock, so the throwing-knife tool is always selectable/usable.
    struct KnifeGrantHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::KnifeGrantHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "KnifeGrant";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 2> {
            &Addrs::knife_qty,
            &Addrs::knife_qty_max,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> enabled {"Gameplay", "ThrowingKnives", true};
            // Item id the throwing knife uses in the ammo accessor (0x1b = the
            // Action_ThrowKnife id; tune if the log shows a different one).
            ini_field<int, games::ac::rogue::probe_int_parser> item_id {"Gameplay",
                                                                        "ThrowingKnifeItemId",
                                                                        0x1b};
            // Diagnostic: force the count for EVERY queried id (to find which id the
            // throwing knife is). Turn off once the id is known.
            ini_field<bool, default_parser<bool>> force_all {"Gameplay", "ThrowingKnifeAll", false};
            ini_field<int, games::ac::rogue::probe_int_parser> force_value {"Gameplay",
                                                                            "ThrowingKnifeCount",
                                                                            99};
            ini_field<bool, default_parser<bool>> trace {"Gameplay", "ThrowingKnivesTrace", true};

            static constexpr std::size_t field_count = 5;
            static constexpr auto        field_ptrs  = std::tuple {&Config::enabled,
                                                                   &Config::item_id,
                                                                   &Config::force_all,
                                                                   &Config::force_value,
                                                                   &Config::trace};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
