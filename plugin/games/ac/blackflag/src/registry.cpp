#include "games/ac/blackflag/registry.hpp"

namespace games::ac::blackflag {
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
    auto registry() -> BlackFlagRegistry & {
        static BlackFlagRegistry instance;
        return instance;
    }
#pragma clang diagnostic pop
} // namespace games::ac::blackflag
