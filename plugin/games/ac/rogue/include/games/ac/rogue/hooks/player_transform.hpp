#pragma once

#include <cstdint>

#include <array>
#include <charconv>
#include <optional>
#include <string>
#include <string_view>
#include <tuple>

#include <mini/ini.h>

#include "core/hooks/registry/config_base.hpp"
#include "core/hooks/registry/dep_list.hpp"
#include "core/hooks/registry/hook_traits.hpp"
#include "core/hooks/registry/ini_field.hpp"

#include "games/ac/rogue/game_data.hpp"

namespace games::ac::rogue {
    // AccCoop M2/M3: read the live camera (player) world transform each frame and
    // publish it over UDP (see acc-coop/RE-NOTES.md section 6).
    struct PlayerTransformHook {};
} // namespace games::ac::rogue

namespace hooks {
    // The framework ships parsers for float and bool only; ints here.
    struct coop_int_parser {
        [[maybe_unused]] static auto operator()(const std::string &s) -> int {
            int val = 0;
            const auto *const begin = s.data();
            const auto *const end   = s.data() + s.size();
            std::from_chars(begin, end, val);
            return val;
        }
    };

    template<>
    struct HookTraits<games::ac::rogue::PlayerTransformHook> {
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "PlayerTransform";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        // Deterministic addressing: resolved from the module base + fixed RVAs for the
        // pinned ACC.exe build, so a flaky pattern scan cannot skip this hook.
        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            // Log the sampled local transform at this rate (Hz). 0 = silent.
            ini_field<float> log_hz {"PlayerTransform", "LogHz", 2.0F};

            // CoopNet transport. Off by default so the plugin never opens a socket
            // unless the user asks. RemoteIp1..4 is the peer's Radmin/LAN address
            // (ini_field cannot hold a string, so the address is four octets).
            ini_field<bool> coop_enabled {"Coop", "Enabled", false};
            ini_field<int, coop_int_parser> remote_ip1 {"Coop", "RemoteIp1", 127};
            ini_field<int, coop_int_parser> remote_ip2 {"Coop", "RemoteIp2", 0};
            ini_field<int, coop_int_parser> remote_ip3 {"Coop", "RemoteIp3", 0};
            ini_field<int, coop_int_parser> remote_ip4 {"Coop", "RemoteIp4", 1};
            ini_field<int, coop_int_parser> remote_port {"Coop", "RemotePort", 27700};
            ini_field<int, coop_int_parser> local_port {"Coop", "LocalPort", 27700};
            ini_field<int, coop_int_parser> client_id {"Coop", "ClientId", 1};
            ini_field<float> send_hz {"Coop", "SendHz", 20.0F};

            static constexpr std::size_t field_count = 10;
            static constexpr auto        field_ptrs  = std::tuple {
                &Config::log_hz,
                &Config::coop_enabled,
                &Config::remote_ip1,
                &Config::remote_ip2,
                &Config::remote_ip3,
                &Config::remote_ip4,
                &Config::remote_port,
                &Config::local_port,
                &Config::client_id,
                &Config::send_hz,
            };
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
