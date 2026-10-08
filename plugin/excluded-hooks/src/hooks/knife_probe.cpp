#include "games/ac/rogue/hooks/knife_probe.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::KnifeProbeHook;

        // VA of the player-manager global used by FUN_141e6bea0 to pick the slot.
        constexpr std::uintptr_t k_player_manager = 0x1433866D8;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        mem::MidHook                g_entity_hook;
        std::atomic<std::uint64_t>  g_last {0};
        std::atomic<std::uintptr_t> g_last_obj {0};
#pragma clang diagnostic pop

        auto now_ms() -> std::uint64_t {
            using namespace std::chrono;
            return static_cast<std::uint64_t>(
                duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
        }

        auto rd(std::uintptr_t addr, void *out, std::size_t len) -> bool {
            SIZE_T got = 0;
            return ReadProcessMemory(GetCurrentProcess(),
                                     reinterpret_cast<LPCVOID>(addr),
                                     out,
                                     len,
                                     &got) != 0 &&
                   got >= len;
        }

        void hex_append(char *out, std::size_t &h, const std::uint8_t *buf, std::size_t n) {
            constexpr char kDigits[] = "0123456789ABCDEF";
            for (std::size_t i = 0; i < n && h + 3 < 0x1000; ++i) {
                out[h++] = kDigits[buf[i] >> 4];
                out[h++] = kDigits[buf[i] & 0xF];
                out[h++] = ' ';
            }
            out[h] = '\0';
        }

        // Entry of FUN_141e6bea0. rcx = &slot; *rcx = holder. For the player
        // (holder+0xd0 & 7 == 1) walk the same chain the game uses to reach the
        // local player's tool object and dump it.
        struct EntityFn {
            [[maybe_unused]] static constexpr std::string_view name = "KnifeProbe";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                if (!games::ac::rogue::registry().enabled<Tag>() ||
                    !games::ac::rogue::registry().config<Tag>().enabled.get()) {
                    return;
                }
                const auto slot   = regs.rcx;
                const auto holder = (slot != 0) ? *reinterpret_cast<const std::uintptr_t *>(slot) : 0;
                if (holder == 0) {
                    return;
                }
                std::uint32_t type = 0xFFFFFFFF;
                if (!rd(holder + 0xd0, &type, sizeof(type))) {
                    return;
                }
                if ((type & 7U) != 1U) {
                    return; // not the player
                }

                const auto comp = *reinterpret_cast<const std::uintptr_t *>(holder + 0x40);
                if (comp == 0) {
                    return;
                }
                const auto vtbl = *reinterpret_cast<const std::uintptr_t *>(comp);
                if (vtbl == 0) {
                    return;
                }
                const auto fn = *reinterpret_cast<const std::uintptr_t *>(vtbl + 0x60);
                if (fn == 0) {
                    return;
                }
                using GetObjFn = void *(*)(void *);
                const auto *obj = reinterpret_cast<GetObjFn>(fn)(reinterpret_cast<void *>(comp));
                if (obj == nullptr) {
                    return;
                }
                const auto arr = *reinterpret_cast<const std::uintptr_t *>(obj);
                if (arr == 0) {
                    return;
                }
                const auto pmgr = *reinterpret_cast<const std::uintptr_t *>(k_player_manager);
                const auto idx  = (pmgr != 0) ? *reinterpret_cast<const std::uint8_t *>(pmgr + 0x65) : 0;
                const auto tool_obj = *reinterpret_cast<const std::uintptr_t *>(arr + idx * 8);
                if (tool_obj == 0) {
                    return;
                }

                const auto now     = now_ms();
                const bool changed = g_last_obj.load(std::memory_order_relaxed) != tool_obj;
                if (!changed && now - g_last.load(std::memory_order_relaxed) < 2000) {
                    return;
                }
                g_last.store(now, std::memory_order_relaxed);
                g_last_obj.store(tool_obj, std::memory_order_relaxed);

                std::uint8_t buf[0x200];
                if (!rd(tool_obj, buf, sizeof(buf))) {
                    return;
                }
                char        hex[0x1000];
                std::size_t h = 0;
                hex_append(hex, h, buf, sizeof(buf));
                log::get()->info("KnifeProbe: playerTool=0x{:X} {}", tool_obj, hex);
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        log::get()->info("KnifeProbe: enabled={}", cfg.enabled.get() ? "on" : "off");
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        if (!addrs.knife_entity) {
            log::get()->error("KnifeProbe: KNIFE_ENTITY pattern missing");
            return false;
        }
        auto h = mem::make_hook<EntityFn>(*addrs.knife_entity);
        if (!h) {
            log::get()->error("KnifeProbe: hook failed: {}", h.error());
            return false;
        }
        g_entity_hook = std::move(*h);
        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("KnifeProbe: installed at 0x{:X}", *addrs.knife_entity);
        return true;
    }
} // namespace hooks
