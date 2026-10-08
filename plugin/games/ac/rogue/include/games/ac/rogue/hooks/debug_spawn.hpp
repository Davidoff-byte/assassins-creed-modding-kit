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
    // AccCoop A4 Route C probe: call the engine's own debug-cheat spawn
    // ("Spawn Follow Dude" = FUN_141e91d50, RVA 0x1e91d50) to prove a second
    // engine-managed character can be created from a hook. Default OFF.
    struct DebugSpawnHook {};
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::DebugSpawnHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "DebugSpawn";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<bool>  enabled {"DebugSpawn", "Enabled", false};
            // -1 = call all four spawn handlers once (test); 0=Follow, 1=RedBall, 2=Still, 3=Fight.
            ini_field<float> kind    {"DebugSpawn", "Kind", -1.0F};
            ini_field<float> log_hz  {"DebugSpawn", "LogHz", 1.0F};

            static constexpr std::size_t field_count = 3;
            static constexpr auto        field_ptrs  = std::tuple {&Config::enabled, &Config::kind, &Config::log_hz};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
