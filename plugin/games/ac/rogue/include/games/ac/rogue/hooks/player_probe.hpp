#pragma once

#include <cstdint>

#include <array>
#include <optional>
#include <string_view>
#include <tuple>

#include <mini/ini.h>

#include "core/hooks/registry/config_base.hpp"
#include "core/hooks/registry/dep_list.hpp"
#include "core/hooks/registry/hook_traits.hpp"
#include "core/hooks/registry/ini_field.hpp"

#include "games/ac/rogue/game_data.hpp"

namespace games::ac::rogue {
    // AccCoop A4 discovery: enumerate live actors and locate the actor transform offset
    // relative to the known player body position. Read-only; separate hook so a fault can't
    // take down PlayerTransform.
    struct PlayerProbeHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::PlayerProbeHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "PlayerProbe";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<float> log_hz {"PlayerProbe", "LogHz", 1.0F};

            static constexpr std::size_t field_count = 1;
            static constexpr auto        field_ptrs  = std::tuple {&Config::log_hz};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
