#pragma once

#include <array>
#include <cstdint>
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
    // AccCoop A4 self-test: validate the engine's set-world-transform path on the PLAYER.
    // Discovery logs the player's +0x20 component and the interface-0xD vtable; with
    // DoTransform=true it calls the engine's matrix builder + set-transform to nudge Shay.
    struct SetTransformHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::SetTransformHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "SetTransform";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool>  enabled      {"SetTransform", "Enabled", false};
            ini_field<bool>  do_transform {"SetTransform", "DoTransform", false};
            ini_field<float> offset_x     {"SetTransform", "OffsetX", 3.0F};
            ini_field<float> delay_sec    {"SetTransform", "DelaySec", 8.0F};
            ini_field<float> log_hz       {"SetTransform", "LogHz", 1.0F};

            static constexpr std::size_t field_count = 5;
            static constexpr auto        field_ptrs  = std::tuple {&Config::enabled,
                                                                   &Config::do_transform,
                                                                   &Config::offset_x,
                                                                   &Config::delay_sec,
                                                                   &Config::log_hz};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
