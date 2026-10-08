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
    // KnifeProbe: diagnostic. Logs the local player's current tool object — the
    // structure that holds tool ids / counts, including the throwing knife. Hooks
    // the `test rcx,rcx` inside FUN_141e6bea0 where rcx is that object.
    struct KnifeProbeHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::KnifeProbeHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "KnifeProbe";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 1> {
            &Addrs::knife_entity,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 1> {
            &Addrs::knife_probe,
        };

        struct Config : config_base<Config> {
            ini_field<bool, default_parser<bool>> enabled {"Gameplay", "KnifeProbe", true};

            static constexpr std::size_t field_count = 1;
            static constexpr auto        field_ptrs  = std::tuple {&Config::enabled};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
