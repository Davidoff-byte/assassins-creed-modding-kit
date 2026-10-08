#include "games/ac/rogue/hooks/player_transform.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <string_view>
#include <utility>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"
#include "core/mem/x64.hpp"

#include "games/ac/rogue/coop/coop_net.hpp"
#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::PlayerTransformHook;

        // Fixed RVAs for the pinned ACC.exe (MD5 a323729f…), resolved from the module base.
        constexpr std::uintptr_t k_cam_mgr_rva    = 0x329DD08; // DAT_14329dd08 camera manager slot
        constexpr std::uintptr_t k_upd_cam_rva    = 0x3664E0;  // Ai::UpdateCamera per-frame task
        constexpr std::uintptr_t k_index_slot_rva = 0x32DE460; // DAT_1432de460 (ready gate)
        constexpr std::uintptr_t k_get_idx_rva    = 0x352C10;  // FUN_140352c10 -> active index
        constexpr std::uintptr_t k_get_player_rva = 0x346AA0;  // FUN_140346aa0 -> object by index
        constexpr std::uintptr_t k_get_pos_rva    = 0x0D8600;  // FUN_1400d8600 -> PlayerPosition

        std::uintptr_t g_camera_manager_slot = 0;
        std::uintptr_t g_index_slot = 0;

        using GetPlayerIndexFn    = int (*)();
        using GetPlayerByIndexFn  = std::uintptr_t (*)(std::uint32_t);
        using GetPositionStructFn = std::uintptr_t (*)(std::uintptr_t);
        GetPlayerIndexFn    g_get_player_index = nullptr;
        GetPlayerByIndexFn  g_get_player_by_index = nullptr;
        GetPositionStructFn g_get_position_struct = nullptr;

        // Camera manager ring (RE-NOTES §6).
        constexpr std::uintptr_t k_counter_off = 0x190;
        constexpr std::uintptr_t k_pos_ring    = 0x0F0;
        constexpr std::uintptr_t k_quat_ring   = 0x140;
        constexpr std::uintptr_t k_ring_stride = 0x10;
        constexpr std::uint32_t  k_ring_len    = 5;

        // PlayerPosition struct (RE-NOTES §7).
        constexpr std::uintptr_t k_pos_flag = 0x18;
        constexpr std::uintptr_t k_pos_ptr  = 0x40;
        constexpr std::uintptr_t k_pos      = 0x30;

        struct Vec3 {
            float x;
            float y;
            float z;
        };
        struct Vec4 {
            float x;
            float y;
            float z;
            float w;
        };

        struct BodyDiag {
            std::int32_t guard = -1;    // DAT_1432de460 slot value (0 => not ready)
            std::int32_t idx = -2;      // active index (-1 => none)
            std::uintptr_t player = 0;
            std::uintptr_t ps = 0;
            std::uintptr_t base = 0;
        };

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<float>        g_log_hz {2.0F};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        std::atomic<std::uintptr_t> g_diag_guard {0};
        std::atomic<std::int32_t>   g_diag_idx {-2};
        std::atomic<std::uintptr_t> g_diag_player {0};
        std::atomic<std::uintptr_t> g_diag_ps {0};
        std::atomic<std::uintptr_t> g_diag_base {0};
        std::atomic<float>          g_speed {0.0F};
        Vec3                        g_last_body {};
        std::int64_t                g_last_body_t = 0;
        bool                        g_have_last = false;
        mem::MidHook              g_hook;
