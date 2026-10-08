#include "games/ac/blackflag/hooks/cam_probe.hpp"

#include <atomic>
#include <cmath>
#include <cstdint>
#include <string_view>
#include <utility>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/blackflag/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::blackflag::CamProbeHook;

        // Pinned AC4BFSP.exe (MD5 2058342866688F780C8B34526A65BC35), base 0x400000.
        constexpr std::uintptr_t k_upd_cam_rva  = 0x23BBB0;   // Ai::UpdateCamera
        constexpr std::uintptr_t k_cam_mgr_rva  = 0x026BE588; // camera manager global (0x02abe588)
        constexpr std::uintptr_t k_cam_pos_rva  = 0x026BE530; // camera position vec4 (0x02abe530)
        constexpr std::uintptr_t k_cam_pos2_rva = 0x026BE540; // second vec4 (0x02abe540)

        std::uintptr_t g_cam_mgr_slot = 0;
        std::uintptr_t g_cam_pos = 0;
        std::uintptr_t g_cam_pos2 = 0;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<bool>         g_enabled {true};
        std::atomic<float>        g_log_hz {0.5F};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
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
            if ((mbi.Protect & ok) == 0) {
                return false;
            }
            const auto end = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
            return addr + size <= end;
        }

        auto f32(std::uintptr_t a) -> float { return mem::read<float>(a); }

        // Is there a float triple at base+off close to (cx,cy,cz)?
        auto near_triple(std::uintptr_t base, std::uintptr_t off, float cx, float cy, float cz,
                         float eps) -> bool {
            const float x = f32(base + off + 0);
            const float y = f32(base + off + 4);
            const float z = f32(base + off + 8);
            if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
                return false;
            }
            return std::fabs(x - cx) < eps && std::fabs(y - cy) < eps && std::fabs(z - cz) < eps;
        }

        struct Probe {
            [[maybe_unused]] static constexpr std::string_view name = "CamProbe";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                if (!g_enabled.load(std::memory_order_relaxed)) {
                    return;
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                const auto hz = g_log_hz.load(std::memory_order_relaxed);
                const auto last = g_last_log.load(std::memory_order_relaxed);
                if (freq <= 0 || hz <= 0.0F ||
                    now.QuadPart - last < static_cast<std::int64_t>(static_cast<double>(freq) / hz)) {
                    return;
                }
                g_last_log.store(now.QuadPart, std::memory_order_relaxed);

                if (g_cam_mgr_slot == 0 || !readable(g_cam_mgr_slot, 4)) {
                    log::get()->info("CamProbe: no manager slot");
                    return;
                }
                const auto mgr = mem::read<std::uint32_t>(g_cam_mgr_slot);
                if (mgr == 0 || !readable(mgr, 0x200)) {
                    log::get()->info("CamProbe: manager null/invalid (0x{:X})", mgr);
                    return;
                }

                float cx = 0.0F;
                float cy = 0.0F;
                float cz = 0.0F;
                if (readable(g_cam_pos, 12)) {
                    cx = f32(g_cam_pos + 0);
                    cy = f32(g_cam_pos + 4);
                    cz = f32(g_cam_pos + 8);
                }
                log::get()->info("CamProbe: mgr=0x{:X} campos=({:.1f},{:.1f},{:.1f})", mgr, cx, cy, cz);

                // The camera object chain: mgr+0x4c -> holder -> *holder = camera object.
                const auto a = mem::read<std::uint32_t>(mgr + 0x4c);
                if (readable(a, 0x10)) {
                    const auto b = mem::read<std::uint32_t>(a);
                    log::get()->info("CamProbe: mgr+0x4c=0x{:X} -> *()=0x{:X}", a, b);
                    if (readable(b, 0x40)) {
                        log::get()->info(
                            "CamProbe: camobj pos(+0x10)=({:.1f},{:.1f},{:.1f}) ori(+0x20)=({:.1f},{:.1f},{:.1f})",
                            f32(b + 0x10), f32(b + 0x14), f32(b + 0x18),
                            f32(b + 0x20), f32(b + 0x24), f32(b + 0x28));
                        // The camera target object: camobj+0x68. Dump its vtable + pointer
                        // fields (with their vtables) to identify the class of the player object.
                        const auto tgt = mem::read<std::uint32_t>(b + 0x68);
                        if (readable(tgt, 0x100)) {
                            const auto tvt = mem::read<std::uint32_t>(tgt);
                            log::get()->info("CamProbe: TARGET obj=0x{:X} vt=0x{:X}", tgt, tvt);
                            for (std::uintptr_t o = 0; o < 0x100; o += 4) {
                                const auto p = mem::read<std::uint32_t>(tgt + o);
                                if (!readable(p, 0x40)) {
                                    continue;
                                }
                                const auto pvt = mem::read<std::uint32_t>(p);
                                log::get()->info(
                                    "CamProbe:   TARGET+0x{:X} -> 0x{:X} (vt=0x{:X})", o, p, pvt);
                            }
                        }
                        for (std::uintptr_t off = 0; off < 0x80; off += 4) {
                            const auto p = mem::read<std::uint32_t>(b + off);
                            if (!readable(p, 0x100)) {
                                continue;
                            }
                            for (std::uintptr_t o = 0; o < 0x80; o += 4) {
                                if (near_triple(p, o, cx, cy, cz, 8.0F)) {
                                    log::get()->info(
                                        "CamProbe:   camobj+0x{:X} -> 0x{:X} +0x{:X} near campos = ({:.1f},{:.1f},{:.1f})",
                                        off, p, o, f32(p + o), f32(p + o + 4), f32(p + o + 8));
                                }
                            }
                        }
                    }
                }

                // Scan the manager's own fields for pointers to objects holding a triple
                // at/near the camera position (candidate player/character objects).
                int hits = 0;
                for (std::uintptr_t off = 0; off < 0x200 && hits < 12; off += 4) {
                    const auto p = mem::read<std::uint32_t>(mgr + off);
                    if (!readable(p, 0x100)) {
                        continue;
                    }
                    for (std::uintptr_t o = 0; o < 0x80; o += 4) {
                        if (near_triple(p, o, cx, cy, cz, 8.0F)) {
                            log::get()->info(
                                "CamProbe: PTR mgr+0x{:X} -> 0x{:X} +0x{:X} = ({:.1f},{:.1f},{:.1f})",
                                off, p, o, f32(p + o), f32(p + o + 4), f32(p + o + 8));
                            ++hits;
                            break;
                        }
                    }
                }
                if (hits == 0) {
                    log::get()->info("CamProbe: no near-camera object found on manager");
                }
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_enabled.store(cfg.enabled.get(), std::memory_order_relaxed);
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("CamProbe: GetModuleHandle failed");
            return false;
        }
        g_cam_mgr_slot = base + k_cam_mgr_rva;
        g_cam_pos      = base + k_cam_pos_rva;
        g_cam_pos2     = base + k_cam_pos2_rva;

        auto hook = mem::make_hook<Probe>(base + k_upd_cam_rva);
        if (!hook) {
            log::get()->error("CamProbe: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::blackflag::registry().config<Tag>());
        log::get()->info("CamProbe: installed");
        return true;
    }
} // namespace hooks
