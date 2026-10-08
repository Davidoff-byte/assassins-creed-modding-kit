#include "games/ac/rogue/hooks/knife_grant.hpp"

#include <atomic>
#include <cstdint>

#include <safetyhook/inline_hook.hpp>

#include "core/logger.hpp" // IWYU pragma: keep

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::KnifeGrantHook;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        safetyhook::InlineHook      g_qty_hook;
        safetyhook::InlineHook      g_max_hook;
        constexpr int               k_max_seen = 96;
        std::atomic<int>            g_seen_count {0};
        std::array<std::atomic<std::uint64_t>, k_max_seen> g_seen {};
#pragma clang diagnostic pop

        void note_once(std::int32_t id, std::int32_t value) {
            const std::uint64_t packed =
                (static_cast<std::uint64_t>(static_cast<std::uint32_t>(id)) << 32) |
                static_cast<std::uint32_t>(value);
            int n = g_seen_count.load(std::memory_order_acquire);
            for (int i = 0; i < n && i < k_max_seen; ++i) {
                if (g_seen[static_cast<std::size_t>(i)].load(std::memory_order_relaxed) == packed) {
                    return;
                }
            }
            if (n >= k_max_seen) {
                return;
            }
            if (g_seen_count.compare_exchange_strong(n, n + 1, std::memory_order_acq_rel)) {
                g_seen[static_cast<std::size_t>(n)].store(packed, std::memory_order_relaxed);
                log::get()->info("KnifeGrant: id=0x{:X} qty={}", static_cast<std::uint32_t>(id), value);
            }
        }

        // FUN_1410f7460(id, actor) -> current quantity
        auto detour_qty(int id, void *actor) -> std::int64_t {
            const auto orig = g_qty_hook.call<std::int64_t>(id, actor);
            const auto &cfg = games::ac::rogue::registry().config<Tag>();
            const bool  hit =
                cfg.enabled.get() && (cfg.force_all.get() || id == cfg.item_id.get());
            const auto ret = hit ? static_cast<std::int64_t>(cfg.force_value.get()) : orig;
            if (cfg.trace.get() && (orig != 0 || hit)) {
                note_once(id, static_cast<std::int32_t>(ret));
            }
            return ret;
        }

        // FUN_1410f73d0(actor, id) -> max quantity
        auto detour_qty_max(void *actor, int id) -> std::int64_t {
            const auto orig = g_max_hook.call<std::int64_t>(actor, id);
            const auto &cfg = games::ac::rogue::registry().config<Tag>();
            if (cfg.enabled.get() && (cfg.force_all.get() || id == cfg.item_id.get())) {
                return cfg.force_value.get();
            }
            return orig;
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        log::get()->info("KnifeGrant: enabled={} item_id=0x{:X} all={} count={} trace={}",
                         cfg.enabled.get() ? "on" : "off",
                         static_cast<unsigned>(cfg.item_id.get()),
                         cfg.force_all.get() ? "on" : "off",
                         cfg.force_value.get(),
                         cfg.trace.get() ? "on" : "off");
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        const auto qty_addr = addrs.knife_qty.value();
        const auto max_addr = addrs.knife_qty_max.value();
        auto       hq       = safetyhook::InlineHook::create(reinterpret_cast<void *>(qty_addr),
                                                       reinterpret_cast<void *>(&detour_qty));
        if (!hq) {
            log::get()->error("KnifeGrant: qty hook failed");
            return false;
        }
        g_qty_hook = std::move(*hq);
        auto hm    = safetyhook::InlineHook::create(reinterpret_cast<void *>(max_addr),
                                                 reinterpret_cast<void *>(&detour_qty_max));
        if (!hm) {
            log::get()->error("KnifeGrant: max hook failed");
            return false;
        }
        g_max_hook = std::move(*hm);
        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("KnifeGrant: installed (qty=0x{:X}, max=0x{:X})", qty_addr, max_addr);
        return true;
    }
} // namespace hooks
