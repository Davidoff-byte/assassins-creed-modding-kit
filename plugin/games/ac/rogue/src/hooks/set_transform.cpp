#include "games/ac/rogue/hooks/set_transform.hpp"

#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string_view>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::SetTransformHook;

        // Fixed RVAs for the pinned ACC.exe (MD5 a323729f…), image base 0x140000000.
        constexpr std::uintptr_t k_hook_rva       = 0x3664E0;  // Ai::UpdateCamera (per-frame)
        constexpr std::uintptr_t k_get_idx_rva    = 0x352C10;  // active player index
        constexpr std::uintptr_t k_get_player_rva = 0x346AA0;  // player object by index
        constexpr std::uintptr_t k_get_pos_rva    = 0x0D8600;  // PlayerPosition struct
        constexpr std::uintptr_t k_ai_global_rva  = 0x329BD78; // DAT_14329bd78 (AI global)
        constexpr std::uintptr_t k_mtx_build_rva  = 0x1EAAF30; // FUN_141eaaf30(char, mtx4x4)
        constexpr std::uintptr_t k_ready_slot_rva = 0x32DE460; // ready gate

        constexpr std::uintptr_t k_actor_comp  = 0x20;   // actor+0x20 = component (teleport char)
        constexpr std::uintptr_t k_actor_pos   = 0x800;  // actor+0x800 = 3 floats (teleport char)
        constexpr std::uintptr_t k_getiface_vt = 0x90;   // comp->vt[0x90](comp, 0xD) -> iface
        constexpr int            k_iface_id    = 0xD;
        constexpr std::uintptr_t k_mtx_trans   = 0x30;   // translation row in the 64-byte matrix
        constexpr std::uintptr_t k_mtx_size    = 64;

        // PlayerPosition struct offsets (RE-NOTES §7).
        constexpr std::uintptr_t k_pos_flag = 0x18;
        constexpr std::uintptr_t k_pos_ptr  = 0x40;
        constexpr std::uintptr_t k_pos_off  = 0x30;

        using GetIdxFn    = int (*)();
        using GetObjFn    = std::uintptr_t (*)(std::uint32_t);
        using GetPosFn    = std::uintptr_t (*)(std::uintptr_t);
        using MtxBuildFn  = char (*)(std::uintptr_t, void *);
        using GetIfaceFn  = void *(*)(void *, int);
        using IfaceValFn  = char (*)(void *, void *);
        using IfaceSetFn  = void (*)(void *, void *);

        GetIdxFn   g_get_idx = nullptr;
        GetObjFn   g_get_obj = nullptr;
        GetPosFn   g_get_pos = nullptr;
        MtxBuildFn g_mtx_build = nullptr;
        std::uintptr_t g_ai_global = 0;
        std::uintptr_t g_ready_slot = 0;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<bool>         g_enabled {false};
        std::atomic<bool>         g_do_transform {false};
        std::atomic<float>        g_offset_x {3.0F};
        std::atomic<float>        g_delay_sec {8.0F};
        std::atomic<float>        g_log_hz {1.0F};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        std::int64_t              g_in_game_since = 0;
        bool                      g_discovered = false;
        bool                      g_transformed = false;
        mem::MidHook              g_hook;
