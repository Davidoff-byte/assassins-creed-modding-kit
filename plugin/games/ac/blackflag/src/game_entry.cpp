#include <stop_token>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/diagnostics/crash_logger.hpp"
#include "core/diagnostics/crash_report.hpp"

#include "games/ac/blackflag/registry.hpp"
#include "games/game_init.hpp"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wlanguage-extension-token"

namespace {
    struct InitCall {
        HMODULE                 module;
        const std::stop_token  *stop;
    };

    void run_game_init(void *ctx) {
        auto *c = static_cast<InitCall *>(ctx);
        game_init_impl<games::ac::BlackFlag>(c->module, *c->stop, games::ac::blackflag::registry());
    }

    // Function-pointer indirection keeps MSVC from seeing the unwinding call and
    // rejecting __try with C2712.
    auto call_init_guarded(void (*fn)(void *), void *ctx) -> int {
        __try {
            fn(ctx);
            return 1;
        } __except (diagnostics::install_fault_filter(GetExceptionInformation(), "game_init")) {
            return 0;
        }
    }
} // namespace

void game_init(HMODULE hModule, const std::stop_token &stop) {
    InitCall call {hModule, &stop};
    if (call_init_guarded(&run_game_init, &call) == 0) {
        log::get()->critical("Fatal exception during init — plugin disabled");
    }
}

#pragma clang diagnostic pop
