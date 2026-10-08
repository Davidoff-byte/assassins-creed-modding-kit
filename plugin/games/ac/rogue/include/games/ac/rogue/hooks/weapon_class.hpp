#pragma once

#include <cstddef>
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
#include "games/ac/rogue/hooks/game_state.hpp"

namespace games::ac::rogue {
    struct WeaponClassHook {};

    // Fight weapon types applied by FUN_141807200 (from FUN_1414a6270).
    inline constexpr int k_fight_type_sword      = 1;
    inline constexpr int k_fight_type_dual_wield = 7;

    // Instruction inside FUN_1420f3d20 (`mov ebp, edx`) where the type is read.
    inline constexpr std::ptrdiff_t k_apply_type_mov_ebp_edx = 0x0B;
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::WeaponClassHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "OneHandedSword";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 2> {
            &Addrs::set_fight_type,
            &Addrs::set_weapon_pose,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 1> {
            &Addrs::apply_weapon_type,
        };

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> one_handed_sword {"Gameplay",
                                                                    "OneHandedSword",
                                                                    true};
            // Hide the off-hand (secondary) weapon mesh so the dual-wield set reads
            // as a single sword. Applies the "unarmed" set to the off-hand slot.
            ini_field<bool, default_parser<bool>> hide_offhand {"Gameplay",
                                                                "HideOffHand",
                                                                true};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::one_handed_sword,
                                                                   &Config::hide_offhand};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
