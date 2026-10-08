#pragma once

#include <cstdint>

#include <array>
#include <optional>
#include <string_view>

#include "games/game_data.hpp"

namespace games::ac {
    struct BlackFlag {};
} // namespace games::ac

namespace games {
    template<>
    struct game_data<ac::BlackFlag> {
        static constexpr std::string_view name     = "BlackFlag";
        static constexpr std::string_view exe_name = "AC4BFSP.exe";

        static constexpr float k_default_aspect          = 16.0F / 9.0F;
        static constexpr float k_inv_default_aspect      = 9.0F / 16.0F;
        static constexpr float k_inv_base_width          = 1.0F / 1280.0F;
        static constexpr float k_inv_base_height         = 1.0F / 720.0F;
        static constexpr float k_fov_base_zoom           = 0.768F;
        static constexpr float k_triple_screen_threshold = 4.0F;
        static constexpr float k_float_tolerance         = 1e-6F;

        // BFCoop uses fixed RVAs for the pinned AC4BFSP.exe build
        // (MD5 2058342866688F780C8B34526A65BC35), so the scan table is empty.
        struct ResolvedAddresses {
            std::optional<std::uintptr_t> unused_placeholder;
        };

        static constexpr std::array<ScanEntry<ResolvedAddresses>, 0> scan_entries {};
    };

    static_assert(ValidGameData<ac::BlackFlag>);
} // namespace games
