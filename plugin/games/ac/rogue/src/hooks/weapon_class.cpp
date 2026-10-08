#include "games/ac/rogue/hooks/weapon_class.hpp"

#include <cstdint>

#include <atomic>
#include <string_view>
#include <utility>

#include <safetyhook/inline_hook.hpp>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        mem::MidHook               g_set_fight_type;
        mem::MidHook               g_set_weapon_pose;
        mem::MidHook               g_apply_weapon_type;
        std::atomic<std::uint64_t> g_type_seen_mask {0};
        std::atomic<std::uint64_t> g_type_calls {0};
        std::atomic<bool>          g_offhand_logged {false};
        safetyhook::InlineHook     g_apply_method_hook;
        std::atomic<bool>          g_apply_method_tried {false};
#pragma clang diagnostic pop

        using Tag          = games::ac::rogue::WeaponClassHook;
        using ApplyMethodFn = std::int64_t (*)(void *, unsigned, unsigned);

        // Detour for the component's `vtable+0x400` apply method (__fastcall:
        // comp, type, slot). Force the off-hand slot to type 0 (unarmed).
        auto apply_method_detour(void *comp, unsigned type, unsigned slot) -> std::int64_t {
            const auto &cfg = games::ac::rogue::registry().config<Tag>();
            if (games::ac::rogue::registry().enabled<Tag>() && cfg.hide_offhand.get() && slot == 2) {
                type = 0;
            }
            return g_apply_method_hook.call<std::int64_t>(comp, type, slot);
        }

        // FUN_141807200(rcx=character, edx=fight type, ...) stores the type at
        // character+0x218 and applies the combat/anim set. Remap a dual-wield
        // apply to a single sword so the player uses the one-handed moveset.
        struct WeaponClassFunctor {
            [[maybe_unused]] static constexpr std::string_view name = "OneHandedSword";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                const auto type = static_cast<unsigned>(regs.rdx & 0xFFFF'FFFFULL);

                g_type_calls.fetch_add(1, std::memory_order_relaxed);
                if (type < 64) {
                    const auto bit = std::uint64_t {1} << type;
                    const auto old = g_type_seen_mask.fetch_or(bit, std::memory_order_relaxed);
                    if ((old & bit) == 0) {
                        log::get()->info("OneHandedSword diag: applied fight type {}", type);
                    }
                }

                if (!games::ac::rogue::registry().enabled<Tag>()) {
                    return;
                }
                if (!games::ac::rogue::registry().config<Tag>().one_handed_sword.get()) {
                    return;
                }
                if (type == games::ac::rogue::k_fight_type_dual_wield) {
                    regs.rdx = static_cast<std::uint64_t>(games::ac::rogue::k_fight_type_sword);
                }
            }
        };

        // FUN_1420f3d20(character, type, slot): applies the weapon set for a slot.
        // slot 2 = off-hand. Force the off-hand to "unarmed" so the secondary
        // (dagger) mesh is never applied -> the set reads as a single sword.
        struct ApplyWeaponFunctor {
            [[maybe_unused]] static constexpr std::string_view name = "HideOffHand";

            [[maybe_unused]] static void operator()(mem::Registers &regs) {
                const auto &cfg = games::ac::rogue::registry().config<Tag>();
                if (!games::ac::rogue::registry().enabled<Tag>() || !cfg.hide_offhand.get()) {
                    return;
                }

                // One-time: resolve the component's `vtable+0x400` apply method and
                // detour it so every off-hand apply is forced to type 0 (unarmed).
                if (!g_apply_method_tried.exchange(true, std::memory_order_relaxed)) {
                    const auto entity = *reinterpret_cast<const std::uintptr_t *>(regs.rcx);
                    if (entity != 0) {
                        const auto comp = entity + 0x1f0;
                        const auto vtable = *reinterpret_cast<const std::uintptr_t *>(comp);
                        if (vtable != 0) {
                            const auto method =
                                *reinterpret_cast<const std::uintptr_t *>(vtable + 0x400);
                            if (method != 0) {
                                if (auto h = safetyhook::InlineHook::create(
                                        reinterpret_cast<void *>(method),
                                        reinterpret_cast<void *>(&apply_method_detour))) {
                                    g_apply_method_hook = std::move(*h);
                                    log::get()->info("HideOffHand: apply-method hooked at 0x{:X}",
                                                     method);
                                } else {
                                    log::get()->warn("HideOffHand: apply-method hook failed");
                                }
                            }
                        }
                    }
                }

                const auto slot = static_cast<unsigned>(regs.r8 & 0xFFFF'FFFFULL);
                if (slot != 2) {
                    return;
                }
                if (!g_offhand_logged.exchange(true, std::memory_order_relaxed)) {
                    log::get()->info("HideOffHand: nulling off-hand weapon type (was {})",
                                     static_cast<int>(regs.rdx & 0xFFFF'FFFFULL));
                }
                regs.rdx = 0; // apply unarmed to the off-hand
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        log::get()->info("OneHandedSword: {} | HideOffHand: {}",
                         cfg.one_handed_sword.get() ? "on (DualWield -> Sword)" : "off",
                         cfg.hide_offhand.get() ? "on" : "off");
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        const auto fight_type_addr = addrs.set_fight_type.value();
        const auto pose_addr       = addrs.set_weapon_pose.value();
        log::get()->trace("OneHandedSword: set_fight_type at 0x{:X}, set_weapon_pose at 0x{:X}",
                          fight_type_addr,
                          pose_addr);

        if (auto h = mem::make_hook<WeaponClassFunctor>(fight_type_addr)) {
            g_set_fight_type = std::move(*h);
        } else {
            log::get()->error("OneHandedSword: set_fight_type hook failed: {}", h.error());
            return false;
        }

        if (auto h = mem::make_hook<WeaponClassFunctor>(pose_addr)) {
            g_set_weapon_pose = std::move(*h);
        } else {
            log::get()->error("OneHandedSword: set_weapon_pose hook failed: {}", h.error());
            return false;
        }

        if (addrs.apply_weapon_type) {
            if (auto h = mem::make_hook<ApplyWeaponFunctor>(*addrs.apply_weapon_type)) {
                g_apply_weapon_type = std::move(*h);
                log::get()->info("HideOffHand: installed at 0x{:X}", *addrs.apply_weapon_type);
            } else {
                log::get()->warn("HideOffHand: hook failed: {}", h.error());
            }
        } else {
            log::get()->warn("HideOffHand: APPLY_WEAPON_TYPE pattern missing");
        }

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("OneHandedSword: installed");
        return true;
    }
} // namespace hooks
