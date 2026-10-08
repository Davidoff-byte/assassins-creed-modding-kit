#pragma once

#include <atomic>
#include <concepts>
#include <string_view>
#include <type_traits>

#include <Windows.h>

#include <safetyhook/context.hpp>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/diagnostics/crash_report.hpp"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wlanguage-extension-token"

namespace diagnostics {
    template<typename F>
    concept named_functor = requires {
        { F::name } -> std::convertible_to<std::string_view>;
    };

    auto guarded_call(void (*fn)(void *), void *ctx, std::string_view name) -> bool;

    template<typename Functor>
    void guarded_callback(safetyhook::Context &regs) {
        static_assert(std::is_trivially_destructible_v<Functor>,
                      "Functor must be trivially destructible for SEH guard");

        static std::atomic<bool> s_faulted {false};
        if (s_faulted.load(std::memory_order_relaxed)) {
            return;
        }

        auto thunk = +[](void *p) { Functor {}(*static_cast<safetyhook::Context *>(p)); };
        bool ok    = true;
        if constexpr (named_functor<Functor>) {
            ok = guarded_call(thunk, &regs, Functor::name);
        } else {
            ok = guarded_call(thunk, &regs, std::string_view {});
        }
        if (!ok) {
            s_faulted.store(true, std::memory_order_relaxed);
            if constexpr (named_functor<Functor>) {
                log::get(Functor::name)->critical("Hook callback crashed — permanently disabled");
            }
        }
    }

    auto guarded_install(bool (*fn)(const void *), const void *addrs, std::string_view hook_name)
        -> bool;
} // namespace diagnostics

#pragma clang diagnostic pop
