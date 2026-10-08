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
    // CounterWindow: shrink the player counter window.
    //
    // The parry handler FUN_141845e60 classifies the incoming attack's current action
    // id (0x1F6..0x1F9) and dispatches a parry animation for each match; any other
    // value (e.g. 0x1F5 before the window, or a negative id after it) takes the default
    // no-counter parry. Each classifier is a tiny `cmp [obj+0x230], <id>` function;
    // overwriting its compare immediate with 0xFFFFFFFF drops that id from the
    // counterable set, so only the phases left enabled still trigger a counter kill.
    struct CounterWindowHook {};

    inline constexpr std::uint32_t k_counter_phase_disabled = 0xFFFF'FFFFU;

    // Phase mask: bit0 = 0x1F6, bit1 = 0x1F7, bit2 = 0x1F8, bit3 = 0x1F9.
    // Accepts decimal (15), hex (0xF) or binary (0b1111).
    struct phase_mask_parser {
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
                return 0xF;
            }
            int base = 10;
            if (v.size() > 2 && v[0] == '0' && (v[1] == 'x' || v[1] == 'X')) {
                base = 16;
                v.remove_prefix(2);
            } else if (v.size() > 2 && v[0] == '0' && (v[1] == 'b' || v[1] == 'B')) {
                base = 2;
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
                    return 0xF;
                }
                out = out * base + d;
            }
            return out & 0xF;
        }
    };
} // namespace games::ac::rogue

namespace hooks {
    template<>
    struct HookTraits<games::ac::rogue::CounterWindowHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "CounterWindow";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        static constexpr auto required_patterns = std::array<PatternField, 4> {
            &Addrs::counter_phase_1f6,
            &Addrs::counter_phase_1f7,
            &Addrs::counter_phase_1f8,
            &Addrs::counter_phase_1f9,
        };
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            // Master enable. When off, the original compare immediates are restored.
            ini_field<bool, default_parser<bool>> counter_window {"Gameplay", "CounterWindow", false};
            // Which of the four phases count as a counter. Default 0xF = vanilla (all four).
            ini_field<int, games::ac::rogue::phase_mask_parser> counter_window_phases {
                "Gameplay",
                "CounterWindowPhases",
                0xF};

            static constexpr std::size_t field_count = 2;
            static constexpr auto        field_ptrs  = std::tuple {&Config::counter_window,
                                                                  &Config::counter_window_phases};
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
