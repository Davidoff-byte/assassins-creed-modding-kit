#include "games/ac/rogue/hooks/ai_pacing.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>

#include <safetyhook/inline_hook.hpp>

#include "core/logger.hpp" // IWYU pragma: keep

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag     = games::ac::rogue::AIAggressionHook;
        using AvailFn = std::int64_t (*)(void *, void *);

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        safetyhook::InlineHook     g_hook;
        std::atomic<std::uint64_t> g_calls {0};
        std::atomic<std::uint64_t> g_forced {0};
        std::atomic<std::uint64_t> g_players {0};
        std::atomic<std::uint64_t> g_last_log {0};
#pragma clang diagnostic pop

        auto u64_at(std::uintptr_t p) -> std::uintptr_t {
            return *reinterpret_cast<const std::uintptr_t *>(p);
        }

        auto now_ms() -> std::uint64_t {
            using namespace std::chrono;
            return static_cast<std::uint64_t>(
                duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
        }

        // Detour for FUN_14183b970(actor-ctx, action). The actor entity is
        // *(*(*param_1 + 0x1e8) + 8); its object type is the low 3 bits at +0xd0
        // (1 == player, per FUN_14132d7f0). NPC actors get an unconditional "allowed"
        // code; the player falls through to the original.
        auto detour(void *self, void *action) -> std::int64_t {
            const auto calls = g_calls.fetch_add(1, std::memory_order_relaxed) + 1;

            if (games::ac::rogue::registry().enabled<Tag>() &&
                games::ac::rogue::registry().config<Tag>().extreme_aggression.get()) {
                const auto ctx  = reinterpret_cast<std::uintptr_t>(self);
                const auto obj  = ctx != 0 ? u64_at(ctx) : 0;
                const auto slot = obj != 0 ? u64_at(obj + 0x1e8) : 0;
                const auto actor = slot != 0 ? u64_at(slot + 8) : 0;
                const bool is_player =
                    actor != 0 &&
                    ((*reinterpret_cast<const std::uint32_t *>(actor + 0xd0) & 7U) == 1U);
                if (actor != 0) {
                    if (is_player) {
                        g_players.fetch_add(1, std::memory_order_relaxed);
                    } else {
                        g_forced.fetch_add(1, std::memory_order_relaxed);
                    }
                }
                if (actor != 0 && !is_player) {
                    return 3;
                }
            }

            if (games::ac::rogue::registry().config<Tag>().trace.get()) {
                const auto now = now_ms();
                if (now - g_last_log.load(std::memory_order_relaxed) >= 1000) {
                    g_last_log.store(now, std::memory_order_relaxed);
                    log::get()->info("AIAggression: calls={} npcForced={} playerPass={}",
                                     calls,
                                     g_forced.load(std::memory_order_relaxed),
                                     g_players.load(std::memory_order_relaxed));
                }
            }

            return g_hook.call<std::int64_t>(self, action);
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        log::get()->info("AIAggression: extreme_aggression={} trace={}",
                         cfg.extreme_aggression.get() ? "on" : "off",
                         cfg.trace.get() ? "on" : "off");
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        const auto addr = addrs.ai_action_avail.value();
        auto       h    = safetyhook::InlineHook::create(reinterpret_cast<void *>(addr),
                                                  reinterpret_cast<void *>(&detour));
        if (!h) {
            log::get()->error("AIAggression: inline hook failed");
            return false;
        }
        g_hook = std::move(*h);
        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("AIAggression: installed at 0x{:X}", addr);
        return true;
    }
} // namespace hooks
