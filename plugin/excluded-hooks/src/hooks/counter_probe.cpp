#include "games/ac/rogue/hooks/counter_probe.hpp"

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string_view>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag          = games::ac::rogue::CounterProbeHook;
        using Addrs        = games::game_data<games::ac::Rogue>::ResolvedAddresses;
        using PatternField = std::optional<std::uintptr_t> Addrs::*;

        constexpr std::size_t k_probe_count = 4;
        // 0 = CAN (FUN_1417f6fa0, per-frame counter-availability)
        // 1 = RESOLVE (FUN_141869550, combat action resolver)
        // 2 = RESOLVER_B (FUN_14183b970, action availability)
        // 3 = PARRY (FUN_141845e60, parry/counter entry; decode incoming attack id)
        constexpr std::array<std::string_view, k_probe_count> k_probe_names = {
            "CAN",
            "RESOLVE",
            "RESB",
            "PARRY",
        };
        constexpr std::array<PatternField, k_probe_count> k_probe_fields = {
            &Addrs::counter_can,
            &Addrs::combat_resolve,
            &Addrs::counter_resolver_b,
            &Addrs::combat_parry,
        };

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::array<mem::MidHook, k_probe_count>               g_hooks;
        std::array<std::atomic<std::uint64_t>, k_probe_count> g_counts {};
        std::array<std::uintptr_t, 2>                         g_force_addr {};
        std::array<std::array<std::uint8_t, 6>, 2>            g_force_orig {};
        std::array<bool, 2>                                   g_force_have {};
