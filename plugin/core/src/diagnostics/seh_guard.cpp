#include "core/diagnostics/seh_guard.hpp"

#include <string_view>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/diagnostics/crash_report.hpp"
#include "core/diagnostics/hook_context.hpp"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wlanguage-extension-token"

namespace {
    // Kept free of any object requiring unwinding so MSVC accepts __try here.
    auto install_guarded(bool (*fn)(const void *), const void *addrs) -> int {
        __try {
            return fn(addrs) ? 1 : 0;
        } __except (diagnostics::install_fault_filter(GetExceptionInformation(),
                                                      diagnostics::current_hook_name())) {
            return -1;
        }
    }

    auto call_guarded(void (*fn)(void *), void *ctx, std::string_view name) -> int {
        __try {
            fn(ctx);
            return 1;
        } __except (diagnostics::callback_fault_filter(GetExceptionInformation(), name)) {
            return 0;
        }
    }
} // namespace

namespace diagnostics {
    auto guarded_install(bool (*fn)(const void *), const void *addrs, std::string_view hook_name)
        -> bool {
        set_current_hook_name(hook_name);
        const int result = install_guarded(fn, addrs);
        if (result < 0) {
            log::get()->critical("Hook installation crashed — hook skipped");
            return false;
        }
        return result == 1;
    }

    auto guarded_call(void (*fn)(void *), void *ctx, std::string_view name) -> bool {
        return call_guarded(fn, ctx, name) == 1;
    }
} // namespace diagnostics

#pragma clang diagnostic pop
