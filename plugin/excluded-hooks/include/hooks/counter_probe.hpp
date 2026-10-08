#pragma once

#include <cstdint>

#include <array>
#include <optional>
#include <string>
#include <string_view>
#include <tuple>

#include "core/hooks/registry/config_base.hpp"
#include "core/hooks/registry/dep_list.hpp"
#include "core/hooks/registry/hook_traits.hpp"
#include "core/hooks/registry/ini_field.hpp"
#include "core/hooks/registry/parsers.hpp"

#include "games/ac/rogue/game_data.hpp"

namespace games::ac::rogue {
    // CounterProbe (diagnostic): logs the counter decision layer and can force the
    // fight-strategy resolvers FUN_1418038d0 / FUN_14183b970 to a constant return
    // (2 = counter, 3 = block) to prove whether they gate the counter kill.
    struct CounterProbeHook {};

    // Minimal decimal/hex int parser (parsers.hpp has no int parser).
    struct probe_int_parser {
        static auto operator()(const std::string &s) -> int {
            std::string_view v(s);
            const auto        is_space = [](char c) -> bool { return c == ' ' || c == '\t'; };
            while (!v.empty() && is_space(v.front())) {
                v.remove_prefix(1);
            }
            while (!v.empty() && is_space(v.back())) {
                v.remove_suffix(1);
            }
            if (v.empty()) {
                return 0;
            }
            int base = 10;
            if (v.size() > 2 && v[0] == '0' && (v[1] == 'x' || v[1] == 'X')) {
                base = 16;
                v.remove_prefix(2);
            }
            int out = 0;
            for (const char c : v) {
                int d = -1;
                if (c >= '0' && c <= '9') {
                    d = c - '0';
                } else if (c >= 'a' && c <= 'f') {
                    d = c - 'a' + 10;
                } else if (c >= 'A' && c <= 'F') {
                    d = c - 'A' + 10;
                }
                if (d < 0 || d >= base) {
                    return 0;
                }
                out = out * base + d;
            }
            return out;
        }
    };
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::CounterProbeHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CounterProbe";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 1> {
            &Addrs::counter_resolver_a,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 3> {
            &Addrs::counter_resolver_b,
            &Addrs::counter_can,
            &Addrs::combat_resolve,
        };

        struct Config : config_base<Config> {
            // Log calls to combat_resolve (FUN_141869550) and counter_can (FUN_1417f6fa0).
            ini_field<bool, default_parser<bool>> counter_probe {"Debug", "CounterProbe", false};
            // Force the resolvers FUN_1418038d0/_b to return: 0 = normal, 2 = counter, 3 = block.
            ini_field<int, games::ac::rogue::probe_int_parser> counter_force {"Debug", "CounterForce", 0};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::counter_probe,
                                                                  &Config::counter_force};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
