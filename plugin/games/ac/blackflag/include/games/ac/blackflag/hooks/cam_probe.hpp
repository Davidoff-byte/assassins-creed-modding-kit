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

#include "games/ac/blackflag/game_data.hpp"

namespace games::ac::blackflag {
    // BFCoop B3 discovery (read-only): dump the camera-manager pointer graph and find
    // the object whose transform sits at the camera position (the player character).
    struct CamProbeHook {};
} // namespace games::ac::blackflag

namespace hooks {
    template<>
    struct HookTraits<games::ac::blackflag::CamProbeHook> {
        using Addrs        = games::game_data<games::ac::BlackFlag>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CamProbe";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool>  enabled {"CamProbe", "Enabled", true};
            ini_field<float> log_hz  {"CamProbe", "LogHz", 0.5F};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::enabled, &Config::log_hz};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
