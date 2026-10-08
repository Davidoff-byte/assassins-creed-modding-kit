#include "games/ac/rogue/hooks/counter_gate.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::CounterGateHook;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        mem::MidHook               g_hook;
        std::atomic<int>           g_delay_ms {1200};
        std::atomic<std::uint64_t> g_onset_ms {0};
        std::atomic<bool>          g_window_open {false};
#pragma clang diagnostic pop

        auto now_ms() -> std::uint64_t {
            using namespace std::chrono;
            return static_cast<std::uint64_t>(
                duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
        }

        auto u64_at(std::uintptr_t base) -> std::uint64_t {
            return *reinterpret_cast<const std::uint64_t *>(base);
        }
        auto u8_at(std::uintptr_t base) -> std::uint8_t {
            return *reinterpret_cast<const std::uint8_t *>(base);
        }

        // Runs on the per-frame counter-availability predicate (FUN_1417f6fa0). rcx is
        // the fight-context wrapper: obj = *(rcx+0x18), fight manager = *(obj+0xf8).
        struct GateFn {
            [[maybe_unused]] static constexpr std::string_view name = "CounterGate";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                if (!games::ac::rogue::registry().enabled<Tag>() ||
                    !games::ac::rogue::registry().config<Tag>().counter_gate.get()) {
                    return;
                }
                const auto player = regs.rcx;
                const auto obj    = u64_at(player + 0x18);
                if (obj == 0) {
                    return;
                }
                const auto fm = u64_at(obj + 0xf8);
                if (fm == 0) {
                    return;
                }
                const auto now = now_ms();
                if (u8_at(fm + 0x1138) != 0) {
                    // Player's counter pose (created by a successful press). Not our domain.
                    if (g_window_open.exchange(false, std::memory_order_relaxed)) {
                        log::get()->info("CounterGate: pose END t={} len={}ms",
                                         now,
                                         now - g_onset_ms.load(std::memory_order_relaxed));
                    }
                    return;
                }
                // fm1138 == 0: this is the state the counter input is validated in. Gate it:
                // refuse the counter for CounterGateDelayMs after the pose ends, then allow.
                if (!g_window_open.load(std::memory_order_relaxed)) {
                    g_window_open.store(true, std::memory_order_relaxed);
                    g_onset_ms.store(now, std::memory_order_relaxed);
                    log::get()->info("CounterGate: ready t={} fm={:X}", now, fm);
                }
                const auto elapsed = now - g_onset_ms.load(std::memory_order_relaxed);
                const bool early =
                    elapsed < static_cast<std::uint64_t>(g_delay_ms.load(std::memory_order_relaxed));
                *reinterpret_cast<volatile std::uint8_t *>(fm + 0x1008) = early ? 1U : 0U;
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_delay_ms.store(cfg.counter_gate_delay_ms.get(), std::memory_order_relaxed);
        log::get()->info("CounterGate: {} (deny counter for first {} ms of the window)",
                         cfg.counter_gate.get() ? "enabled" : "disabled",
                         cfg.counter_gate_delay_ms.get());
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        const auto addr = addrs.counter_can.value();
        auto       h    = mem::make_hook<GateFn>(addr);
        if (!h) {
            log::get()->error("CounterGate: hook failed: {}", h.error());
            return false;
        }
        g_hook = std::move(*h);
        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("CounterGate: installed");
        return true;
    }
} // namespace hooks