#pragma clang diagnostic pop

        auto readable(std::uintptr_t addr, std::size_t size) -> bool {
            if (addr == 0 || addr < 0x10000) {
                return false;
            }
            MEMORY_BASIC_INFORMATION mbi {};
            if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                return false;
            }
            if (mbi.State != MEM_COMMIT) {
                return false;
            }
            constexpr DWORD ok = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                                 PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                                 PAGE_EXECUTE_WRITECOPY;
            return (mbi.Protect & ok) != 0;
        }

        auto executable(std::uintptr_t addr) -> bool {
            if (addr == 0 || addr < 0x10000) {
                return false;
            }
            MEMORY_BASIC_INFORMATION mbi {};
            if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                return false;
            }
            if (mbi.State != MEM_COMMIT) {
                return false;
            }
            constexpr DWORD ex = PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                                 PAGE_EXECUTE_WRITECOPY;
            return (mbi.Protect & ex) != 0;
        }

        auto player_body_pos(float &ox, float &oy, float &oz) -> bool {
            if (g_get_idx == nullptr || g_get_obj == nullptr || g_get_pos == nullptr ||
                g_ready_slot == 0 || !readable(g_ready_slot, 8) ||
                mem::read<std::uintptr_t>(g_ready_slot) == 0) {
                return false;
            }
            const int idx = g_get_idx();
            if (idx < 0) {
                return false;
            }
            const auto player = g_get_obj(static_cast<std::uint32_t>(idx));
            if (!readable(player, 0x80)) {
                return false;
            }
            const auto ps = g_get_pos(player);
            if (!readable(ps, 0x50)) {
                return false;
            }
            std::uintptr_t base = 0;
            if (mem::read<std::uint64_t>(ps + k_pos_flag) == 0) {
                base = ps + 0x20;
            } else {
                const auto ptr = mem::read<std::uintptr_t>(ps + k_pos_ptr);
                if (ptr != 0 && readable(ptr, 0x40)) {
                    base = ptr + 0x20;
                }
            }
            if (!readable(base + k_pos_off, 12)) {
                return false;
            }
            ox = mem::read<float>(base + k_pos_off);
            oy = mem::read<float>(base + k_pos_off + 4);
            oz = mem::read<float>(base + k_pos_off + 8);
            return std::isfinite(ox) && std::isfinite(oy) && std::isfinite(oz);
        }

        // First live actor in AI partition 1 — the object shape that matches the teleport's
        // `char` (component at +0x20, position/saved slot at +0x800).
        auto current_actor() -> std::uintptr_t {
            if (g_ai_global == 0 || !readable(g_ai_global, 8)) {
                return 0;
            }
            const auto ai = mem::read<std::uintptr_t>(g_ai_global);
            if (ai == 0) {
                return 0;
            }
            const auto chunk = ai + ((static_cast<std::uintptr_t>(1) + 7) * 0x10);
            if (!readable(chunk, 0x40)) {
                return 0;
            }
            const auto n = mem::read<std::uint16_t>(chunk + 0x0A);
            const auto data = mem::read<std::uintptr_t>(chunk);
            if (data == 0 || n == 0 || !readable(data, static_cast<std::size_t>(n) * 8)) {
                return 0;
            }
            for (std::uint16_t i = 0; i < n && i < 8; ++i) {
                const auto actor =
                    mem::read<std::uintptr_t>(data + (static_cast<std::size_t>(i) * 8));
                if (readable(actor, 0x820)) {
                    return actor;
                }
            }
            return 0;
        }

        struct Probe {
            [[maybe_unused]] static constexpr std::string_view name = "SetTransform";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                if (!g_enabled.load(std::memory_order_relaxed)) {
                    return;
                }
                float px = 0.0F;
                float py = 0.0F;
                float pz = 0.0F;
                const bool have_player = player_body_pos(px, py, pz);
                const auto actor = current_actor();
                if (actor == 0 || !have_player) {
                    g_in_game_since = 0;
                    return;
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                if (g_in_game_since == 0) {
                    g_in_game_since = now.QuadPart;
                }

                if (!g_discovered) {
                    g_discovered = true;
                    const auto comp = mem::read<std::uintptr_t>(actor + k_actor_comp);
                    const float ax = mem::read<float>(actor + k_actor_pos);
                    const float ay = mem::read<float>(actor + k_actor_pos + 4);
                    const float az = mem::read<float>(actor + k_actor_pos + 8);
                    log::get()->info(
                        "SetTransform: actor=0x{:X} comp(+0x20)=0x{:X} pos(+0x800)=({:.1f},{:.1f},{:.1f}) player=({:.1f},{:.1f},{:.1f})",
                        actor, comp, ax, ay, az, px, py, pz);
                    if (comp != 0 && readable(comp, 8)) {
                        const auto vt = mem::read<std::uintptr_t>(comp);
                        log::get()->info("SetTransform: actor->comp->vt=0x{:X}", vt);
                        if (vt != 0 && readable(vt + k_getiface_vt, 8)) {
                            const auto getfn = mem::read<std::uintptr_t>(vt + k_getiface_vt);
                            log::get()->info("SetTransform: vt+0x90=0x{:X} exec={}", getfn,
                                             executable(getfn));
                            if (executable(getfn)) {
                                auto *fn = reinterpret_cast<GetIfaceFn>(getfn);
                                void *iface = fn(reinterpret_cast<void *>(comp), k_iface_id);
                                log::get()->info("SetTransform: iface(0xD)=0x{:X}",
                                                 reinterpret_cast<std::uintptr_t>(iface));
                            }
                        }
                    }
                }

                // Guarded transform test after a delay so the discovery lines land first.
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                if (g_do_transform.load(std::memory_order_relaxed) && !g_transformed && freq > 0 &&
                    now.QuadPart - g_in_game_since >=
                        static_cast<std::int64_t>(static_cast<double>(g_delay_sec.load()) * freq)) {
                    g_transformed = true;
                    const auto comp = mem::read<std::uintptr_t>(actor + k_actor_comp);
                    if (comp == 0 || !readable(comp, 8)) {
                        log::get()->info("SetTransform: abort (actor+0x20 not a component: 0x{:X})",
                                         comp);
                        return;
                    }
                    const auto vt = mem::read<std::uintptr_t>(comp);
                    if (!readable(vt + k_getiface_vt, 8)) {
                        return;
                    }
                    auto *getfn =
                        reinterpret_cast<GetIfaceFn>(mem::read<std::uintptr_t>(vt + k_getiface_vt));
                    if (!executable(reinterpret_cast<std::uintptr_t>(getfn))) {
                        return;
                    }
                    void *iface = getfn(reinterpret_cast<void *>(comp), k_iface_id);
                    if (iface == nullptr || !readable(reinterpret_cast<std::uintptr_t>(iface), 8)) {
                        log::get()->info("SetTransform: iface null");
                        return;
                    }
                    // Build our own matrix: identity rotation + translation (+0x30) at player pos.
                    alignas(16) unsigned char mtx[k_mtx_size] {};
                    auto *f = reinterpret_cast<float *>(mtx);
                    f[0] = 1.0F;
                    f[5] = 1.0F;
                    f[10] = 1.0F;
                    f[15] = 1.0F;
                    auto *tr = reinterpret_cast<float *>(mtx + k_mtx_trans);
                    tr[0] = px + g_offset_x.load();
                    tr[1] = py;
                    tr[2] = pz;
                    tr[3] = 1.0F;
                    const auto ivt =
                        mem::read<std::uintptr_t>(reinterpret_cast<std::uintptr_t>(iface));
                    const auto f28 = mem::read<std::uintptr_t>(ivt + 0x28);
                    const auto f30 = mem::read<std::uintptr_t>(ivt + 0x30);
                    log::get()->info(
                        "SetTransform: iface vt=0x{:X} f28=0x{:X} f30=0x{:X} target=({:.1f},{:.1f},{:.1f})",
                        ivt, f28, f30, tr[0], tr[1], tr[2]);
                    if (executable(f28) && executable(f30)) {
                        auto *val = reinterpret_cast<IfaceValFn>(f28);
                        auto *set = reinterpret_cast<IfaceSetFn>(f30);
                        const char ok = val(iface, mtx);
                        log::get()->info("SetTransform: validate={}", ok);
                        if (ok != '\0') {
                            set(iface, mtx);
                            log::get()->info(
                                "SetTransform: APPLIED transform to ({:.1f},{:.1f},{:.1f})",
                                tr[0], tr[1], tr[2]);
                        }
                    }
                }

                const auto hz = g_log_hz.load(std::memory_order_relaxed);
                if (hz <= 0.0F || freq <= 0) {
                    return;
                }
                const auto last = g_last_log.load(std::memory_order_relaxed);
                if (now.QuadPart - last < static_cast<std::int64_t>(static_cast<double>(freq) / hz)) {
                    return;
                }
                g_last_log.store(now.QuadPart, std::memory_order_relaxed);
                log::get()->info("SetTransform: actor=0x{:X} discovered={} transformed={}",
                                 actor, g_discovered, g_transformed);
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_enabled.store(cfg.enabled.get(), std::memory_order_relaxed);
        g_do_transform.store(cfg.do_transform.get(), std::memory_order_relaxed);
        g_offset_x.store(cfg.offset_x.get(), std::memory_order_relaxed);
        g_delay_sec.store(cfg.delay_sec.get(), std::memory_order_relaxed);
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("SetTransform: GetModuleHandle failed");
            return false;
        }
        g_get_idx    = reinterpret_cast<GetIdxFn>(base + k_get_idx_rva);
        g_get_obj    = reinterpret_cast<GetObjFn>(base + k_get_player_rva);
        g_get_pos    = reinterpret_cast<GetPosFn>(base + k_get_pos_rva);
        g_mtx_build  = reinterpret_cast<MtxBuildFn>(base + k_mtx_build_rva);
        g_ai_global  = base + k_ai_global_rva;
        g_ready_slot = base + k_ready_slot_rva;

        auto hook = mem::make_hook<Probe>(base + k_hook_rva);
        if (!hook) {
            log::get()->error("SetTransform: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("SetTransform: installed (builder 0x{:X})",
                         reinterpret_cast<std::uintptr_t>(g_mtx_build));
        return true;
    }
} // namespace hooks
