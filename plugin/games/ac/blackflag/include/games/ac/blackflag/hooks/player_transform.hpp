#pragma once

#include <array>
#include <charconv>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <tuple>
#include <utility>

#include <mini/ini.h>

#include "core/hooks/registry/config_base.hpp"
#include "core/hooks/registry/dep_list.hpp"
#include "core/hooks/registry/hook_traits.hpp"
#include "core/hooks/registry/ini_field.hpp"

#include "games/ac/blackflag/game_data.hpp"

namespace games::ac::blackflag {
    // BFCoop B1: read the live camera/player world transform each frame (from the camera
    // manager ring) and publish it over UDP. Mirrors ACCoop's Rogue hook, 32-bit.
    struct PlayerTransformHook {};
} // namespace games::ac::blackflag

namespace hooks {
    // The framework ships parsers for float and bool only; ints here.
    struct bf_coop_int_parser {
        [[maybe_unused]] static auto operator()(const std::string &s) -> int {
            int val = 0;
            const auto *const begin = s.data();
            const auto *const end   = s.data() + s.size();
            std::from_chars(begin, end, val);
            return val;
        }
    };

    // ini_field wraps the value in std::atomic, which rejects std::string; the player
    // name therefore gets its own load_from-compatible field. Touched on the game
    // thread only (on_reload + the camera hook), so no atomic is needed.
    struct bf_coop_string_field {
        std::string_view section;
        std::string_view key;
        std::string      default_value;
        std::string      value;

        bf_coop_string_field(std::string_view sec, std::string_view k, std::string def)
            : section(sec),
              key(k),
              default_value(std::move(def)),
              value(default_value) {}

        auto get() const -> std::string { return value; }
        void store(std::string val) { value = std::move(val); }

        void load_from(mINI::INIStructure &ini) {
            const std::string s(section);
            const std::string k(key);
            const auto        sec = ini.get(s);
            // Missing or empty -> default, matching ini_field's delete-means-default rule.
            value = (sec.has(k) && !sec.get(k).empty()) ? sec.get(k) : default_value;
        }
    };

    template<>
    struct HookTraits<games::ac::blackflag::PlayerTransformHook> {
        using Addrs        = games::game_data<games::ac::BlackFlag>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        static constexpr std::string_view name = "PlayerTransform";

        using hard_deps = dep_list<>;
        using soft_deps = dep_list<>;

        // Deterministic addressing: module base + fixed RVAs for the pinned build.
        static constexpr auto required_patterns = std::array<PatternField, 0> {};
        static constexpr auto optional_patterns = std::array<PatternField, 0> {};

        struct Config : config_base<Config> {
            ini_field<float> log_hz {"PlayerTransform", "LogHz", 2.0F};

