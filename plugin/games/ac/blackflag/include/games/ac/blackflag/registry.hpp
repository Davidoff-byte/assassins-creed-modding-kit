#pragma once

#include "core/hooks/registry/registry.hpp"

#include "games/ac/blackflag/hooks/cam_probe.hpp"
#include "games/ac/blackflag/hooks/player_transform.hpp"

namespace games::ac::blackflag {
    using AllHooks = hooks::hook_list<PlayerTransformHook, CamProbeHook>;

    using BlackFlagRegistry = hooks::Registry<AllHooks>;

    auto registry() -> BlackFlagRegistry &;
} // namespace games::ac::blackflag