#pragma clang diagnostic pop

        // True only if [addr, addr+size) is all committed and readable. Prevents a bad
        // pointer from faulting the hook (a fault permanently disables it).
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
            const auto region_end =
                reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
            return addr + size <= region_end;
        }

        auto camera_manager() -> std::uintptr_t {
            if (g_camera_manager_slot == 0 || !readable(g_camera_manager_slot, 8)) {
                return 0;
            }
            return mem::read<std::uintptr_t>(g_camera_manager_slot);
        }

        auto finite3(const Vec3 &v) -> bool {
            return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z) &&
                   std::fabs(v.x) < 1.0e7F && std::fabs(v.y) < 1.0e7F && std::fabs(v.z) < 1.0e7F;
        }

        // Player world body position, via the engine's own accessors. Every pointer is
        // validated before it is dereferenced, and the intermediates are recorded for the
        // throttled diagnostic log.
        auto read_player_body(Vec3 &out) -> bool {
            g_diag_guard.store(0);
            g_diag_idx.store(-2);
            g_diag_player.store(0);
            g_diag_ps.store(0);
            g_diag_base.store(0);

            if (g_get_player_index == nullptr || g_get_player_by_index == nullptr ||
                g_get_position_struct == nullptr) {
                return false;
            }
            if (g_index_slot == 0 || !readable(g_index_slot, 8)) {
                return false;
            }
            const auto guard = mem::read<std::uintptr_t>(g_index_slot);
            g_diag_guard.store(static_cast<std::int32_t>(guard != 0));
            if (guard == 0) {
                return false; // DAT_1432de460 dereferenced unguarded inside the chain
            }
            const int idx = g_get_player_index();
            g_diag_idx.store(idx);
            if (idx < 0) {
                return false;
            }
            const auto player = g_get_player_by_index(static_cast<std::uint32_t>(idx));
            g_diag_player.store(player);
            if (!readable(player, 0x80)) {
                return false;
            }
            const auto ps = g_get_position_struct(player);
            g_diag_ps.store(ps);
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
            g_diag_base.store(base);
            if (!readable(base + k_pos, 12)) {
                return false;
            }
            const auto pos = mem::read<Vec3>(base + k_pos);
            if (!finite3(pos)) {
                return false;
            }
            out = pos;
            return true;
        }

        struct SampleCamera {
            [[maybe_unused]] static constexpr std::string_view name = "PlayerTransform";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                Vec3 cam {};
                Vec4 quat {0.0F, 0.0F, 0.0F, 1.0F};
                if (const auto mgr = camera_manager(); mgr != 0 && readable(mgr + k_quat_ring, 0x50)) {
                    const auto counter =
                        mem::read<std::uint32_t>(mgr + k_counter_off) % k_ring_len;
                    const auto i     = (counter + k_ring_len) % k_ring_len;
                    cam = mem::read<Vec3>(mgr + k_pos_ring + (i * k_ring_stride));
                    quat = mem::read<Vec4>(mgr + k_quat_ring + (i * k_ring_stride));
                }

                Vec3 body {};
                const bool have_body = read_player_body(body);
                const Vec3 pos = have_body ? body : cam;

                // Locomotion state derived from the body's own speed (safe: no engine calls).
                std::uint32_t anim = 0;
                if (have_body) {
                    LARGE_INTEGER now {};
                    QueryPerformanceCounter(&now);
                    const auto sfreq = g_qpc_freq.load(std::memory_order_relaxed);
                    if (g_have_last && sfreq > 0 && now.QuadPart > g_last_body_t) {
                        const double dt =
                            static_cast<double>(now.QuadPart - g_last_body_t) /
                            static_cast<double>(sfreq);
                        if (dt > 1.0e-4) {
                            const double dx = static_cast<double>(body.x) - g_last_body.x;
                            const double dy = static_cast<double>(body.y) - g_last_body.y;
                            const double dz = static_cast<double>(body.z) - g_last_body.z;
                            const double speed = std::sqrt((dx * dx) + (dy * dy) + (dz * dz)) / dt;
                            g_speed.store(static_cast<float>(speed), std::memory_order_relaxed);
                            if (speed < 0.5) {
                                anim = 0;
                            } else if (speed < 3.0) {
                                anim = 1;
                            } else if (speed < 7.0) {
                                anim = 2;
                            } else {
                                anim = 3;
                            }
                        }
                    }
                    g_last_body = body;
                    g_last_body_t = now.QuadPart;
                    g_have_last = true;
                }

                using namespace games::ac::rogue::coop;
                publish(pos.x, pos.y, pos.z, quat.x, quat.y, quat.z, quat.w, anim);
                poll();

                const auto hz = g_log_hz.load(std::memory_order_relaxed);
                if (hz <= 0.0F) {
                    return;
                }
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                const auto last = g_last_log.load(std::memory_order_relaxed);
                if (freq <= 0 ||
                    now.QuadPart - last <
                        static_cast<std::int64_t>(static_cast<double>(freq) / hz)) {
                    return;
                }
                g_last_log.store(now.QuadPart, std::memory_order_relaxed);

                if (have_body) {
                    log::get()->info(
                        "PlayerTransform: BODY=({:.1f},{:.1f},{:.1f}) cam=({:.1f},{:.1f},{:.1f}) "
                        "speed={:.1f} state={}",
                        body.x, body.y, body.z, cam.x, cam.y, cam.z, g_speed.load(), anim);
                } else {
                    log::get()->info(
                        "PlayerTransform: body=BAD guard={} idx={} player=0x{:X} ps=0x{:X} base=0x{:X}",
                        g_diag_guard.load(),
                        g_diag_idx.load(),
                        g_diag_player.load(),
                        g_diag_ps.load(),
                        g_diag_base.load());
                }
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);

        games::ac::rogue::coop::NetConfig net;
        net.enabled = cfg.coop_enabled.get();
        const auto octet = [](int v) -> int { return std::clamp(v, 0, 255); };
        net.remote_host = std::to_string(octet(cfg.remote_ip1.get())) + "." +
                          std::to_string(octet(cfg.remote_ip2.get())) + "." +
                          std::to_string(octet(cfg.remote_ip3.get())) + "." +
                          std::to_string(octet(cfg.remote_ip4.get()));
        net.remote_port = static_cast<std::uint16_t>(
            std::clamp(cfg.remote_port.get(), 1, 65535));
        net.local_port = static_cast<std::uint16_t>(
            std::clamp(cfg.local_port.get(), 1, 65535));
        net.client_id = static_cast<std::uint32_t>(std::max(cfg.client_id.get(), 0));
        net.send_hz   = cfg.send_hz.get();
        games::ac::rogue::coop::configure(net);

        log::get()->trace("PlayerTransform: log {:.1f} Hz", cfg.log_hz.get());
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        LARGE_INTEGER freq {};
        QueryPerformanceFrequency(&freq);
        g_qpc_freq.store(freq.QuadPart, std::memory_order_relaxed);

        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        if (base == 0) {
            log::get()->error("PlayerTransform: GetModuleHandle failed");
            return false;
        }
        g_camera_manager_slot = base + k_cam_mgr_rva;
        g_index_slot          = base + k_index_slot_rva;
        g_get_player_index    = reinterpret_cast<GetPlayerIndexFn>(base + k_get_idx_rva);
        g_get_player_by_index = reinterpret_cast<GetPlayerByIndexFn>(base + k_get_player_rva);
        g_get_position_struct = reinterpret_cast<GetPositionStructFn>(base + k_get_pos_rva);
        const auto hook_addr  = base + k_upd_cam_rva;

        log::get()->info("PlayerTransform: base 0x{:X} hook 0x{:X} playerGetter 0x{:X}",
                         base, hook_addr, reinterpret_cast<std::uintptr_t>(g_get_player_by_index));

        auto hook = mem::make_hook<SampleCamera>(hook_addr);
        if (!hook) {
            log::get()->error("PlayerTransform: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        on_reload(games::ac::rogue::registry().config<Tag>());
        log::get()->info("PlayerTransform: installed");
        return true;
    }
} // namespace hooks