#pragma clang diagnostic pop

        auto now_ms() -> std::uint64_t {
            using namespace std::chrono;
            return static_cast<std::uint64_t>(
                duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
        }

        auto u32_at(std::uintptr_t base, std::ptrdiff_t off) -> std::uint32_t {
            return *reinterpret_cast<const std::uint32_t *>(base + off);
        }
        auto u8_at(std::uintptr_t base, std::ptrdiff_t off) -> unsigned {
            return *reinterpret_cast<const std::uint8_t *>(base + off);
        }
        auto u64_at(std::uintptr_t base) -> std::uint64_t {
            return *reinterpret_cast<const std::uint64_t *>(base);
        }

        template<std::size_t I>
        struct ProbeFn {
            [[maybe_unused]] static constexpr std::string_view name = "CounterProbe";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                if (!games::ac::rogue::registry().config<Tag>().counter_probe.get()) {
                    return;
                }
                const auto n = g_counts[I].fetch_add(1, std::memory_order_relaxed);
                if (n > 60000) {
                    return;
                }
                const auto player = regs.rcx;
                const auto desc   = regs.rdx;

                if constexpr (I == 0) {
                    // CAN: derive the fight manager from the player (always the live rcx) and
                    // only log when the interesting state changes.
                    const auto obj    = u64_at(player + 0x18);
                    const auto fm     = (obj != 0) ? u64_at(obj + 0xf8) : 0;
                    const auto id230  = (obj != 0) ? u32_at(obj, 0x230) : 0;
                    const auto id6d0  = (obj != 0) ? u32_at(obj, 0x6d0) : 0;
                    const auto b70    = (obj != 0) ? u64_at(obj + 0xb70) : 0;
                    const auto sel    = (obj != 0) ? ((b70 == obj + 0x230) ? id6d0 : id230) : 0;
                    const auto f1138  = (fm != 0) ? u8_at(fm, 0x1138) : 0xFFU;
                    const auto f1008  = (fm != 0) ? u8_at(fm, 0x1008) : 0xFFU;
                    const auto paf8   = u32_at(player, 0xaf8);
                    const auto p124   = u32_at(player, 0x124);
                    const std::uint64_t key =
                        (static_cast<std::uint64_t>(sel) << 32) ^
                        (static_cast<std::uint64_t>(f1138) << 24) ^
                        (static_cast<std::uint64_t>(f1008) << 16) ^
                        (static_cast<std::uint64_t>(paf8 & 0xFFFFU)) ^
                        (static_cast<std::uint64_t>(p124) << 40);
                    static std::uint64_t s_last_key = ~0ULL;
                    if (key != s_last_key) {
                        s_last_key = key;
                        log::get()->info(
                            "CP CAN #{} t={} player={:X} obj={:X} fm={:X} sel={:X} fm1138={} "
                            "fm1008={} paf8={:X} p124={:X}",
                            n,
                            now_ms(),
                            player,
                            obj,
                            fm,
                            sel,
                            f1138,
                            f1008,
                            paf8,
                            p124);
                    }
                } else if constexpr (I == 1) {
                    log::get()->info(
                        "CP RESOLVE #{} t={} player={:X} desc={:X} act={:X} type={:X} step={:X} "
                        "b18b={} p124={:X}",
                        n,
                        now_ms(),
                        player,
                        desc,
                        u32_at(desc, 0x18),
                        u32_at(desc, 0x34),
                        u32_at(desc, 0x18a),
                        u8_at(desc, 0x18b),
                        u32_at(player, 0x124));
                } else if constexpr (I == 2) {
                    log::get()->info(
                        "CP RESB #{} t={} player={:X} desc={:X} act={:X} type={:X} step={:X} "
                        "p124={:X} paf8={:X}",
                        n,
                        now_ms(),
                        player,
                        desc,
                        u32_at(desc, 0x18),
                        u32_at(desc, 0x34),
                        u32_at(desc, 0x18a),
                        u32_at(player, 0x124),
                        u32_at(player, 0xaf8));
                } else {
                    // PARRY: r9 = param_4 (the incoming-attack context). Decode the id the
                    // classifiers read: obj = *param_4; id = obj+0x230 unless obj+0xb70==obj+0x230.
                    const auto ctx = regs.r9;
                    const auto obj = u64_at(ctx);
                    const auto id_main = u32_at(obj, 0x230);
                    const auto id_alt  = u32_at(obj, 0x6d0);
                    const auto ap     = u64_at(obj + 0xb70);
                    log::get()->info(
                        "CP PARRY #{} t={} player={:X} ctx={:X} obj={:X} id230={:X} id6d0={:X} "
                        "b70={:X} sel={:X}",
                        n,
                        now_ms(),
                        player,
                        ctx,
                        obj,
                        id_main,
                        id_alt,
                        ap,
                        (ap == obj + 0x230) ? id_alt : id_main);
                }
            }
        };

        template<std::size_t I>
        void install_probe(const Addrs &addrs) {
            const auto addr = (addrs.*k_probe_fields[I]).value_or(0);
            if (addr == 0) {
                log::get()->warn("CounterProbe: {} pattern missing", k_probe_names[I]);
                return;
            }
            if (auto h = mem::make_hook<ProbeFn<I>>(addr)) {
                g_hooks[I] = std::move(*h);
            } else {
                log::get()->error("CounterProbe: {} hook failed: {}", k_probe_names[I], h.error());
            }
        }

        void apply_force(int force) {
            const bool patch = (force == 2 || force == 3);
            // Only resolver_a (FUN_1418038d0) is force-patched; resolver_b is MidHooked
            // for logging, and patching its prologue would corrupt that hook.
            for (std::size_t i = 0; i < 1; ++i) {
                if (!g_force_have[i] || g_force_addr[i] == 0) {
                    continue;
                }
                if (patch) {
                    const std::uint8_t code[6] = {0xB8, static_cast<std::uint8_t>(force), 0, 0, 0, 0xC3};
                    mem::write(g_force_addr[i], code, 6);
                } else {
                    mem::write(g_force_addr[i], g_force_orig[i].data(), 6);
                }
            }
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        const int force = cfg.counter_force.get();
        apply_force(force);
        log::get()->info("CounterProbe: logging={} force_return={}",
                         cfg.counter_probe.get() ? "on" : "off",
                         force);
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        // Save originals before any force patch so we can always restore.
        g_force_addr[0] = addrs.counter_resolver_a.value();
        std::memcpy(g_force_orig[0].data(), reinterpret_cast<const void *>(g_force_addr[0]), 6);
        g_force_have[0] = true;

        install_probe<0>(addrs);
        install_probe<1>(addrs);
        install_probe<2>(addrs);
        install_probe<3>(addrs);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("CounterProbe: installed");
        return true;
    }
} // namespace hooks