            ini_field<bool> coop_enabled {"Coop", "Enabled", false};
            ini_field<int, bf_coop_int_parser> remote_ip1 {"Coop", "RemoteIp1", 127};
            ini_field<int, bf_coop_int_parser> remote_ip2 {"Coop", "RemoteIp2", 0};
            ini_field<int, bf_coop_int_parser> remote_ip3 {"Coop", "RemoteIp3", 0};
            ini_field<int, bf_coop_int_parser> remote_ip4 {"Coop", "RemoteIp4", 1};
            ini_field<int, bf_coop_int_parser> remote_port {"Coop", "RemotePort", 27700};
            ini_field<int, bf_coop_int_parser> local_port {"Coop", "LocalPort", 27700};
            ini_field<int, bf_coop_int_parser> client_id {"Coop", "ClientId", 1};
            bf_coop_string_field player_name {"Coop", "PlayerName", "player"};
            ini_field<bool> is_host {"Coop", "IsHost", false};
            ini_field<float> send_hz {"Coop", "SendHz", 20.0F};
            ini_field<bool>  body_drive {"Coop", "BodyDrive", true};
            ini_field<int, bf_coop_int_parser> body_min_children {"Coop", "BodyMinChildren", 16};
            ini_field<int, bf_coop_int_parser> body_max_dist {"Coop", "BodyMaxDist", 200};
            ini_field<bool> clone_test {"Coop", "CloneTest", false};
            ini_field<bool> clone_live {"Coop", "CloneLive", false}; // dev one-shot: clone the player's character object (visibility test)
            ini_field<bool> spawn_test {"Coop", "SpawnTest", false}; // dev one-shot: call the streamer spawn (crowd template hash)
            ini_field<bool> spawn_watch {"Coop", "SpawnWatch", false}; // dev: capture streamer spawn template hashes (read-only hook)
            bf_coop_string_field spawn_hash {"Coop", "SpawnHash", "47CD5ECC"}; // hex template hash for SpawnTest
            ini_field<bool> cull_watch {"Coop", "CullWatch", false}; // P1 oracle: sample the ghost body's lifecycle fields
            ini_field<bool> anim_drive {"Coop", "AnimDrive", false}; // P3: replay the peer's action state on the ghost
            ini_field<bool> anim_probe {"Coop", "AnimProbe", false}; // read-only: map the ghost body's real animation objects
            ini_field<bool>  marker_enabled {"Coop", "MarkerEnabled", false}; // P2: partner marker overlay
            ini_field<float> marker_fov {"Coop", "MarkerFov", 55.0F};         // vertical FOV for the projection
            ini_field<float> marker_size {"Coop", "MarkerSize", 16.0F};       // marker half-size, px
            ini_field<bool>  marker_player {"Coop", "MarkerPlayer", true};    // draw the calibration marker
            ini_field<bool>  api_move {"Coop", "ApiMove", false};             // P1 fix: move via the engine's transform setter
            ini_field<bool>  probe_damage {"Coop", "ProbeDamage", false};     // dev: log health-setter calls (damage-path hunt)
            ini_field<bool>  combat_sync {"Coop", "CombatSync", false};       // P4: NPC health watch + damage/kill apply
            ini_field<bool>  combat_kill_test {"Coop", "CombatKillTest", false}; // dev: one-shot kill via the engine setter
            ini_field<bool>  nav_test {"Coop", "NavTest", false}; // dev one-shot: navigate a nearby NPC via CSrvNavigation::NavigateTo
            ini_field<bool>  nav_watch {"Coop", "NavWatch", false}; // dev: capture real NavigateTo traffic (read-only hooks)
            ini_field<bool>  adopt_test {"Coop", "AdoptTest", false}; // v19 dev one-shot: pre-place shells at the previous region's keys
            ini_field<bool>  act_scan {"PlayerTransform", "ActScan", false}; // v19.2: allow the act-ctl rescan (~3 s freeze per pass; off)
            bf_coop_string_field adopt_only {"Coop", "AdoptOnly", ""}; // v19.3: plant ONLY this key ("LLLLLLLL:HHHHHHHH")
            bf_coop_string_field adopt_skip {"Coop", "AdoptSkip", ""}; // v19.3: never plant this key ("LLLLLLLL:HHHHHHHH")
            ini_field<int, bf_coop_int_parser> adopt_max {"Coop", "AdoptMax", 0}; // v19.3: cap planted count (0 = default)

            static constexpr std::size_t field_count = 38;
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
                &Config::player_name,
                &Config::is_host,
                &Config::send_hz,
                &Config::body_drive,
                &Config::body_min_children,
                &Config::body_max_dist,
                &Config::clone_test,
                &Config::clone_live,
                &Config::spawn_test,
                &Config::spawn_watch,
                &Config::spawn_hash,
                &Config::cull_watch,
                &Config::anim_drive,
                &Config::anim_probe,
                &Config::marker_enabled,
                &Config::marker_fov,
                &Config::marker_size,
                &Config::marker_player,
                &Config::api_move,
                &Config::probe_damage,
                &Config::combat_sync,
                &Config::combat_kill_test,
                &Config::nav_test,
                &Config::nav_watch,
                &Config::adopt_test,
                &Config::act_scan,
                &Config::adopt_only,
                &Config::adopt_skip,
                &Config::adopt_max,
            };
        };

        static void on_reload(const Config &cfg);
        static auto install(const Addrs &addrs) -> bool;
    };
} // namespace hooks
