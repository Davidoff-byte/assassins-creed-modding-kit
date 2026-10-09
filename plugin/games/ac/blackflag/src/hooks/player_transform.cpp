#include "games/ac/blackflag/hooks/player_transform.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <Windows.h>
#include <tlhelp32.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

#include "games/ac/blackflag/coop/combat_sync.hpp"
#include "games/ac/blackflag/coop/coop_net.hpp"
#include "games/ac/blackflag/coop/ghost_body.hpp"
#include "games/ac/blackflag/coop/nav_drive.hpp"
#include "games/ac/blackflag/coop/overlay.hpp"
#include "games/ac/blackflag/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::blackflag::PlayerTransformHook;

        // Fixed RVAs for the pinned AC4BFSP.exe (MD5 2058342866688F780C8B34526A65BC35), base 0x400000.
        constexpr std::uintptr_t k_cam_mgr_rva = 0x026BE588; // global 0x02abe588
        constexpr std::uintptr_t k_upd_cam_rva = 0x23BBB0;   // Ai::UpdateCamera = 0x0063bbb0

        // Camera manager ring (bf-coop/RE-NOTES.md §4):
        //   counter at +0x130, position ring (inferred) at +0x90, orientation ring at +0xE0.
        constexpr std::uintptr_t k_counter_off = 0x130;
        constexpr std::uintptr_t k_pos_ring    = 0x90;
        constexpr std::uintptr_t k_quat_ring   = 0xE0;
        constexpr std::uintptr_t k_ring_stride = 0x10;
        constexpr std::uint32_t  k_ring_len    = 5;

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

        std::uintptr_t g_cam_mgr_slot = 0;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<float>        g_log_hz {2.0F};
        std::atomic<bool>         g_act_scan_allowed {false}; // v19.2: [PlayerTransform] ActScan
        std::atomic<std::uint32_t> g_adopt_only_lo {0}; // v19.3 knobs
        std::atomic<std::uint32_t> g_adopt_only_hi {0};
        std::atomic<std::uint32_t> g_adopt_skip_lo {0};
        std::atomic<std::uint32_t> g_adopt_skip_hi {0};
        std::atomic<int>           g_adopt_max {0};
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        std::atomic<int>          g_spawn_logs {0};
        std::atomic<int>          g_new_logs {0};

        // v10 AllocTrace: unique (class-ctor, caller) pairs seen by the alloc probe. Maps the
        // complete object-creation call graph; the Entity body ctor (0x52B750, desc 0x2760EF0)
        // reveals the character-creating call sites.
        struct AllocPair {
            std::uint32_t ctor = 0;
            std::uint32_t ret = 0;
            std::uint32_t desc = 0;
            std::uint32_t count = 0;
        };
        AllocPair        g_alloc_pairs[768];
        std::atomic<int> g_alloc_pair_n {0};
        std::atomic<int> g_mass_logs {0};
        std::atomic<int> g_entctor_logs {0};
        std::atomic<int> g_node_logs {0};
        std::atomic<std::uint32_t> g_last_ent_key_lo {0};
        std::atomic<std::uint32_t> g_last_ent_key_hi {0};
        std::atomic<int>           g_ent_key_count {0};
        std::uint32_t              g_ent_keys_lo[128] = {};
        std::uint32_t              g_ent_keys_hi[128] = {};
        std::atomic<std::uint32_t> g_last_registry {0}; // v14: the registry (ECX at mass-create)

        // v19 AdoptTest: full key history per load burst (a region load = ~1772 Entity keys).
        // A shell pre-placed at a key of an UNLOADED region may be adopted by that region's next
        // load through the same find-or-create the world itself uses - converting a runtime-created
        // object into a stream-owned one.
        struct AdoptKey {
            std::uint32_t lo    = 0;
            std::uint32_t hi    = 0;
            std::uint32_t burst = 0;
        };
        AdoptKey                   g_adopt_keys[8192];
        std::atomic<int>           g_adopt_key_n {0};
        std::atomic<std::uint32_t> g_adopt_burst {0};
        std::atomic<std::uint64_t> g_adopt_burst_last {0}; // GetTickCount64 of the last key
        std::uint32_t              g_adopt_burst_count[128] = {};
        std::uint32_t              g_adopt_burst_first_lo[128] = {};
        std::uint32_t              g_adopt_burst_first_hi[128] = {};
        std::atomic<std::uint32_t> g_adopt_logged_burst {0};
        std::atomic<bool>          g_adopt_test {false};
        bool                       g_adopt_armed = false;
        bool                       g_adopt_created = false;
        std::uintptr_t             g_adopt_shells[32] = {};
        std::uint32_t              g_adopt_shell_lo[32] = {};
        std::uint32_t              g_adopt_shell_hi[32] = {};
        std::uint32_t              g_adopt_shell_state[32] = {};
        int                        g_adopt_shell_n = 0;
        int                        g_adopt_watch_logs = 0;
        std::uintptr_t             g_adopt_deliver_target = 0;
        int                        g_adopt_deliver_tries = 0;
        mem::MidHook              g_hook;
        mem::MidHook              g_probe;
        mem::MidHook              g_probe_new;
        mem::MidHook              g_probe_main;
        mem::MidHook              g_probe_jobpost;
        mem::MidHook              g_probe_jobdesc;
        mem::MidHook              g_probe_jobctx;
        mem::MidHook              g_probe_alloc;
        mem::MidHook              g_probe_inst; // v10: generic instantiate probe (FUN_00a359c0)
        mem::MidHook              g_probe_entctor; // v11: Entity ctor 0x52B750 (desc 0x2760EF0)
        mem::MidHook              g_probe_copy;
        mem::MidHook              g_probe_spawnapi;
        mem::MidHook              g_probe_spawnret;
        mem::MidHook              g_probe_masscreate;
        mem::MidHook              g_probe_reqwatch; // v20: animation-request setter watch (FUN_01ad9190)
        mem::MidHook              g_probe_setlife;
        mem::MidHook              g_probe_setlife_n;
        mem::MidHook              g_probe_msg_a;
        mem::MidHook              g_probe_msg_b;
        mem::MidHook              g_probe_animapply; // v21: animation-apply probe (FUN_01ac1ad0)
        mem::MidHook              g_probe_animwrite; // v21: animation-write probe (FUN_01b52c0)
        std::atomic<int>          g_dmg_probe_logs {0};
        std::atomic<bool>         g_world_seen {false};
        std::atomic<bool>         g_spawn_capture {false};
        std::uintptr_t            g_spawnq_obj = 0; // v16.5: last spawned object (watch + source guard)
        std::uintptr_t            g_v16_obj = 0;    // v16.5: pending graphics attach target
        std::uintptr_t            g_hswap_clone = 0; // v18: record-handle share target
        bool                      g_hswap_done = true;
        std::uintptr_t            g_hswap_cursor = 0;
        std::uintptr_t            g_jobenq_addr = 0;
        std::uintptr_t            g_exe_base    = 0;
        Vec3                      g_last_pos {0.0F, 0.0F, 0.0F};
        std::int64_t              g_last_pos_t0 = 0; // QPC of the last valid g_last_pos update
        Vec4                      g_last_quat {0.0F, 0.0F, 0.0F, 1.0F};

        static DWORD WINAPI replay_thread(LPVOID); // defined below (spawn replay)

        static std::uintptr_t registry_find_helper(std::uintptr_t fn, std::uint32_t k1,
                                                   std::uint32_t k2); // defined below
        static std::uintptr_t registry_find2(std::uintptr_t fn, std::uint32_t reg, std::uint32_t k1,
                                             std::uint32_t k2); // v14
        static void          *spawn_keyed2(std::uintptr_t fn, std::uint32_t reg, std::uint32_t id,
                                           std::uint32_t k1, std::uint32_t k2); // v14
        static int spawn_reg_helper(std::uintptr_t fn, std::uintptr_t entity); // v15
#pragma clang diagnostic pop

        // True only if [addr, addr+size) is all committed and readable.
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
            const auto end =
                reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
            return addr + size <= end;
        }

        auto finite3(const Vec3 &v) -> bool {
            return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z) &&
                   std::fabs(v.x) < 1.0e7F && std::fabs(v.y) < 1.0e7F && std::fabs(v.z) < 1.0e7F;
        }

        // Walks the camera chain to the player's character provider and returns the
        // live body transform: quat at +0x100, feet position at +0x110.
        auto read_body_transform(std::uintptr_t mgr, Vec3 &pos, Vec4 &quat) -> bool {
            if (mgr == 0) {
                return false;
            }
            if (!readable(mgr + 0x4C, 4)) {
                return false;
            }
            const auto holder = mem::read<std::uintptr_t>(mgr + 0x4C);
            if (!readable(holder, 4)) {
                return false;
            }
            const auto camobj = mem::read<std::uintptr_t>(holder);
            if (!readable(camobj + 0x68, 4)) {
                return false;
            }
            const auto block = mem::read<std::uintptr_t>(camobj + 0x68);
            if (!readable(block + 0x174, 4)) {
                return false;
            }
            const auto prov = mem::read<std::uintptr_t>(block + 0x174);
            if (!readable(prov + 0x100, 0x20)) {
                return false;
            }
            quat = mem::read<Vec4>(prov + 0x100);
            pos  = mem::read<Vec3>(prov + 0x110);
            return finite3(pos);
        }

        // --- B4 read side: the player's action state (controller fields mapped 2026-10-06) ---
        // Player controller = node(+0xE8); phase=+0x8E0, hang=+0x8D8, blend=+0x8D4,
        // in-action flags bit0 of +0x138 and +0x8D0. Published as packed anim_state.
        std::uintptr_t g_act_ctl      = 0;
        std::uintptr_t g_act_node     = 0;
        std::int64_t   g_act_last_qpc = 0;
        std::uint32_t  g_act_fail_count = 0; // consecutive failed controller scans (backoff)
        std::atomic<std::int64_t> g_load_qpc {0};
        std::uint32_t  g_last_anim_state = 0;
        bool           g_act_read_enabled = true; // re-enabled: refresh_act_ctl caches + rescans on backoff

        // --- StateProbe: read-only locomotion-state sampler (parkour/animation sync research) ---
        // Logs the player controller's state bytes (+0x8D0..0x8E8) and +0x138 whenever they
        // change, so walk/run/climb/vault/swim codes can be mapped offline.
        std::uint8_t  g_sp_last[0x18] = {};
        std::uint32_t g_sp_last_f138  = 0;
        std::int64_t  g_sp_last_qpc   = 0;
        int           g_sp_count      = 0;

        // --- B3 clone test (config-gated, one-shot): clone the character object(s) ---
        std::atomic<bool> g_clone_test {false};
        bool              g_clone_done  = false;

        // --- P1 CullWatch: 10 Hz read-only lifecycle sampler for the driven ghost body ---
        std::atomic<bool> g_cull_watch {false};
        std::int64_t      g_cw_last_qpc = 0;
        std::uintptr_t    g_cw_body     = 0;
        bool              g_cw_dead     = false;
        struct CwSample {
            std::uint32_t vt       = 0;
            std::uint16_t children = 0;
            std::uint32_t f68      = 0;
            std::uint32_t fc8      = 0;
            std::uint32_t fe8      = 0;
            bool          valid    = false;
        };
        CwSample g_cw_last;

        // Per-page scan (pure helper - its own __try so a page freed mid-scan only skips
        // that page, not the whole hunt).
        static int scan_char_page(std::uintptr_t ba, std::uintptr_t end, std::uintptr_t *out,
                                  int max, int found_n) {
            constexpr std::uint32_t k_vt_derived = 0x01E64680;
            constexpr std::uint32_t k_vt_mid     = 0x01E4A128;
            constexpr std::uintptr_t k_clone_fn  = 0x006DEFF0;
            __try {
                for (std::uintptr_t p = ba; p <= end && found_n < max; p += 4) {
                    const auto vt = mem::read<std::uint32_t>(p);
                    bool match = false;
                    if (vt == k_vt_derived || vt == k_vt_mid) {
                        match = true;
                    } else if (vt >= 0x400000 && vt < 0x2F00000 && readable(vt + 0x0C, 4) &&
                               mem::read<std::uintptr_t>(vt + 0x0C) == k_clone_fn) {
                        match = true;
                    }
                    if (!match) {
                        continue;
                    }
                    // The async clone reads [this+4] (the entity-data pointer) - the mid-class
                    // shells have it null and crash the serializer. Require a real pointer.
                    const auto eptr = mem::read<std::uintptr_t>(p + 4);
                    if (eptr < 0x20000000 || eptr >= 0x7FFF0000 || !readable(eptr, 4)) {
                        continue;
                    }
                    out[found_n++] = p;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            return found_n;
        }

        auto scan_char_objs(std::uintptr_t *out, int max) -> int {
            // Cloneable characters: the two known character vtables (derived + runtime-built
            // mid-class) OR any vtable whose slot 3 (0xC) = the clone (subclass family).
            // Candidates must carry a valid entity-data pointer at +4 (the async clone's
            // serializer reads [this+4] - shells have it null and crash).
            int found_n = 0;
            LARGE_INTEGER t0 {};
            QueryPerformanceCounter(&t0);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            // The game's heap (where the character objects live) sits well above the image +
            // DLL region; start at 0x20000000 to skip the first 512 MB of noise.
            std::uintptr_t addr = 0x20000000;
            while (addr < 0x7FFF0000 && found_n < max) {
                MEMORY_BASIC_INFORMATION mbi {};
                if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                    break;
                }
                const auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                auto       sz = mbi.RegionSize;
                if (sz == 0) {
                    sz = 0x10000; // guard against a zero-size region looping forever
                }
                const bool ok = (mbi.State == MEM_COMMIT) &&
                                (mbi.Protect & (PAGE_READONLY | PAGE_READWRITE |
                                                PAGE_WRITECOPY)) != 0 &&
                                (mbi.Protect & PAGE_GUARD) == 0;
                if (ok && sz >= 4) {
                    found_n = scan_char_page(ba, ba + sz - 4, out, max, found_n);
                }
                addr = ba + sz;
                // deadline: never spin past ~90 s
                if (freq > 0) {
                    LARGE_INTEGER t1 {};
                    QueryPerformanceCounter(&t1);
                    if (t1.QuadPart - t0.QuadPart > freq * 90) {
                        break;
                    }
                }
            }
            return found_n;
        }

        auto thread_census_tick() -> void {
            if (g_clone_done) {
                return;
            }
            g_clone_done = true;
            using NtQITFn = LONG(NTAPI *)(HANDLE, LONG, void *, ULONG, ULONG *);
            static NtQITFn nt_qit = reinterpret_cast<NtQITFn>(reinterpret_cast<void *>(
                GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "NtQueryInformationThread")));
            if (nt_qit == nullptr) {
                log::get()->info("ThreadCensus: NtQueryInformationThread unavailable");
                return;
            }
            const auto pid  = GetCurrentProcessId();
            const auto snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
            if (snap == INVALID_HANDLE_VALUE) {
                log::get()->info("ThreadCensus: snapshot failed");
                return;
            }
            THREADENTRY32 te {};
            te.dwSize = sizeof(te);
            int n = 0;
            if (Thread32First(snap, &te)) {
                do {
                    if (te.th32OwnerProcessID != pid) {
                        continue;
                    }
                    const HANDLE th = OpenThread(THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
                    if (th == nullptr) {
                        continue;
                    }
                    ULONG_PTR start = 0;
                    ULONG     len   = 0;
                    const auto st   = nt_qit(th, 9, &start, sizeof(start), &len); // ThreadQuerySetWin32StartAddress
                    log::get()->info("ThreadCensus: tid={} start=0x{:X} prio={} st={}",
                                     te.th32ThreadID, static_cast<std::uintptr_t>(start),
                                     te.tpBasePri, static_cast<LONG>(st));
                    CloseHandle(th);
                    n++;
                } while (Thread32Next(snap, &te));
            }
            CloseHandle(snap);
            log::get()->info("ThreadCensus: done ({} threads)", n);
        }

        // --- CloneTest runner: the census + scan + clones run on a plugin-owned thread ---
        // (the scan walks the whole heap and would block the camera frame for minutes).
        std::atomic<bool> g_probe_started {false};

        // Main-loop hook: runs on the game's MAIN thread (window loop FUN_004060a0).
        // The clone must be invoked from here - the camera thread's job context deadlocks.
        struct ProbeMain {
            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                // (boot-only loop; kept armed for future main-thread work)
            }
        };

        // ProbeClone: log every engine-side call of the clone (FUN_006deff0) - the definitive
        // answer to which thread + which args the engine itself uses.
        struct ProbeClone {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                const auto a1 = mem::read<std::uintptr_t>(r.esp + 4);
                const auto a2 = mem::read<std::uintptr_t>(r.esp + 8);
                log::get()->info("CloneTest: engine clone call this=0x{:X} a1=0x{:X} a2=0x{:X} thread={}",
                                 r.ecx, a1, a2, GetCurrentThreadId());
            }
        };

        // --- CloneTest micro-probes: trace the clone chain to pin the exact hang ---
        // Log-only (pass-through); gated on the in-clone window so only the clone's own
        // job-posting chain is traced (the engine's ambient per-frame jobs stay silent).
        std::atomic<bool> g_in_clone {false};

        // Inline-call the engine's deferred setup callback (the job-runner convention:
        // ecx = obj, two zero stack args; the thunks forward ecx untouched). Pure helper.
        static int inline_cb_call(std::uintptr_t obj, std::uintptr_t cb) {
            __try {
                using CbFn = void(__thiscall *)(void *, int, int);
                reinterpret_cast<CbFn>(cb)(reinterpret_cast<void *>(obj), 0, 0);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return GetExceptionCode();
            }
        }

        struct ProbeJobPost { // FUN_00a2dae0 (RVA 0x62DAE0) - the job-post entry
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_in_clone.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto a1 = mem::read<std::uintptr_t>(r.esp + 4);
                const auto a2 = mem::read<std::uintptr_t>(r.esp + 8);
                const auto a3 = mem::read<std::uintptr_t>(r.esp + 0x0C);
                const int  rc = inline_cb_call(a1, a2);
                log::get()->info("CloneTest: JobPost(obj=0x{:X} cb=0x{:X} q=0x{:X}) inline -> 0x{:X}",
                                 a1, a2, a3, rc);
            }
        };

        struct ProbeJobDesc { // FUN_00a2dbd0 (RVA 0x62DBD0) - the task-desc init
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_in_clone.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto a1 = mem::read<std::uintptr_t>(r.esp + 4);
                log::get()->info("CloneTest: JobDesc(desc=0x{:X})", a1);
            }
        };

        struct ProbeJobCtx { // FUN_00a2d4f0 (RVA 0x62D4F0) - the TLS job-context init
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_in_clone.load(std::memory_order_relaxed)) {
                    return;
                }
                log::get()->info("CloneTest: JobCtxInit(ctx=0x{:X} thread={})", r.ecx,
                                 GetCurrentThreadId());
            }
        };

        // The clone test itself: scan for character objects and invoke their clone method.
        // May hang the calling (camera) thread - the LoopProbe sampler runs in parallel and
        // records the frozen EIP, which pinpoints the deadlock.
        bool g_clone_attempted = false;

        // Per-page scan for the AI-world object (vtable in the AI-world vtable window).
        static void scan_world_page(std::uintptr_t ba, std::uintptr_t end, std::uintptr_t *out,
                                    int max, int &found_n) {
            __try {
                for (std::uintptr_t p = ba; p <= end && found_n < max; p += 4) {
                    const auto vt = mem::read<std::uint32_t>(p);
                    if (vt >= 0x01E5C900 && vt <= 0x01E5CA00) {
                        out[found_n++] = p;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        // Generic per-page scan for objects whose first dword falls in a vtable window.
        static void scan_vt_page(std::uintptr_t ba, std::uintptr_t end, std::uint32_t lo,
                                 std::uint32_t hi, std::uintptr_t *out, int max, int &found_n) {
            __try {
                for (std::uintptr_t p = ba; p <= end && found_n < max; p += 4) {
                    const auto vt = mem::read<std::uint32_t>(p);
                    if (vt >= lo && vt <= hi) {
                        out[found_n++] = p;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        // Per-page scan for FULL character bodies (the ghost module's exact criteria).
        static void scan_body_page(std::uintptr_t ba, std::uintptr_t end, std::uintptr_t *out,
                                   int max, int &found_n) {
            __try {
                for (std::uintptr_t p = ba; p <= end && found_n < max; p += 4) {
                    if (mem::read<std::uint32_t>(p) != 0x01E4CE90) {
                        continue;
                    }
                    if (mem::read<std::uint32_t>(p + 0x68) != 0x04DD5F8C) {
                        continue;
                    }
                    const auto f = mem::read<float>(p + 0x7C);
                    if (f < -0.52F || f > -0.48F) {
                        continue;
                    }
                    if (mem::read<std::uint16_t>(p + 0x66) < 16) {
                        continue;
                    }
                    out[found_n++] = p;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        // The engine's factory with a registry key: FUN_00a201a0(classId, keyLo, keyHi, 0).
        static void *spawn_keyed_helper(std::uintptr_t fn, std::uint32_t id, std::uint32_t k1,
                                        std::uint32_t k2) {
            __try {
                using SpawnFn = void *(__cdecl *)(std::uint32_t, std::uint32_t, std::uint32_t,
                                                  std::uint32_t);
                return reinterpret_cast<SpawnFn>(fn)(id, k1, k2, 0);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return nullptr;
            }
        }

        // FUN_00a0bb40(keyLo, keyHi, obj, 0) - the object-registry insert.
        static int registry_helper(std::uintptr_t fn, std::uint32_t k1, std::uint32_t k2,
                                   void *obj) {
            __try {
                using RegFn = void(__cdecl *)(std::uint32_t, std::uint32_t, void *, std::uint32_t);
                reinterpret_cast<RegFn>(fn)(k1, k2, obj, 0);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // FUN_0043a190(world, entity) - register the entity with the world's spawn system.
        static int attach_helper(std::uintptr_t fn, std::uintptr_t world, void *obj) {
            __try {
                using AttachFn = void(__cdecl *)(std::uintptr_t, void *);
                reinterpret_cast<AttachFn>(fn)(world, obj);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        auto find_player_ctl(const Vec3 &pos) -> std::uintptr_t;

        // The async clone call (vtable+0x8 = FUN_006def40): serialize + engine-side deserialize
        // = the engine's complete spawn recipe (renderable). SEH-guarded pure helper.
        static DWORD          g_exc_code = 0;
        static std::uintptr_t g_exc_addr = 0;

        static int clone_filter(const unsigned long code, EXCEPTION_POINTERS *info) {
            g_exc_code = code;
            g_exc_addr = (info != nullptr && info->ExceptionRecord != nullptr)
                             ? reinterpret_cast<std::uintptr_t>(
                                   info->ExceptionRecord->ExceptionAddress)
                             : 0;
            return EXCEPTION_EXECUTE_HANDLER;
        }

        static int async_clone_call_helper(std::uintptr_t p, void **out) {
            __try {
                const auto vt = static_cast<std::uintptr_t>(mem::read<std::uint32_t>(p));
                using CloneFn = void *(__thiscall *)(void *, void *, void *);
                const auto fn = reinterpret_cast<CloneFn>(mem::read<std::uintptr_t>(vt + 0x08));
                *out = fn(reinterpret_cast<void *>(p), nullptr, nullptr);
                return 0;
            } __except (clone_filter(GetExceptionCode(), GetExceptionInformation())) {
                return static_cast<int>(g_exc_code);
            }
        }

        static int clone_call_helper(std::uintptr_t p, void **out) {
            __try {
                const auto vt = static_cast<std::uintptr_t>(mem::read<std::uint32_t>(p));
                using CloneFn = void *(__thiscall *)(void *, void *, void *);
                const auto fn = reinterpret_cast<CloneFn>(mem::read<std::uintptr_t>(vt + 0x0C));
                *out = fn(reinterpret_cast<void *>(p), nullptr, nullptr);
                return 0;
            } __except (clone_filter(GetExceptionCode(), GetExceptionInformation())) {
                return static_cast<int>(g_exc_code);
            }
        }

        // === CloneLive (dev one-shot, 2026-10-08): the never-run visibility test for the sync
        // clone. Finds the player's character-class object (vt 0x01E4A128 / 0x01E64680 - the
        // "1-3 cloneable" objects = player + story NPCs), calls the proven clone slot
        // (vtable+0xC = FUN_006deff0), logs a source-vs-clone field diff, then the user walks
        // away and looks back: does a second body stand where they were?
        std::atomic<bool> g_clone_live {false};
        int              g_clone_live_stage  = 0; // 0 idle/armed, 1 scan, 2 clone, 3 recheck, 4 done
        std::uintptr_t   g_clone_live_cursor = 0;
        std::uintptr_t   g_clone_live_src    = 0;
        std::uintptr_t   g_clone_live_obj    = 0;
        float            g_clone_live_bestd  = 1.0e9F;
        std::int64_t     g_clone_live_t0     = 0;

        static void clone_live_fields(const char *tag, std::uintptr_t b) {
            if (!readable(b, 0x60)) {
                log::get()->info("{} 0x{:X}: unreadable", tag, b);
                return;
            }
            log::get()->info(
                "{} 0x{:X}: vt=0x{:X} ch={} f7c={:.2f} f50=0x{:X} f54=0x{:X} f58=0x{:X} "
                "f5C=0x{:X} f60=0x{:X}",
                tag, b, static_cast<std::uintptr_t>(mem::read<std::uint32_t>(b)),
                mem::read<std::uint16_t>(b + 0x66), static_cast<double>(mem::read<float>(b + 0x7C)),
                mem::read<std::uint32_t>(b + 0x50), mem::read<std::uint32_t>(b + 0x54),
                mem::read<std::uint32_t>(b + 0x58), mem::read<std::uint32_t>(b + 0x5C),
                mem::read<std::uint32_t>(b + 0x60));
        }

        struct CloneLiveCand {
            std::uintptr_t addr = 0;
            std::uint32_t  vt   = 0;
            float          x    = 0.0F;
            float          y    = 0.0F;
            float          d    = 0.0F;
            std::uint16_t  ch   = 0;
            float          f7c  = 0.0F;
            std::uint32_t  f50  = 0;
        };
        CloneLiveCand g_clone_live_cands[32];
        int           g_clone_live_cand_n = 0;
        int           g_clone_live_try    = 0; // next attempt index into the sorted order
        std::int64_t  g_clone_live_gap    = 0; // pacing between clone attempts
        bool          g_clone_live_scan_ran = false;

        // v4: scan for ENTITY BODIES (vt 0x01E4CE90 = class "Entity" - the bodies, incl. the
        // player's). Their vtable+0xC = FUN_0052A980 = the node clone (instantiate + deep copy),
        // the same primitive the streamer uses to create nodes during gameplay.
        std::uintptr_t g_clone_live_ghost = 0;

        static void clone_live_scan(std::uintptr_t lo, std::uintptr_t hi, const Vec3 &player) {
            __try {
                for (auto p = lo; p + 4 <= hi; p += 4) {
                    if (g_clone_live_cand_n >= 32) {
                        break;
                    }
                    const auto vt = mem::read<std::uint32_t>(p);
                    if (vt != 0x01E4CE90U) {
                        continue;
                    }
                    if (p == g_clone_live_ghost) {
                        continue; // never clone the pinned ghost
                    }
                    const auto ch = readable(p + 0x66, 2) ? mem::read<std::uint16_t>(p + 0x66) : 0;
                    if (ch < 16) {
                        continue; // real bodies only
                    }
                    float bx = 0.0F;
                    float by = 0.0F;
                    if (readable(p + 0x40, 8)) {
                        bx = mem::read<float>(p + 0x40);
                        by = mem::read<float>(p + 0x44);
                    }
                    if (!(bx > -20000.0F && bx < 20000.0F && by > -20000.0F && by < 20000.0F)) {
                        continue;
                    }
                    const auto dx = bx - player.x;
                    const auto dy = by - player.y;
                    auto      &c  = g_clone_live_cands[g_clone_live_cand_n++];
                    c.addr = p;
                    c.vt   = vt;
                    c.x    = bx;
                    c.y    = by;
                    c.d    = std::sqrt(dx * dx + dy * dy);
                    c.ch   = static_cast<std::uint16_t>(ch);
                    c.f7c  = readable(p + 0x7C, 4) ? mem::read<float>(p + 0x7C) : 0.0F;
                    c.f50  = readable(p + 0x50, 4) ? mem::read<std::uint32_t>(p + 0x50) : 0;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        // Order attempts: healthy-looking (children > 0) first, then by distance.
        int g_clone_live_order[32];

        static auto clone_live_score(const CloneLiveCand &c) -> float {
            return c.d - (c.ch > 0 ? 1.0e6F : 0.0F);
        }

        // The streamer's spawn completion (from the crowd spawn recipe): activate = set flags
        // +0x50 |= 4|8|0x800000 then register spatially; job flush = process the posted job.
        static int activate_helper(std::uintptr_t node) {
            __try {
                using ActFn = void(__thiscall *)(void *);
                reinterpret_cast<ActFn>(g_exe_base + 0x126590)(reinterpret_cast<void *>(node));
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        static int jobflush_helper() {
            __try {
                using FlushFn = void(__cdecl *)();
                reinterpret_cast<FlushFn>(g_exe_base + 0x62E820)();
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // === SpawnTest (dev one-shot): call the streamer's own spawn with the captured crowd
        // template hash - the exact mid-game NPC creation path the engine uses itself.
        // FUN_005FD730(hash) stdcall -> new node (template slot -> vtable+0xC clone ->
        // FUN_00526590 activate -> FUN_00a2e820 flush).
        std::atomic<bool> g_spawn_test {false};
        bool              g_spawn_test_done = false;
        std::atomic<int>  g_spawnwatch_logs {0};

        static void *spawn_hash_helper(std::uint32_t mgr, std::uint32_t key) {
            __try {
                // FUN_005FD730 is __thiscall: ECX = the spawn manager, the key pointer on the
                // stack (ret 4). Earlier attempts passed a garbage ECX -> lookup always failed.
                using SpawnFn = void *(__thiscall *)(void *, std::uint32_t);
                return reinterpret_cast<SpawnFn>(g_exe_base + 0x1FD730)(
                    reinterpret_cast<void *>(mgr), key);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return nullptr;
            }
        }

        // read-only watcher for the streamer spawn calls. v3: capture the spawn TEMPLATE too.
        // FUN_005FD730 is (ECX=mgr, key on stack): slot = FUN_005fac60(mgr,key) walks the mgr's
        // transient pass table (array at mgr+0x94, u16 count at mgr+0x9a; match = the slot value
        // at +4 is IN the key's id-array (ptr at key+0x1C, u16 count at key+0x22)). Slot[0] = P
        // (validity: P[+8] must be negative), P[0] = Q = the TEMPLATE object; the engine's slow
        // path spawns via [[Q]+0xC](Q,0,0) + activate + flush. mgr + its table are TRANSIENT
        // (die with the pass) -> the replay must clone the captured Q directly.
        std::atomic<std::uint32_t> g_spawn_last_mgr {0};
        std::atomic<std::uint32_t> g_spawn_last_key {0};

        struct SpawnV3 {
            std::uint32_t mgr = 0;
            std::uint32_t key = 0;
            std::uint32_t caller_rva = 0;
            std::uint16_t arr_cnt = 0;
            std::uint32_t arr[64] = {};
            std::uint32_t kv = 0;
            std::int32_t  pv = 0;
            std::uint32_t q = 0;
            std::uint32_t q_vt = 0;
            std::uint32_t q_fn = 0;
            std::uint16_t q_ch = 0; // v8: the record's child count (full-body records = ch>=16)
            int           matches = 0;
            bool          found = false;
            bool          body = false;
            bool          fallback = false;
            std::uint32_t tab = 0;
            std::uint32_t n = 0;
            int           mode = -1; // mode byte *[0x2AC1E68] at call time (-1 = ptr null)
        };
        SpawnV3 g_spawn_v3;      // best capture (for the test)
        SpawnV3 g_spawn_v3_last; // most recent call (for logging)

        static void spawn_v3_capture_try(std::uint32_t mgr, std::uint32_t key,
                                         std::uint32_t caller) {
            __try {
                SpawnV3 c {};
                c.mgr = mgr;
                c.key = key;
                c.caller_rva = caller ? static_cast<std::uint32_t>(caller - g_exe_base) : 0;
                {
                    const auto mp = mem::read<std::uint32_t>(g_exe_base + 0x26C1E68);
                    if (mp) {
                        c.mode = static_cast<int>(mem::read<std::uint8_t>(mp));
                    }
                }
                if (key != 0 && readable(key, 0x40)) {
                    const auto arrp = mem::read<std::uint32_t>(key + 0x1C);
                    const auto cnt = mem::read<std::uint16_t>(key + 0x22);
                    if (arrp && cnt && cnt <= 64 && readable(arrp, cnt * 4)) {
                        c.arr_cnt = cnt;
                        for (std::uint32_t i = 0; i < cnt; ++i) {
                            c.arr[i] = mem::read<std::uint32_t>(arrp + i * 4);
                        }
                    }
                    c.tab = mem::read<std::uint32_t>(mgr + 0x94);
                    c.n = mem::read<std::uint16_t>(mgr + 0x9A);
                    if (c.tab && c.n && c.n <= 64 && readable(c.tab, c.n * 8)) {
                        for (std::uint32_t i = 0; i < c.n; ++i) {
                            const auto kv = mem::read<std::uint32_t>(c.tab + i * 8 + 4);
                            bool       match = c.arr_cnt != 0;
                            if (match) {
                                match = false;
                                for (std::uint32_t j = 0; j < c.arr_cnt; ++j) {
                                    if (c.arr[j] == kv) {
                                        match = true;
                                        break;
                                    }
                                }
                            }
                            if (!match) {
                                continue;
                            }
                            const auto P = mem::read<std::uint32_t>(c.tab + i * 8);
                            if (!P || !readable(P, 0xC)) {
                                continue;
                            }
                            const auto Q = mem::read<std::uint32_t>(P);
                            if (!Q || !readable(Q, 8)) {
                                continue;
                            }
                            const auto    vt = mem::read<std::uint32_t>(Q);
                            std::uint32_t fn = 0;
                            if (vt && readable(vt + 0xC, 4)) {
                                fn = mem::read<std::uint32_t>(vt + 0xC);
                            }
                            ++c.matches;
                            c.kv = kv;
                            c.pv = static_cast<std::int32_t>(mem::read<std::uint32_t>(P + 8));
                            c.q = Q;
                            c.q_vt = vt;
                            c.q_fn = fn;
                            c.q_ch = readable(Q + 0x66, 2)
                                         ? mem::read<std::uint16_t>(Q + 0x66)
                                         : 0;
                            c.found = true;
                            c.body = (vt == 0x01E4CE90U);
                            if (c.body) {
                                break; // prefer a body-class template
                            }
                        }
                    }
                    // FUN_005fac60's FALLBACK when the table is empty / has no match: the slot
                    // at mgr+0x80. Observed live: every streamer manager takes exactly this
                    // path (tables empty; the fallback record holds the Entity template).
                    if (!c.found) {
                        const auto P = mem::read<std::uint32_t>(mgr + 0x80);
                        if (P && readable(P, 0xC)) {
                            const auto Q = mem::read<std::uint32_t>(P);
                            if (Q && readable(Q, 8)) {
                                const auto    vt = mem::read<std::uint32_t>(Q);
                                std::uint32_t fn = 0;
                                if (vt && readable(vt + 0xC, 4)) {
                                    fn = mem::read<std::uint32_t>(vt + 0xC);
                                }
                                c.pv = static_cast<std::int32_t>(mem::read<std::uint32_t>(P + 8));
                                c.q = Q;
                                c.q_vt = vt;
                                c.q_fn = fn;
                                c.q_ch = readable(Q + 0x66, 2)
                                             ? mem::read<std::uint16_t>(Q + 0x66)
                                             : 0;
                                c.found = true;
                                c.body = (vt == 0x01E4CE90U);
                                c.fallback = true;
                            }
                        }
                    }
                }
                g_spawn_v3_last = c;
                // best-for-test v8: maximise the record's child count (the fullest record wins);
                // tie-break to the Entity class.
                if (c.found) {
                    const bool better =
                        !g_spawn_v3.found || (c.q_ch > g_spawn_v3.q_ch) ||
                        (c.q_ch == g_spawn_v3.q_ch && c.body && !g_spawn_v3.body);
                    if (better) {
                        g_spawn_v3 = c;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        static void spawn_v3_log() {
            const auto &c = g_spawn_v3_last;
            static int           full_logs = 0;
            static std::uint32_t last_sig = ~0U;
            std::uint32_t sig = (c.found ? 1U : 0U) | (c.fallback ? 2U : 0U) |
                                (c.body ? 4U : 0U);
            sig = sig * 31U + c.q_vt;
            sig = sig * 31U + c.q_fn;
            if (full_logs >= 12 && sig == last_sig) {
                return;
            }
            ++full_logs;
            last_sig = sig;
            log::get()->info(
                "SpawnWatch: call#{} mgr=0x{:X} key=0x{:X} caller=+0x{:X} mode={} arr_cnt={} "
                "tab=0x{:X} n={} fb={} found={} kv=0x{:X} pv={} q=0x{:X} vt=0x{:X} fn=0x{:X} "
                "ch={} matches={}",
                full_logs, c.mgr, c.key, c.caller_rva, c.mode, c.arr_cnt, c.tab, c.n,
                c.fallback ? 1 : 0, c.found ? 1 : 0, c.kv, c.pv, c.q, c.q_vt, c.q_fn, c.q_ch,
                c.matches);
        }

        static void spawn_live_do(std::uint32_t mgr, std::uint32_t key); // v4 (defined below)
        static void spawn_edward_do(std::uint32_t mgr, std::uint32_t key); // v6 (defined below)

        struct ProbeSpawnCall {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                const auto key = mem::read<std::uint32_t>(r.esp + 4);
                const auto caller = mem::read<std::uint32_t>(r.esp);
                const auto mgr = static_cast<std::uint32_t>(r.ecx);
                g_spawn_last_mgr.store(mgr, std::memory_order_relaxed);
                g_spawn_last_key.store(key, std::memory_order_relaxed);
                spawn_v3_capture_try(mgr, key, caller);
                const auto n = g_spawnwatch_logs.fetch_add(1, std::memory_order_relaxed);
                if (n < 200) {
                    log::get()->info("SpawnWatch: streamer spawn mgr=0x{:X} key=0x{:X}", mgr, key);
                }
                spawn_v3_log();
                // v4: in-hook spawn test (armed one-shot, clone-path calls only). The hook
                // runs ON the streaming thread inside the pass - the context the engine
                // itself spawns in, and the only one where the clone path survives.
                if (g_spawn_test.load(std::memory_order_relaxed) && !g_spawn_test_done &&
                    g_spawn_v3_last.mode == 0) {
                    // v16.5: clone EDWARD (v6 recipe) + attach. The SOURCE must be verified:
                    // it must have real part definitions (>=0x10000) and must NEVER be one of
                    // our own clones (clones of clones lose the part defs).
                    const bool edward_ok =
                        g_act_node != 0 && readable(g_act_node, 4) &&
                        mem::read<std::uint32_t>(g_act_node) == 0x01E4CE90U;
                    const bool world_ok =
                        (std::fabs(g_last_pos.x) + std::fabs(g_last_pos.y) +
                         std::fabs(g_last_pos.z)) > 20.0F;
                    bool src_ok = false;
                    if (edward_ok && world_ok && g_spawn_v3_last.body) {
                        src_ok = (g_act_node != g_spawnq_obj && g_act_node != g_v16_obj);
                    }
                    if (g_spawn_v3_last.body && world_ok) {
                        g_spawn_test_done = true;
                        if (edward_ok && src_ok) {
                            spawn_edward_do(mgr, key);
                        } else {
                            // v18.2: no live Edward available - the plain record clone still runs
                            // the graphics attach + the record-handle share.
                            spawn_live_do(mgr, key);
                        }
                    } else {
                        static int skipped = 0;
                        if (skipped < 8) {
                            ++skipped;
                            log::get()->info(
                                "SpawnTest v18.2: skipping call (body={} edward={} world={} src={})",
                                g_spawn_v3_last.body ? 1 : 0, edward_ok ? 1 : 0, world_ok ? 1 : 0,
                                src_ok ? 1 : 0);
                        }
                    }
                }
            }
        };

        mem::MidHook g_probe_spawn_call;

        // FUN_00503600 = the FULL deep copy: allocate via desc 0x275AFD0 + node clone FUN_0052A980
        // + STATE BLOCK 0x100..0x148. The node-only clone (vt+0xC = FUN_0052A980) that we called
        // before skipped the state - the likely reason the copy never rendered. thiscall(source,0,0).
        static int deep_copy_helper(std::uintptr_t source, void **out) {
            __try {
                using DeepFn = void *(__thiscall *)(void *, std::uint32_t, std::uint32_t);
                *out = reinterpret_cast<DeepFn>(g_exe_base + 0x103600)(
                    reinterpret_cast<void *>(source), 0U, 0U);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // FUN_006deff0 = the engine's own sync-clone entry (allocate via desc [0x2799098] + setup
        // post + FUN_00503600 deep copy incl. the state block). thiscall(source, 0, 0).
        static int sync_clone_helper(std::uintptr_t source, void **out) {
            __try {
                using ClFn = void *(__thiscall *)(void *, std::uint32_t, std::uint32_t);
                *out = reinterpret_cast<ClFn>(g_exe_base + 0x2DEFF0)(
                    reinterpret_cast<void *>(source), 0U, 0U);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // --- SpawnTest v3: clone the captured TEMPLATE + materialization watch ---
        std::int64_t   g_spawnq_t0 = 0;
        int            g_spawnq_stage = 0; // 0 idle, 1 watching (1s/4s/10s), 2 done
        int            g_spawnq_step = 0;
        bool           g_spawnq_pending = false; // v5: placement deferred until a valid position
        bool           g_v16_done = true;
        std::uint32_t  g_seh_code = 0;  // last SEH code from the clone helpers
        std::uint32_t  g_seh_addr = 0;  // last faulting address (absolute)

        static int lookup_helper(std::uint32_t mgr, std::uint32_t key, void **out) {
            __try {
                using LookupFn = void *(__thiscall *)(void *, std::uint32_t);
                *out = reinterpret_cast<LookupFn>(g_exe_base + 0x1FAC60)(
                    reinterpret_cast<void *>(mgr), key);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        static int template_clone_helper(std::uintptr_t q, void **out) {
            __try {
                const auto vt = mem::read<std::uint32_t>(q);
                if (!vt || !readable(vt + 0xC, 4)) {
                    return 2;
                }
                const auto fn = mem::read<std::uint32_t>(vt + 0xC);
                if (fn < 0x401000U || fn > 0x2400000U) {
                    return 3;
                }
                using ClFn = void *(__thiscall *)(void *, std::uint32_t, std::uint32_t);
                *out = reinterpret_cast<ClFn>(fn)(reinterpret_cast<void *>(q), 0U, 0U);
                return 0;
            } __except (g_seh_code = GetExceptionCode(),
                        g_seh_addr = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(
                            GetExceptionInformation()->ExceptionRecord->ExceptionAddress)),
                        EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        static void spawnq_fields(const char *tag, std::uintptr_t b) {
            if (!readable(b, 0x100)) {
                log::get()->info("{} 0x{:X}: unreadable", tag, b);
                return;
            }
            log::get()->info(
                "{} 0x{:X}: vt=0x{:X} ch={} f7c={:.2f} f50=0x{:X} f54=0x{:X} f5C=0x{:X} f60=0x{:X} "
                "fAC=0x{:X} fB0=0x{:X} fD4=0x{:X} fE8=0x{:X}",
                tag, b, static_cast<std::uintptr_t>(mem::read<std::uint32_t>(b)),
                mem::read<std::uint16_t>(b + 0x66), static_cast<double>(mem::read<float>(b + 0x7C)),
                mem::read<std::uint32_t>(b + 0x50), mem::read<std::uint32_t>(b + 0x54),
                mem::read<std::uint32_t>(b + 0x5C), mem::read<std::uint32_t>(b + 0x60),
                mem::read<std::uint32_t>(b + 0xAC), mem::read<std::uint32_t>(b + 0xB0),
                mem::read<std::uint32_t>(b + 0xD4), mem::read<std::uint32_t>(b + 0xE8));
        }

        // v4: the in-hook spawn. Called from the spawn hook = ON the streaming thread, inside
        // the pass - the only context where the clone path is proven to work (cold calls fault
        // in the job/queue container growth). Re-runs the engine's own spawn call and captures
        // its return (the clone), then moves it 2.5 m east with the usual watch.
        static int spawn_live_helper(std::uint32_t mgr, std::uint32_t key, void **out) {
            __try {
                using SpawnFn = void *(__thiscall *)(void *, std::uint32_t);
                *out = reinterpret_cast<SpawnFn>(g_exe_base + 0x1FD730)(
                    reinterpret_cast<void *>(mgr), key);
                return 0;
            } __except (g_seh_code = GetExceptionCode(),
                        g_seh_addr = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(
                            GetExceptionInformation()->ExceptionRecord->ExceptionAddress)),
                        EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // v16.2: the variant factory thunk - NOTE the corrected call shape (decoded from the
        // dispatcher case at 0x91F68A): the definition goes ON THE STACK (cdecl); the thunk sets
        // its own ECX (0x27E1CF0) and tail-calls the wrapper -> FUN_0085F9C0(def).
        static std::uintptr_t factory_call(std::uintptr_t entry_va, std::uint32_t def) {
            __try {
                using Fn = std::uintptr_t(__cdecl *)(std::uint32_t);
                return reinterpret_cast<Fn>(entry_va)(def);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 0;
            }
        }

        static std::uintptr_t graphics_lookup(std::uint32_t def, const char **which) {
            const std::uintptr_t entries[6] = {g_exe_base + 0x44A040, g_exe_base + 0x44A050,
                                               g_exe_base + 0x44A060, g_exe_base + 0x44A070,
                                               g_exe_base + 0x44A080, g_exe_base + 0x44A0F0};
            const char        *names[6]   = {"A040", "A050", "A060", "A070", "A080", "A0F0"};
            for (int i = 0; i < 6; ++i) {
                const auto g = factory_call(entries[i], def);
                if (g) {
                    *which = names[i];
                    return g;
                }
            }
            *which = "-";
            return 0;
        }

        // Pure SEH poke helper (keeps __try out of functions that also contain logging).
        static int poke_u32(std::uintptr_t addr, std::uint32_t value) {
            __try {
                *reinterpret_cast<std::uint32_t *>(addr) = value;
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        static void spawn_live_do(std::uint32_t mgr, std::uint32_t key) {
            log::get()->info(
                "SpawnTest v4: IN-HOOK spawn mgr=0x{:X} key=0x{:X} - running the engine's own "
                "call on the streaming thread",
                mgr, key);
            void      *obj = nullptr;
            const auto rc  = spawn_live_helper(mgr, key, &obj);
            log::get()->info("SpawnTest v4: LIVESPAWN rc={} obj=0x{:X} seh=0x{:X} at+0x{:X}", rc,
                             reinterpret_cast<std::uintptr_t>(obj), g_seh_code,
                             g_seh_addr ? static_cast<std::uint32_t>(g_seh_addr - g_exe_base) : 0);
            if (rc != 0 || obj == nullptr) {
                return;
            }
            const auto o = reinterpret_cast<std::uintptr_t>(obj);
            spawnq_fields("SpawnTest v4: obj", o);
            const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
            LARGE_INTEGER nowt {};
            QueryPerformanceCounter(&nowt);
            const bool pos_fresh =
                g_last_pos_t0 != 0 && freq > 0 && (nowt.QuadPart - g_last_pos_t0) <= freq * 3;
            const bool pos_valid =
                (std::fabs(g_last_pos.x) + std::fabs(g_last_pos.y) + std::fabs(g_last_pos.z)) >
                20.0F;
            if (pos_fresh && pos_valid && readable(o + 0x10, 0x40)) {
                alignas(16) float mm[16];
                std::memcpy(mm, reinterpret_cast<const void *>(o + 0x10), sizeof(mm));
                mm[12] = g_last_pos.x + 2.5F;
                mm[13] = g_last_pos.y;
                mm[14] = g_last_pos.z;
                mm[15] = 1.0F;
                std::memcpy(reinterpret_cast<void *>(o + 0x10), mm, sizeof(mm));
                log::get()->info("SpawnTest v5: placed at ({:.1f},{:.1f}) - LOOK 2.5 m EAST",
                                 static_cast<double>(mm[12]), static_cast<double>(mm[13]));
            } else {
                g_spawnq_pending = true;
                log::get()->info("SpawnTest v5: placement DEFERRED (fresh={} valid={}) - placed "
                                 "next to the player as soon as the position is known",
                                 pos_fresh ? 1 : 0, pos_valid ? 1 : 0);
            }
            g_spawnq_obj = o;
            g_spawnq_step = 0;
            g_hswap_clone = o;
            g_hswap_done = false;
            g_hswap_cursor = 0x30000000;
            LARGE_INTEGER t {};
            QueryPerformanceCounter(&t);
            g_spawnq_t0 = t.QuadPart;
            g_spawnq_stage = 1;
        }

        // v16.2: run the attach for an object. Corrected call shape: the def goes on the stack
        // (cdecl), all kind-variants tried. Body first (+0x50 then +0x54), then parts.
        static void attach_graphics_try(std::uintptr_t o) {
            const std::uint32_t def50 =
                readable(o + 0x50, 4) ? mem::read<std::uint32_t>(o + 0x50) : 0U;
            const std::uint32_t def54 =
                readable(o + 0x54, 4) ? mem::read<std::uint32_t>(o + 0x54) : 0U;
            const char *which = "-";
            std::uintptr_t g1 = def50 ? graphics_lookup(def50, &which) : 0;
            log::get()->info("v16.2 ATTACH: body def50=0x{:X} def54=0x{:X} -> graphic=0x{:X} via {}",
                             def50, def54, static_cast<std::uintptr_t>(g1), which);
            if (!g1 && def54) {
                g1 = graphics_lookup(def54, &which);
                log::get()->info("v16.2 ATTACH: retry with def54 -> 0x{:X} via {}",
                                 static_cast<std::uintptr_t>(g1), which);
            }
            if (g1) {
                poke_u32(o + 0xAC, static_cast<std::uint32_t>(g1));
                poke_u32(o + 0xB0, static_cast<std::uint32_t>(g1));
            }
            const auto arr  = mem::read<std::uint32_t>(o + 0x60);
            const auto n    = mem::read<std::uint16_t>(o + 0x66);
            int        done = 0;
            if (arr && n && n < 64 && readable(arr, static_cast<std::size_t>(n) * 4)) {
                for (std::uint32_t i = 0; i < n && done < 32; ++i) {
                    const auto kid = mem::read<std::uint32_t>(arr + i * 4);
                    if (!kid || !readable(kid + 0x58, 4)) {
                        continue;
                    }
                    const auto kdef = mem::read<std::uint32_t>(kid + 0x50);
                    if (!kdef) {
                        continue;
                    }
                    const char *kw = "-";
                    const auto  kg = graphics_lookup(kdef, &kw);
                    if (kg) {
                        poke_u32(kid + 0xAC, static_cast<std::uint32_t>(kg));
                        poke_u32(kid + 0xB0, static_cast<std::uint32_t>(kg));
                        ++done;
                        log::get()->info("v16.3 ATTACH: part[{}] 0x{:X} def=0x{:X} -> 0x{:X} via {}",
                                         i, kid, kdef, static_cast<std::uintptr_t>(kg), kw);
                    }
                }
            }
            spawnq_fields("v16.3: obj after attach", o);
        }

        // v6: spawn a copy of a LIVE FULL CHARACTER (Edward's body) through the engine's own
        // pipeline. The streamer call would normally clone its record template Q - we point the
        // record at Edward for ONE invocation, run the engine's own slow path ourselves (SEH-safe),
        // then restore the record BEFORE the engine's own call proceeds. Our call's return = the
        // engine-made clone of a full character.
        static void spawn_edward_do(std::uint32_t mgr, std::uint32_t key) {
            const auto P = mem::read<std::uint32_t>(mgr + 0x80);
            if (!P || !readable(P, 8)) {
                log::get()->warn("SpawnTest v6: no record at mgr+0x80 (mgr=0x{:X})", mgr);
                return;
            }
            const auto Q = mem::read<std::uint32_t>(P);
            log::get()->info(
                "SpawnTest v6: SUBSTITUTE record P=0x{:X} Q=0x{:X} -> Edward 0x{:X} (ch={})", P, Q,
                g_act_node, mem::read<std::uint16_t>(g_act_node + 0x66));
            if (poke_u32(P, static_cast<std::uint32_t>(g_act_node)) != 0) {
                log::get()->warn("SpawnTest v6: record write faulted");
                return;
            }
            // The engine's own slow path now clones EDWARD. Guarded - an AV is caught, not fatal.
            void      *obj = nullptr;
            const auto rc  = spawn_live_helper(mgr, key, &obj);
            // Restore immediately so the engine's own call (which runs right after this hook)
            // sees the original record again and behaves normally.
            const auto rrc = poke_u32(P, Q);
            log::get()->info(
                "SpawnTest v6: EDWARD CLONE rc={} obj=0x{:X} seh=0x{:X} at+0x{:X} (restore={})",
                rc, reinterpret_cast<std::uintptr_t>(obj), g_seh_code,
                g_seh_addr ? static_cast<std::uint32_t>(g_seh_addr - g_exe_base) : 0, rrc);
            if (rc != 0 || obj == nullptr) {
                return;
            }
            const auto o = reinterpret_cast<std::uintptr_t>(obj);
            spawnq_fields("SpawnTest v6: obj", o);
            const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
            LARGE_INTEGER nowt {};
            QueryPerformanceCounter(&nowt);
            const bool pos_fresh =
                g_last_pos_t0 != 0 && freq > 0 && (nowt.QuadPart - g_last_pos_t0) <= freq * 3;
            const bool pos_valid =
                (std::fabs(g_last_pos.x) + std::fabs(g_last_pos.y) + std::fabs(g_last_pos.z)) >
                20.0F;
            if (pos_fresh && pos_valid && readable(o + 0x10, 0x40)) {
                alignas(16) float mm[16];
                std::memcpy(mm, reinterpret_cast<const void *>(o + 0x10), sizeof(mm));
                mm[12] = g_last_pos.x + 2.5F;
                mm[13] = g_last_pos.y;
                mm[14] = g_last_pos.z;
                mm[15] = 1.0F;
                std::memcpy(reinterpret_cast<void *>(o + 0x10), mm, sizeof(mm));
                log::get()->info("SpawnTest v6: placed at ({:.1f},{:.1f}) - LOOK 2.5 m EAST",
                                 static_cast<double>(mm[12]), static_cast<double>(mm[13]));
            } else {
                g_spawnq_pending = true;
                log::get()->info("SpawnTest v6: placement DEFERRED (fresh={} valid={})",
                                 pos_fresh ? 1 : 0, pos_valid ? 1 : 0);
            }
            // v16.1: the graphics attach is DEFERRED to the watch step (+4 s) - at creation the
            // definition is still the static default (0x1FD2xxxx); Edward's real one
            // (0x5FDA027C) only arrives with the engine's fill (~1 s).
            g_v16_obj  = o;
            g_v16_done = false;
            g_spawnq_obj = o;
            g_spawnq_step = 0;
            g_hswap_clone = o;
            g_hswap_done = false;
            g_hswap_cursor = 0x30000000;
            LARGE_INTEGER t {};
            QueryPerformanceCounter(&t);
            g_spawnq_t0 = t.QuadPart;
            g_spawnq_stage = 1;
        }

        static void spawn_test_tick(const Vec3 &player) {
            // v4: the spawn runs INSIDE the live spawn hook (streaming thread, in-pass - the
            // only context where the clone path is proven to work). This tick only announces
            // arming; the hook sets g_spawn_test_done when it fires.
            (void)player;
            static bool logged = false;
            if (!logged) {
                logged = true;
                log::get()->info("SpawnTest v4: armed - waiting for a live clone-path call "
                                 "(mode=0); the spawn runs in-hook and is placed 2.5 m east");
            }
        }

        // v5: the BANKED async-clone protocol (never executed on a free-roam save): async slot
        // (vtable+0x8) = serialize source + post job -> the engine deserializes a complete,
        // renderable copy. Position-disambiguation: offset the source +3 m, call, restore; the
        // copy appears near the +3 m spot and a body-scan finds it.
        std::int64_t g_async_wait_qpc = 0;
        float        g_async_spot[3]  = {};
        bool         g_async_pending  = false;
        std::uintptr_t g_async_src    = 0;

        static void clone_live_scan_spot(std::uintptr_t lo, std::uintptr_t hi, const float *spot,
                                         std::uintptr_t src, CloneLiveCand *out, int &out_n,
                                         int max_n) {
            __try {
                for (auto p = lo; p + 4 <= hi; p += 4) {
                    if (out_n >= max_n) {
                        break;
                    }
                    if (p == src) {
                        continue;
                    }
                    const auto vt = mem::read<std::uint32_t>(p);
                    if (vt != 0x01E4CE90U) {
                        continue;
                    }
                    const auto ch = readable(p + 0x66, 2) ? mem::read<std::uint16_t>(p + 0x66) : 0;
                    if (ch < 16) {
                        continue;
                    }
                    float bx = 0.0F;
                    float by = 0.0F;
                    if (readable(p + 0x40, 8)) {
                        bx = mem::read<float>(p + 0x40);
                        by = mem::read<float>(p + 0x44);
                    }
                    const auto dx = bx - spot[0];
                    const auto dy = by - spot[1];
                    if (dx * dx + dy * dy > 36.0F) {
                        continue; // more than 6 m from the async spawn spot
                    }
                    auto &c = out[out_n++];
                    c.addr = p;
                    c.vt   = vt;
                    c.x    = bx;
                    c.y    = by;
                    c.d    = std::sqrt(dx * dx + dy * dy);
                    c.ch   = ch;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        static void clone_live_tick(const Vec3 &player) {
            if (g_clone_live_stage == 0) {
                g_clone_live_cursor = 0x30000000;
                g_clone_live_src    = 0;
                g_clone_live_obj    = 0;
                g_clone_live_bestd  = 1.0e9F;
                g_clone_live_cand_n = 0;
                g_clone_live_try    = 0;
                g_clone_live_gap    = 0;
                g_clone_live_scan_ran = false;
                g_clone_live_ghost  = games::ac::blackflag::coop::ghost::status().body;
                log::get()->info("CloneLive: armed (player node=0x{:X}, ghost=0x{:X})", g_act_node,
                                 g_clone_live_ghost);
                if (g_act_node != 0 && readable(g_act_node, 4) &&
                    mem::read<std::uint32_t>(g_act_node) == 0x01E4CE90U) {
                    // Primary path: clone the PLAYER'S OWN body node through its real clone
                    // slot (vtable+0xC = FUN_0052A980, the node clone).
                    g_clone_live_cands[0].addr = g_act_node;
                    g_clone_live_cands[0].vt   = 0x01E4CE90U;
                    g_clone_live_cands[0].d    = 0.0F;
                    g_clone_live_cands[0].ch   = mem::read<std::uint16_t>(g_act_node + 0x66);
                    g_clone_live_cand_n        = 1;
                    g_clone_live_order[0]      = 0;
                    log::get()->info(
                        "CloneLive: primary target = the player's body 0x{:X} (ch={}) - cloning it",
                        g_act_node, g_clone_live_cands[0].ch);
                    g_clone_live_stage = 2;
                } else {
                    log::get()->info(
                        "CloneLive: no player node - falling back to a nearby body scan");
                    g_clone_live_stage = 1;
                }
            } else if (g_clone_live_stage == 1) {
                constexpr std::uintptr_t k_end = 0x50000000;
                const auto step_end = (g_clone_live_cursor + (8U << 20U)) < k_end
                                          ? g_clone_live_cursor + (8U << 20U)
                                          : k_end;
                clone_live_scan(g_clone_live_cursor, step_end, player);
                g_clone_live_cursor = step_end;
                if (g_clone_live_cursor >= k_end) {
                    for (int i = 0; i < g_clone_live_cand_n; i++) {
                        g_clone_live_order[i] = i;
                    }
                    for (int i = 1; i < g_clone_live_cand_n; i++) {
                        const int key = g_clone_live_order[i];
                        int       j   = i - 1;
                        while (j >= 0 &&
                               clone_live_score(g_clone_live_cands[g_clone_live_order[j]]) >
                                   clone_live_score(g_clone_live_cands[key])) {
                            g_clone_live_order[j + 1] = g_clone_live_order[j];
                            j--;
                        }
                        g_clone_live_order[j + 1] = key;
                    }
                    log::get()->info("CloneLive: scan done, {} candidates", g_clone_live_cand_n);
                    g_clone_live_scan_ran = true;
                    for (int i = 0; i < g_clone_live_cand_n; i++) {
                        const auto &c = g_clone_live_cands[g_clone_live_order[i]];
                        log::get()->info(
                            "CloneLive: #{} 0x{:X} vt=0x{:X} ch={} f7c={:.2f} f50=0x{:X} "
                            "({:.1f},{:.1f}) d={:.1f}",
                            i, c.addr, static_cast<std::uintptr_t>(c.vt), c.ch,
                            static_cast<double>(c.f7c), c.f50, static_cast<double>(c.x),
                            static_cast<double>(c.y), static_cast<double>(c.d));
                    }
                    g_clone_live_stage = 2;
                }
            } else if (g_clone_live_stage == 2) {
                if (g_clone_live_cand_n == 0 || g_clone_live_try >= g_clone_live_cand_n ||
                    g_clone_live_try >= 12) {
                    if (!g_clone_live_scan_ran) {
                        log::get()->info(
                            "CloneLive: primary failed - scanning for a fallback body");
                        g_clone_live_scan_ran = true;
                        g_clone_live_cand_n   = 0;
                        g_clone_live_try      = 0;
                        g_clone_live_cursor   = 0x30000000;
                        g_clone_live_stage    = 1;
                        return;
                    }
                    log::get()->warn("CloneLive: no cloneable candidate (tried {})",
                                     g_clone_live_try);
                    g_clone_live_stage = 4;
                    return;
                }
                // Pace: at most one engine call per 0.5 s (no AV bursts).
                {
                    const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                    LARGE_INTEGER now {};
                    QueryPerformanceCounter(&now);
                    if (g_clone_live_gap != 0 && freq > 0 &&
                        now.QuadPart - g_clone_live_gap < freq / 2) {
                        return;
                    }
                    g_clone_live_gap = now.QuadPart;
                }
                const auto &c = g_clone_live_cands[g_clone_live_order[g_clone_live_try]];
                // Shared placement (move 2.5 m east + activate + flush + final stage).
                auto place_clone = [&](std::uintptr_t node) {
                    g_clone_live_obj = node;
                    if (readable(g_clone_live_obj + 0x10, 0x40)) {
                        alignas(16) float mm[16];
                        std::memcpy(mm, reinterpret_cast<const void *>(g_clone_live_obj + 0x10),
                                    sizeof(mm));
                        mm[12] = player.x + 2.5F;
                        mm[13] = player.y;
                        mm[14] = player.z;
                        mm[15] = 1.0F;
                        std::memcpy(reinterpret_cast<void *>(g_clone_live_obj + 0x10), mm,
                                    sizeof(mm));
                    }
                    const auto ar = activate_helper(g_clone_live_obj);
                    const auto fr = jobflush_helper();
                    clone_live_fields("CloneLive: src", c.addr);
                    clone_live_fields("CloneLive: obj", g_clone_live_obj);
                    log::get()->info("CloneLive: placed act={} flush={} - LOOK 2.5 m EAST", ar, fr);
                    LARGE_INTEGER now2 {};
                    QueryPerformanceCounter(&now2);
                    g_clone_live_t0    = now2.QuadPart;
                    g_clone_live_stage = 3;
                };
                // v7 PRIMARY: the engine's own sync clone (FUN_006deff0: allocate via desc
                // [0x2799098] + setup post + FUN_00503600 deep copy incl. state 0x100..0x148).
                // Then the raw deep copy (null-alloc path), then the async path below.
                {
                    void      *sc  = nullptr;
                    const auto src = sync_clone_helper(c.addr, &sc);
                    log::get()->info("CloneLive: SYNCCLONE try#{} cand=0x{:X} rc={} out=0x{:X}",
                                     g_clone_live_try, c.addr, src,
                                     reinterpret_cast<std::uintptr_t>(sc));
                    if (src == 0 && sc != nullptr) {
                        place_clone(reinterpret_cast<std::uintptr_t>(sc));
                        return;
                    }
                }
                {
                    void      *dc  = nullptr;
                    const auto drc = deep_copy_helper(c.addr, &dc);
                    log::get()->info("CloneLive: DEEPCOPY try#{} cand=0x{:X} rc={} out=0x{:X}",
                                     g_clone_live_try, c.addr, drc,
                                     reinterpret_cast<std::uintptr_t>(dc));
                    if (drc == 0 && dc != nullptr) {
                        place_clone(reinterpret_cast<std::uintptr_t>(dc));
                        return;
                    }
                }
                // ASYNC protocol (banked, first run on a free-roam save): serialize + the
                // engine's own deserialize = a complete renderable copy. Non-player sources get
                // a +3 m offset for unambiguous spotting; the transform is restored right after
                // the (synchronous) serialize step.
                const bool        is_player = (c.addr == g_act_node);
                bool              offset_ok = false;
                alignas(16) float mm[16] {};
                float             saved_x = 0.0F;
                float             spot_y  = player.y;
                float             spot_z  = player.z;
                if (!is_player && readable(c.addr + 0x10, 0x40)) {
                    std::memcpy(mm, reinterpret_cast<const void *>(c.addr + 0x10), sizeof(mm));
                    saved_x = mm[12];
                    spot_y  = mm[13];
                    spot_z  = mm[14];
                    mm[12] += 3.0F;
                    std::memcpy(reinterpret_cast<void *>(c.addr + 0x10), mm, sizeof(mm));
                    offset_ok = true;
                }
                void      *out = nullptr;
                const auto rc  = async_clone_call_helper(c.addr, &out);
                if (offset_ok) {
                    mm[12] = saved_x;
                    std::memcpy(reinterpret_cast<void *>(c.addr + 0x10), mm, sizeof(mm));
                }
                log::get()->info(
                    "CloneLive: ASYNC try#{} cand=0x{:X} ch={} player_src={} rc=0x{:X} out=0x{:X}",
                    g_clone_live_try, c.addr, c.ch, is_player ? 1 : 0,
                    static_cast<std::uint32_t>(rc), reinterpret_cast<std::uintptr_t>(out));
                if (rc == 0) {
                    g_async_src     = c.addr;
                    g_async_spot[0] = is_player ? player.x : saved_x + 3.0F;
                    g_async_spot[1] = is_player ? player.y : spot_y;
                    g_async_spot[2] = is_player ? player.z : spot_z;
                    LARGE_INTEGER now {};
                    QueryPerformanceCounter(&now);
                    g_async_wait_qpc    = now.QuadPart;
                    g_clone_live_cursor = 0x30000000;
                    log::get()->info(
                        "CloneLive: async posted - waiting ~2 s, then scanning near ({:.1f},{:.1f})",
                        static_cast<double>(g_async_spot[0]), static_cast<double>(g_async_spot[1]));
                    g_clone_live_stage = 5;
                } else {
                    g_clone_live_try++;
                }
            } else if (g_clone_live_stage == 5) {
                const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                if (freq > 0 && now.QuadPart - g_async_wait_qpc < freq * 2) {
                    return; // give the engine's job time to materialize the copy
                }
                constexpr std::uintptr_t k_end = 0x50000000;
                const auto step_end = (g_clone_live_cursor + (8U << 20U)) < k_end
                                          ? g_clone_live_cursor + (8U << 20U)
                                          : k_end;
                g_clone_live_cand_n = 0;
                clone_live_scan_spot(g_clone_live_cursor, step_end, g_async_spot, g_async_src,
                                     g_clone_live_cands, g_clone_live_cand_n, 32);
                g_clone_live_cursor = step_end;
                if (g_clone_live_cand_n > 0) {
                    for (int i = 0; i < g_clone_live_cand_n; i++) {
                        const auto &d = g_clone_live_cands[i];
                        log::get()->info(
                            "CloneLive: ASYNC copy candidate 0x{:X} ch={} at ({:.1f},{:.1f}) "
                            "d={:.1f}",
                            d.addr, d.ch, static_cast<double>(d.x), static_cast<double>(d.y),
                            static_cast<double>(d.d));
                    }
                    const auto node  = g_clone_live_cands[0].addr;
                    g_clone_live_obj = node;
                    if (readable(node + 0x10, 0x40)) {
                        alignas(16) float mm2[16];
                        std::memcpy(mm2, reinterpret_cast<const void *>(node + 0x10), sizeof(mm2));
                        mm2[12] = player.x + 2.5F;
                        mm2[13] = player.y;
                        mm2[14] = player.z;
                        mm2[15] = 1.0F;
                        std::memcpy(reinterpret_cast<void *>(node + 0x10), mm2, sizeof(mm2));
                    }
                    const auto ar = activate_helper(node);
                    const auto fr = jobflush_helper();
                    log::get()->info(
                        "CloneLive: ASYNC copy 0x{:X} moved to player + activation rc={} flush "
                        "rc={} - LOOK 2.5 m EAST",
                        node, ar, fr);
                    clone_live_fields("CloneLive: async obj", node);
                    LARGE_INTEGER t {};
                    QueryPerformanceCounter(&t);
                    g_clone_live_t0    = t.QuadPart;
                    g_clone_live_stage = 3;
                    return;
                }
                if (g_clone_live_cursor >= k_end ||
                    (freq > 0 && now.QuadPart - g_async_wait_qpc >= freq * 12)) {
                    log::get()->warn("CloneLive: no async copy found near the spot");
                    g_clone_live_try++;
                    g_clone_live_stage = 2;
                }
            } else if (g_clone_live_stage == 3 && g_clone_live_obj != 0) {
                const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                LARGE_INTEGER now {};
                QueryPerformanceCounter(&now);
                if (freq > 0 && now.QuadPart - g_clone_live_t0 >= freq * 10) {
                    clone_live_fields("CloneLive: obj@10s", g_clone_live_obj);
                    log::get()->info("CloneLive: finished");
                    g_clone_live_stage = 4;
                }
            }
        }

        auto clone_test_tick() -> void {
            if (g_clone_attempted) {
                return;
            }
            g_clone_attempted = true;
            // find_player_ctl returns the CONTROLLER (node+0xE8) - the character's logic
            // object (holds the action fields). Check it directly for the async clone.
            const auto ctl = find_player_ctl(g_last_pos);
            log::get()->info("CloneTest: player controller 0x{:X}", ctl);
            if (ctl == 0 || !readable(ctl, 8)) {
                log::get()->info("CloneTest: no player controller");
                return;
            }
            // === ROUTE B: the engine's runtime spawn recipe ===
            // 1) locate the AI-world object (vtable in the AI-world window 0x1E5C900..0x1E5CA00)
            std::uintptr_t worlds[4] = {};
            int            worlds_n  = 0;
            {
                LARGE_INTEGER t0 {};
                QueryPerformanceCounter(&t0);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                std::uintptr_t addr = 0x10000;
                while (addr < 0x7FFF0000 && worlds_n < 4) {
                    MEMORY_BASIC_INFORMATION mbi {};
                    if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                        break;
                    }
                    const auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                    auto       sz = mbi.RegionSize;
                    if (sz == 0) {
                        sz = 0x10000;
                    }
                    const bool ok = (mbi.State == MEM_COMMIT) &&
                                    (mbi.Protect & (PAGE_READONLY | PAGE_READWRITE |
                                                    PAGE_WRITECOPY)) != 0;
                    if (ok && sz >= 4) {
                        scan_world_page(ba, ba + sz - 4, worlds, 4, worlds_n);
                    }
                    addr = ba + sz;
                    if (freq > 0) {
                        LARGE_INTEGER t1 {};
                        QueryPerformanceCounter(&t1);
                        if (t1.QuadPart - t0.QuadPart > freq * 90) {
                            break;
                        }
                    }
                }
            }
            for (int i = 0; i < worlds_n; ++i) {
                log::get()->info("CloneTest: world candidate {} = 0x{:X} vt=0x{:X}", i, worlds[i],
                                 static_cast<std::uintptr_t>(mem::read<std::uint32_t>(worlds[i])));
            }
            const auto world = [&]() -> std::uintptr_t {
                for (int i = 0; i < worlds_n; ++i) {
                    if (mem::read<std::uint32_t>(worlds[i]) == 0x01E5C92C) {
                        return worlds[i];
                    }
                }
                return (worlds_n > 0) ? worlds[0] : 0;
            }();
            log::get()->info("CloneTest: using world 0x{:X}", world);
            // READ-ONLY from here (no engine calls - a half-created entity can choke the game,
            // so this probe creates nothing; it only reads the spawn-system data).
            // === READ-ONLY probe: dump the world's spawn-system structures (no engine calls,
            // no freeze risk). The spawn slots = the engine's own spawn specs.
            if (world != 0) {
                const auto smgr = mem::read<std::uintptr_t>(world + 0x924);
                log::get()->info("CloneTest: world+0x924 spawnMgr = 0x{:X}", smgr);
                if (smgr != 0 && readable(smgr + 0x40, 4)) {
                    log::get()->info("CloneTest: smgr +0x28=0x{:X} +0x3b=0x{:X} +0x40=0x{:X}",
                                     mem::read<std::uintptr_t>(smgr + 0x28),
                                     static_cast<std::uintptr_t>(
                                         mem::read<std::uint8_t>(smgr + 0x3b)),
                                     mem::read<std::uintptr_t>(smgr + 0x40));
                }
                // the update's lists: world+0x8 (object list) and world+0x24 (slots)
                for (const auto off : {0x8U, 0x24U}) {
                    if (!readable(world + off, 4)) {
                        continue;
                    }
                    const auto list = mem::read<std::uintptr_t>(world + off);
                    log::get()->info("CloneTest: world+0x{:X} list=0x{:X}", off, list);
                    if (list < 0x10000 || !readable(list, 0x20)) {
                        continue;
                    }
                    for (int i = 0; i < 4; ++i) {
                        const auto e = mem::read<std::uintptr_t>(list + i * 4);
                        if (e < 0x10000 || !readable(e, 0x20)) {
                            continue;
                        }
                        log::get()->info("CloneTest:   [{}] 0x{:X} vt=0x{:X} f08=0x{:X} f0C=0x{:X} "
                                         "f10=0x{:X} f14=0x{:X}",
                                         i, e,
                                         static_cast<std::uintptr_t>(
                                             mem::read<std::uint32_t>(e)),
                                         mem::read<std::uintptr_t>(e + 8),
                                         mem::read<std::uintptr_t>(e + 0x0C),
                                         mem::read<std::uintptr_t>(e + 0x10),
                                         mem::read<std::uintptr_t>(e + 0x14));
                    }
                }
            }
            // === READ-ONLY: find the population/crowd manager (vtable 0x1E577E0-range) and
            // dump its template catalog (the archetype list = the skin options).
            std::uintptr_t mgrs[4] = {};
            int            mgrs_n  = 0;
            {
                LARGE_INTEGER t0 {};
                QueryPerformanceCounter(&t0);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                std::uintptr_t addr = 0x20000000;
                while (addr < 0x7FFF0000 && mgrs_n < 4) {
                    MEMORY_BASIC_INFORMATION mbi {};
                    if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                        break;
                    }
                    const auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                    auto       sz = mbi.RegionSize;
                    if (sz == 0) {
                        sz = 0x10000;
                    }
                    const bool ok = (mbi.State == MEM_COMMIT) &&
                                    (mbi.Protect & (PAGE_READONLY | PAGE_READWRITE |
                                                    PAGE_WRITECOPY)) != 0;
                    if (ok && sz >= 4) {
                        scan_vt_page(ba, ba + sz - 4, 0x01E577A0, 0x01E578A0, mgrs, 4, mgrs_n);
                    }
                    addr = ba + sz;
                    if (freq > 0) {
                        LARGE_INTEGER t1 {};
                        QueryPerformanceCounter(&t1);
                        if (t1.QuadPart - t0.QuadPart > freq * 60) {
                            break;
                        }
                    }
                }
            }
            for (int i = 0; i < mgrs_n; ++i) {
                log::get()->info("CloneTest: mgr candidate {} = 0x{:X} vt=0x{:X}", i, mgrs[i],
                                 static_cast<std::uintptr_t>(mem::read<std::uint32_t>(mgrs[i])));
            }
            if (mgrs_n > 0 && readable(mgrs[0] + 0xA0, 4)) {
                const auto mgr  = mgrs[0];
                const auto arr  = mem::read<std::uintptr_t>(mgr + 0x94);
                const auto cnt  = mem::read<std::uint16_t>(mgr + 0x9a);
                log::get()->info("CloneTest: template array=0x{:X} count={}", arr, cnt);
                if (arr >= 0x10000 && readable(arr, 8) && cnt < 8192) {
                    for (int i = 0; i < cnt && i < 40; ++i) {
                        const auto e0 = mem::read<std::uintptr_t>(arr + i * 8);
                        const auto e4 = mem::read<std::uintptr_t>(arr + i * 8 + 4);
                        log::get()->info("CloneTest:   tpl[{}] e0=0x{:X} e4=0x{:X}", i, e0, e4);
                        // deref the entry's first pointer for a few entries (template object)
                        if (i < 3 && e0 >= 0x10000 && readable(e0, 8)) {
                            const auto obj = mem::read<std::uintptr_t>(e0);
                            if (obj >= 0x10000 && readable(obj, 0x20)) {
                                log::get()->info(
                                    "CloneTest:     ->obj=0x{:X} vt=0x{:X} d4=0x{:X} d8=0x{:X}",
                                    obj,
                                    static_cast<std::uintptr_t>(
                                        mem::read<std::uint32_t>(obj)),
                                    mem::read<std::uintptr_t>(obj + 4),
                                    mem::read<std::uintptr_t>(obj + 8));
                            }
                        }
                    }
                }
            }
            log::get()->info("CloneTest: done");
        }

        // The census + clone test on a plugin-owned thread: the heap scan takes minutes and
        // must never block the camera frame (it froze the game when it ran inline).
        static DWORD WINAPI clone_test_thread(LPVOID /*unused*/) {
            // v9: this thread now only arms the gameplay spawn TRACE (the old census / route-B /
            // keyed experiments are obsolete). The node-ctor + alloc probes log every character
            // construction with its CALLER while the player walks around (cap 300 lines each).
            Sleep(2000);
            g_spawn_logs.store(0, std::memory_order_relaxed);
            g_new_logs.store(0, std::memory_order_relaxed);
            g_alloc_pair_n.store(0, std::memory_order_relaxed);
            g_mass_logs.store(0, std::memory_order_relaxed);
            g_entctor_logs.store(0, std::memory_order_relaxed);
            g_node_logs.store(0, std::memory_order_relaxed);
            g_ent_key_count.store(0, std::memory_order_relaxed);
            g_spawn_capture.store(true, std::memory_order_relaxed);
            log::get()->info("SpawnCapture: armed - walk around town for ~90 s (node-ctor/alloc trace)");
            // v12: summary after the world has loaded (~150 s): how many Entity mass-creates
            // were seen and the last key pair (the citizen-creation recipe).
            Sleep(150000);
            log::get()->info("KeyTrace: entity mass-creates seen={} lastKey=(0x{:X},0x{:X})",
                             g_ent_key_count.load(std::memory_order_relaxed),
                             g_last_ent_key_lo.load(std::memory_order_relaxed),
                             g_last_ent_key_hi.load(std::memory_order_relaxed));
            // v15: (a) deliver a real body among the captured keys (rolling ring of 128);
            // (b) THE SPAWN TEST - the corrected create + REGISTER combination (never run
            // correctly before: the old attempts passed no registry in ECX).
            {
                if (g_exe_base == 0) {
                    return 0;
                }
                const auto reg = g_last_registry.load(std::memory_order_relaxed);
                if (reg == 0) {
                    log::get()->warn("KeySpawn: no registry captured");
                    return 0;
                }
                std::uintptr_t body  = 0;
                std::uint32_t bodyLo = 0;
                std::uint32_t bodyHi = 0;
                for (int i = 0; i < 128 && body == 0; ++i) {
                    const auto klo = g_ent_keys_lo[i];
                    const auto khi = g_ent_keys_hi[i];
                    if (klo == 0) {
                        continue;
                    }
                    const auto ent = registry_find2(g_exe_base + 0x61F160, reg, klo, khi);
                    if (ent < 0x10000 || !readable(ent + 0x100, 4)) {
                        continue;
                    }
                    const auto f7c = mem::read<float>(ent + 0x7C);
                    const auto ch  = mem::read<std::uint16_t>(ent + 0x66);
                    if (std::fabs(f7c + 0.5F) < 0.01F && ch >= 16) {
                        body   = ent;
                        bodyLo = klo;
                        bodyHi = khi;
                    }
                }
                if (body != 0) {
                    log::get()->info("KeySpawn: body found key (0x{:X},0x{:X}) -> 0x{:X}", bodyLo,
                                     bodyHi, body);
                    spawnq_fields("KeySpawn: body", body);
                    if (readable(body + 0x10, 0x40)) {
                        alignas(16) float mm[16];
                        std::memcpy(mm, reinterpret_cast<const void *>(body + 0x10), sizeof(mm));
                        mm[12] = g_last_pos.x + 2.5F;
                        mm[13] = g_last_pos.y;
                        mm[14] = g_last_pos.z;
                        mm[15] = 1.0F;
                        for (int w = 0; w < 40; ++w) {
                            std::memcpy(reinterpret_cast<void *>(body + 0x10), mm, sizeof(mm));
                            Sleep(75);
                        }
                        log::get()->info("KeySpawn: DELIVERED real body (key 0x{:X},0x{:X}) - LOOK "
                                         "2.5 m EAST",
                                         bodyLo, bodyHi);
                    }
                } else {
                    log::get()->warn("KeySpawn: no body-like entity among the captured keys");
                }
                // === (b) v17: MATURATION TEST - does a registered fake-key entity receive the
                // world/scene fill (+0x5C + fAC + fB0) over the next minutes? The engine's own
                // mass-created entities gain those ~2 min after creation. ===
                const std::uint32_t nkLo = 0x7A3C9E01U;
                const std::uint32_t nkHi = 7U;
                spawn_keyed2(g_exe_base + 0x6201A0, reg, 0x0984415EU, nkLo, nkHi);
                auto ne = registry_find2(g_exe_base + 0x61F160, reg, nkLo, nkHi);
                log::get()->info("KeySpawn v17: CREATE fake key (0x{:X},{}) -> 0x{:X}", nkLo, nkHi,
                                 static_cast<std::uintptr_t>(ne));
                if (ne >= 0x10000 && readable(ne + 0x100, 4)) {
                    spawnq_fields("KeySpawn v17: shell", ne);
                    const auto rrc = spawn_reg_helper(g_exe_base + 0x11D290, ne);
                    log::get()->info("KeySpawn v17: register rc={}", rrc);
                    for (int p = 0; p < 20; ++p) {
                        Sleep(15000);
                        if (!readable(ne + 0x100, 4)) {
                            log::get()->warn("KeySpawn v17: shell freed at poll {}", p);
                            break;
                        }
                        const auto f = [&](std::uint32_t off) {
                            return mem::read<std::uint32_t>(ne + off);
                        };
                        log::get()->info(
                            "KeySpawn v17: poll{} ch={} f50=0x{:X} w5C=0x{:X} fAC=0x{:X} fB0=0x{:X} "
                            "fD4=0x{:X} fE8=0x{:X}",
                            p, mem::read<std::uint16_t>(ne + 0x66), f(0x50), f(0x5C), f(0xAC),
                            f(0xB0), f(0xD4), f(0xE8));
                        if (f(0x5C) || f(0xAC) || f(0xB0)) {
                            log::get()->info("KeySpawn v17: *** SHELL MATURED at poll {} ***", p);
                        }
                    }
                    spawnq_fields("KeySpawn v17: shell final", ne);
                    if (readable(ne + 0x10, 0x40)) {
                        alignas(16) float mm[16];
                        std::memcpy(mm, reinterpret_cast<const void *>(ne + 0x10), sizeof(mm));
                        mm[12] = g_last_pos.x - 2.5F;
                        mm[13] = g_last_pos.y;
                        mm[14] = g_last_pos.z;
                        mm[15] = 1.0F;
                        for (int w = 0; w < 10; ++w) {
                            std::memcpy(reinterpret_cast<void *>(ne + 0x10), mm, sizeof(mm));
                            Sleep(75);
                        }
                        log::get()->info("KeySpawn v17: shell placed at ({:.1f},{:.1f}) - LOOK 2.5 m "
                                         "WEST",
                                         static_cast<double>(mm[12]),
                                         static_cast<double>(mm[13]));
                    }
                } else {
                    log::get()->warn("KeySpawn v17: create returned no entity");
                }
            }
            return 0;
        }

        auto clone_test_start() -> void {
            if (g_probe_started.exchange(true)) {
                return;
            }
            // 16 MB stack: the node clone recurses through up to 27 children and the default
            // 1 MB thread stack overflows mid-clone (crash at a CRT guard page).
            CreateThread(nullptr, 16U * 1024U * 1024U, &clone_test_thread, nullptr, 0, nullptr);
        }

        // Per-page node finder (pure helper - its own __try so a raced page only skips).
        static void scan_node_page(std::uintptr_t ba, std::uintptr_t end, const Vec3 &pos,
                                   std::uintptr_t &best, float &bestd) {
            constexpr std::uint32_t k_node_vtable = 0x01E4CE90;
            constexpr std::uint32_t k_marker      = 0x04DD5F8C;
            __try {
                for (std::uintptr_t p = ba; p <= end; p += 4) {
                    if (mem::read<std::uint32_t>(p) != k_node_vtable) {
                        continue;
                    }
                    if (!readable(p + 0x90, 4)) {
                        continue;
                    }
                    if (mem::read<std::uint32_t>(p + 0x68) != k_marker) {
                        continue;
                    }
                    if (mem::read<std::uint16_t>(p + 0x66) < 24) {
                        continue;
                    }
                    const auto nx = mem::read<float>(p + 0x40);
                    const auto ny = mem::read<float>(p + 0x44);
                    const auto dx = nx - pos.x;
                    const auto dy = ny - pos.y;
                    const auto d  = dx * dx + dy * dy;
                    if (d < bestd) {
                        bestd = d;
                        best  = p;
                    }
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }

        // Walk one address range for character nodes near pos (region by region, 90 ms soft
        // budget per range). Returns the best candidate via best/bestd.
        static void scan_node_range(std::uintptr_t lo, std::uintptr_t hi, const Vec3 &pos,
                                    std::uintptr_t &best, float &bestd) {
            LARGE_INTEGER t0 {};
            QueryPerformanceCounter(&t0);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            std::uintptr_t addr = lo;
            while (addr < hi) {
                MEMORY_BASIC_INFORMATION mbi {};
                if (VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) == 0) {
                    break;
                }
                const auto ba = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                auto       sz = mbi.RegionSize;
                if (sz == 0) {
                    sz = 0x10000;
                }
                const bool ok = (mbi.State == MEM_COMMIT) &&
                                (mbi.Protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY |
                                                PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                                                PAGE_EXECUTE_WRITECOPY)) != 0;
                if (ok && sz >= 0x90) {
                    scan_node_page(ba, ba + sz - 4, pos, best, bestd);
                }
                addr = ba + sz;
                if (freq > 0) {
                    LARGE_INTEGER t1 {};
                    QueryPerformanceCounter(&t1);
                    if (t1.QuadPart - t0.QuadPart > freq * 90) {
                        break;
                    }
                }
            }
        }

        auto find_player_ctl(const Vec3 &pos) -> std::uintptr_t {
            std::uintptr_t best  = 0;
            float          bestd = 64.0F; // 8 m squared
            // Pass 1: the character heap (where player/crowd nodes actually live) - fast.
            // Pass 2: the whole address space, only if pass 1 found nothing.
            // NOTE: this used to always walk the whole space, stalling the game ~3 s per
            // pass; the two-pass order keeps the common case cheap.
            scan_node_range(0x30000000U, 0x54000000U, pos, best, bestd);
            if (best == 0) {
                scan_node_range(0x10000U, 0x7FFF0000U, pos, best, bestd);
            }
            if (best == 0) {
                return 0;
            }
            g_act_node = best;
            const auto ctl = mem::read<std::uintptr_t>(best + 0xE8);
            if (ctl < 0x10000 || !readable(ctl + 0x8E4, 4)) {
                return 0;
            }
            return ctl;
        }

        auto refresh_act_ctl(const Vec3 &pos) -> void {
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            if (freq <= 0) {
                return;
            }
            // don't scan while the world is still loading (page churn -> the loader wins)
            if (now.QuadPart - g_load_qpc < freq * 20) {
                return;
            }
            // Fast path: cached controller whose node is still alive - never scan.
            // (Old logic ALSO forced a full-address-space rescan every 10 s, and with no
            // rate limit at all when no controller was known yet. That scan freezes the
            // game thread for ~3 s per pass; at menus it ran back-to-back. Timing matched
            // the "freezes every few seconds" report and is the prime suspect for the
            // recurring nvwgf2um driver crashes. Fixed 2026-10-08.)
            if (g_act_ctl != 0 && g_act_node != 0 && readable(g_act_node + 0x68, 4) &&
                mem::read<std::uint32_t>(g_act_node + 0x68) == 0x04DD5F8C) {
                return; // node still alive, keep the cached controller
            }
            // v19.2: rescans are OFF unless [PlayerTransform] ActScan=true. find_player_ctl
            // walks up to ~2 GB byte-wise (~3 s freeze per pass). During fast travel the
            // cached node dies and the scan fired mid-load; the 2026-10-09 crash dumps
            // (game-code null deref, then nvwgf2um driver AV) both show an identical
            // ~3.2 s pre-crash log gap - the stall is the crash trigger, not the shells.
            if (!g_act_scan_allowed.load(std::memory_order_relaxed)) {
                g_act_ctl  = 0;
                g_act_node = 0;
                return;
            }
            // Rate-limit rescans (3 s base, growing to 20 s after repeated misses) so a
            // menu/loading screen can never keep the scanner running on the game thread.
            {
                auto delay = 3U * (g_act_fail_count + 1U);
                if (delay > 20U) {
                    delay = 20U;
                }
                if (g_act_last_qpc != 0 && now.QuadPart - g_act_last_qpc < freq * delay) {
                    return;
                }
            }
            g_act_last_qpc = now.QuadPart;
            LARGE_INTEGER   scan_t0 {};
            QueryPerformanceCounter(&scan_t0);
            g_act_ctl      = find_player_ctl(pos);
            LARGE_INTEGER   scan_t1 {};
            QueryPerformanceCounter(&scan_t1);
            log::get()->info("ActScan: took {} ms found={}",
                             static_cast<int>((scan_t1.QuadPart - scan_t0.QuadPart) * 1000 / freq),
                             g_act_ctl != 0 ? 1 : 0);
            if (g_act_ctl == 0) {
                if (g_act_fail_count < 6U) {
                    g_act_fail_count++;
                }
            } else {
                g_act_fail_count = 0;
            }
            // One-time class comparison for the anim probe (route-2 hunt): log the player
            // controller's vtable + header so it can be compared against the ghost body's
            // +0xE8 object (GhostAnimProbe). Read-only.
            static std::uintptr_t s_last_ctl_logged = 0;
            if (g_act_ctl != 0 && g_act_ctl != s_last_ctl_logged) {
                s_last_ctl_logged = g_act_ctl;
                log::get()->info("ActCtl: player ctl=0x{:X} vt=0x{:X}", g_act_ctl,
                                 mem::read<std::uint32_t>(g_act_ctl));
                std::string head;
                char        tmp[16];
                for (int i = 0; i < 0x40; i += 4) {
                    std::snprintf(tmp, sizeof(tmp), "%08X ", mem::read<std::uint32_t>(g_act_ctl + i));
                    head += tmp;
                }
                log::get()->info("ActCtl: head: {}", head);
            }
        }

        // Replay: CREATE in-hook during a live burst (the spawn container is transient and only
        // valid while the engine is streaming), then PLACE the body later from our thread once
        // the player position is valid (placement = pure memory writes, thread-safe).
        std::atomic<int> g_replay_state {0};
        std::atomic<int> g_replay_count {0};
        std::atomic<bool> g_expect_return {false};
        std::atomic<std::uint32_t> g_last_spawn_arg {0};
        std::atomic<int> g_hijack_target {0}; // 1 = a-type, 2 = b-type
        std::atomic<std::uintptr_t> g_created_a {0};
        std::atomic<std::uintptr_t> g_created_b {0};

        // Capture the engine's own mass-creator calls (FUN_00a201a0): classId + key pair -
        // the real recipe for crowd/character creation (391 calls at world load).
        struct ProbeMassCreate {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                g_last_registry.store(static_cast<std::uint32_t>(r.ecx), std::memory_order_relaxed);
                const auto a1 = mem::read<std::uintptr_t>(r.esp + 4);
                const auto a2 = mem::read<std::uintptr_t>(r.esp + 8);
                const auto a3 = mem::read<std::uintptr_t>(r.esp + 0x0C);
                const auto a4 = mem::read<std::uintptr_t>(r.esp + 0x10);
                if (a1 == 0x0984415EU) { // Entity class - the character/world entity creation
                    const auto idx = g_ent_key_count.fetch_add(1, std::memory_order_relaxed);
                    g_last_ent_key_lo.store(static_cast<std::uint32_t>(a2), std::memory_order_relaxed);
                    g_last_ent_key_hi.store(static_cast<std::uint32_t>(a3), std::memory_order_relaxed);
                    const auto slot = static_cast<unsigned>(idx) & 127U;
                    g_ent_keys_lo[slot] = static_cast<std::uint32_t>(a2);
                    g_ent_keys_hi[slot] = static_cast<std::uint32_t>(a3);
                    // v19: record the key with a load-burst id (>15 s gap = new burst).
                    const auto nowms = static_cast<std::uint64_t>(GetTickCount64());
                    if (nowms - g_adopt_burst_last.load(std::memory_order_relaxed) > 15000ULL) {
                        g_adopt_burst.fetch_add(1, std::memory_order_relaxed);
                    }
                    g_adopt_burst_last.store(nowms, std::memory_order_relaxed);
                    const auto bi   = g_adopt_burst.load(std::memory_order_relaxed);
                    const auto aidx = g_adopt_key_n.fetch_add(1, std::memory_order_relaxed);
                    if (aidx < 8192) {
                        g_adopt_keys[aidx].lo    = static_cast<std::uint32_t>(a2);
                        g_adopt_keys[aidx].hi    = static_cast<std::uint32_t>(a3);
                        g_adopt_keys[aidx].burst = bi;
                    }
                    if (bi < 128) {
                        if (g_adopt_burst_count[bi] == 0) {
                            g_adopt_burst_first_lo[bi] = static_cast<std::uint32_t>(a2);
                            g_adopt_burst_first_hi[bi] = static_cast<std::uint32_t>(a3);
                        }
                        ++g_adopt_burst_count[bi];
                    }
                    // v19: did the load request one of our pre-placed keys?
                    if (g_adopt_shell_n > 0) {
                        for (int s = 0; s < g_adopt_shell_n; ++s) {
                            if (g_adopt_shell_lo[s] == static_cast<std::uint32_t>(a2) &&
                                g_adopt_shell_hi[s] == static_cast<std::uint32_t>(a3)) {
                                static std::atomic<int> hit_logs {0};
                                if (hit_logs.fetch_add(1, std::memory_order_relaxed) < 100) {
                                    log::get()->info("Adopt: LOAD HIT shell[{}] key=(0x{:X},0x{:X})",
                                                     s, a2, a3);
                                }
                                break;
                            }
                        }
                    }
                }
                const auto n = g_mass_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 3000) {
                    return;
                }
                log::get()->info("MassCreate: classId=0x{:X} keyLo=0x{:X} keyHi=0x{:X} a4=0x{:X}",
                                 a1, a2, a3, a4);
            }
        };

        // Fires at the engine's post-spawn return site: the created entity is in EAX.
        struct ProbeSpawnRet {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                static std::atomic<int> logged {0};
                const auto              created = static_cast<std::uintptr_t>(r.eax);
                if (!g_expect_return.exchange(false, std::memory_order_relaxed)) {
                    // regular engine spawn: log the first few for comparison
                    const auto n = logged.fetch_add(1, std::memory_order_relaxed);
                    if (n < 12 && created >= 0x10000 && readable(created + 0x148, 4)) {
                        log::get()->info(
                            "SpawnRet(engine): arg=0x{:X} created=0x{:X} vt=0x{:X} children={} f7c={:.2f}",
                            g_last_spawn_arg.load(std::memory_order_relaxed), created,
                            static_cast<std::uintptr_t>(mem::read<std::uint32_t>(created)),
                            mem::read<std::uint16_t>(created + 0x66),
                            static_cast<double>(mem::read<float>(created + 0x7C)));
                    }
                    return;
                }
                log::get()->info("SpawnReplay: captured created=0x{:X}", created);
                if (created < 0x10000) {
                    return;
                }
                if (readable(created + 0x40, 12)) {
                    const Vec3 p = mem::read<Vec3>(created + 0x40);
                    log::get()->info("SpawnReplay: original pos ({:.1f},{:.1f},{:.1f})", p.x, p.y,
                                     p.z);
                }
                // structure dump: what does the created entity have vs a real crowd body?
                if (readable(created + 0x148, 4)) {
                    log::get()->info(
                        "SpawnReplay: created vt=0x{:X} children={} f7c={:.2f} arr=0x{:X} mark=0x{:X}",
                        static_cast<std::uintptr_t>(mem::read<std::uint32_t>(created)),
                        mem::read<std::uint16_t>(created + 0x66),
                        static_cast<double>(mem::read<float>(created + 0x7C)),
                        mem::read<std::uintptr_t>(created + 0x140),
                        mem::read<std::uintptr_t>(created + 0xC8));
                }
                if (g_hijack_target.load(std::memory_order_relaxed) == 1) {
                    g_created_a.store(created, std::memory_order_relaxed);
                } else {
                    g_created_b.store(created, std::memory_order_relaxed);
                }
            }
        };

        static int spawn_call_helper(std::uintptr_t fn, std::uintptr_t group, std::uint32_t hash,
                                     std::uintptr_t *out) {
            __try {
                using Fn = unsigned int(__thiscall *)(void *, unsigned int);
                *out      = reinterpret_cast<Fn>(fn)(reinterpret_cast<void *>(group), hash);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // FUN_00a1f160(keyLo, keyHi) - the registry find-by-key; returns the created entity.
        static std::uintptr_t registry_find_helper(std::uintptr_t fn, std::uint32_t k1,
                                                   std::uint32_t k2) {
            __try {
                using Fn = std::uintptr_t(__cdecl *)(std::uint32_t, std::uint32_t);
                return reinterpret_cast<Fn>(fn)(k1, k2);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 0;
            }
        }

        // v14 CORRECTED signatures (decoded from the disasm): both are THISCALL with the
        // registry in ECX. FUN_00a1f160(ECX=registry, keyLo, keyHi) -> entity.
        static std::uintptr_t registry_find2(std::uintptr_t fn, std::uint32_t reg, std::uint32_t k1,
                                             std::uint32_t k2) {
            __try {
                using Fn = std::uintptr_t(__thiscall *)(void *, std::uint32_t, std::uint32_t);
                return reinterpret_cast<Fn>(fn)(reinterpret_cast<void *>(reg), k1, k2);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 0;
            }
        }

        // FUN_00a201a0(ECX=registry, classId, keyLo, keyHi, 0) - find-or-create.
        static void *spawn_keyed2(std::uintptr_t fn, std::uint32_t reg, std::uint32_t id,
                                  std::uint32_t k1, std::uint32_t k2) {
            __try {
                using SpawnFn = void *(__thiscall *)(void *, std::uint32_t, std::uint32_t,
                                                     std::uint32_t, std::uint32_t);
                return reinterpret_cast<SpawnFn>(fn)(reinterpret_cast<void *>(reg), id, k1, k2, 0);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return nullptr;
            }
        }

        // FUN_0051d290(entity) - register the entity (fastcall: entity in ecx).
        static int spawn_reg_helper(std::uintptr_t fn, std::uintptr_t entity) {
            __try {
                using Fn = void(__fastcall *)(std::uintptr_t);
                reinterpret_cast<Fn>(fn)(entity);
                return 0;
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                return 1;
            }
        }

        // v20 ReqWatch: capture the engine's own animation-request setter FUN_01ad9190.
        // thiscall: ECX = behavior object; stack: [esp+4] = slot index (-1 = all six),
        // [esp+8] = requested value; [esp] = return address. Read-only, capped log.
        struct ProbeReqWatch {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                static std::atomic<int> n {0};
                const auto              k = n.fetch_add(1, std::memory_order_relaxed);
                if (k >= 600) {
                    return;
                }
                const auto stack = static_cast<std::uintptr_t>(r.esp);
                const auto slot  = mem::read<std::int32_t>(stack + 4);
                const auto val   = mem::read<std::uint32_t>(stack + 8);
                log::get()->info("ReqWatch: #{} this=0x{:X} slot={} val=0x{:X} caller=0x{:X}",
                                 k, static_cast<std::uint32_t>(r.ecx), slot, val,
                                 mem::read<std::uint32_t>(stack));
            }
        };

        // v21 AnimApply: animation-apply probe FUN_01ac1ad0. thiscall: ECX = behavior object;
        // six uint32 slots at this+0x2F50..+0x2F64. Read-only, capped log. Log the first 60
        // calls, then only while any slot differs from the 0xFFFFFFFF sentinel.
        struct ProbeAnimApply {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                static std::atomic<int> calls {0};
                static int              logged = 0;
                const auto              k     = calls.fetch_add(1, std::memory_order_relaxed);
                const auto              thisv = static_cast<std::uint32_t>(r.ecx);
                if (k % 4096 == 0) {
                    log::get()->info("AnimApply: calls={} this=0x{:X}", k, thisv);
                }
                if (logged >= 8000) {
                    return;
                }
                std::uint32_t slots[6] = {0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu,
                                          0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu};
                bool          any_non_ff = false;
                if (readable(thisv + 0x2F50, 24)) {
                    for (int i = 0; i < 6; ++i) {
                        slots[i] = mem::read<std::uint32_t>(
                            static_cast<std::uintptr_t>(thisv) + 0x2F50 + i * 4);
                        if (slots[i] != 0xFFFFFFFFu) {
                            any_non_ff = true;
                        }
                    }
                }
                if (k < 60 || any_non_ff) {
                    ++logged;
                    log::get()->info(
                        "AnimApply: #{} this=0x{:X} slots=0x{:X},0x{:X},0x{:X},0x{:X},0x{:X},0x{:X}",
                        k, thisv, slots[0], slots[1], slots[2], slots[3], slots[4], slots[5]);
                }
            }
        };

        // v21 AnimWrite: animation-write probe FUN_01b52c0. thiscall; stack args mirror
        // ProbeReqWatch ([esp]=return address, [esp+4]=a,...). Read-only, capped log; after the
        // first 60 calls only re-log when a..d change.
        struct ProbeAnimWrite {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                static std::atomic<int> n {0};
                static int              logged = 0;
                static std::uint32_t    last_a = 0;
                static std::uint32_t    last_b = 0;
                static std::uint32_t    last_c = 0;
                static std::uint32_t    last_d = 0;
                static std::uint8_t     last_e = 0;
                static std::uint8_t     last_f = 0;
                const auto              k      = n.fetch_add(1, std::memory_order_relaxed);
                const auto              stack  = static_cast<std::uintptr_t>(r.esp);
                const auto              a      = mem::read<std::uint32_t>(stack + 4);
                const auto              b      = mem::read<std::uint32_t>(stack + 8);
                const auto              c      = mem::read<std::uint32_t>(stack + 0xC);
                const auto              d      = mem::read<std::uint32_t>(stack + 0x10);
                const auto              e      = mem::read<std::uint8_t>(stack + 0x14);
                const auto              f      = mem::read<std::uint8_t>(stack + 0x18);
                const auto              caller = mem::read<std::uint32_t>(stack);
                if (k % 4096 == 0) {
                    log::get()->info("AnimWrite: calls={}", k);
                }
                if (logged >= 30000) {
                    return;
                }
                const bool changed =
                    (a != last_a || b != last_b || c != last_c || d != last_d ||
                     e != last_e || f != last_f);
                if (k < 60 || changed) {
                    last_a = a;
                    last_b = b;
                    last_c = c;
                    last_d = d;
                    last_e = e;
                    last_f = f;
                    ++logged;
                    log::get()->info("AnimWrite: #{} this=0x{:X} a=0x{:X} b=0x{:X} c=0x{:X} "
                                     "d=0x{:X} e=0x{:X} f=0x{:X} caller=0x{:X}",
                                     k, static_cast<std::uint32_t>(r.ecx), a, b, c, d, e, f, caller);
                }
            }
        };

        // === v19 AdoptTest ===
        // The world's own entity creation is find-or-create keyed by (worldHash, block): a shell
        // pre-placed at a key BEFORE the region ever loads is returned by the load's own creation
        // pass - i.e. the load may adopt OUR object. v19.1: plant ONLY at keys that currently have
        // NO entity (fresh targets), and dump every recorded key to a file so a restart keeps them.
        constexpr const char *k_adopt_keys_path =
            "D:\\SteamLibrary\\steamapps\\common\\Assassin's Creed IV Black Flag\\plugins\\"
            "AC.BlackFlag.PatchFix.keys.txt";

        static void adopt_dump_keys() {
            static int flushed = 0;
            const auto n = g_adopt_key_n.load(std::memory_order_relaxed);
            if (n <= flushed) {
                return;
            }
            if (std::FILE *f = std::fopen(k_adopt_keys_path, "a")) {
                char line[48];
                int  cnt = 0;
                for (int i = flushed; i < n && i < 8192; ++i) {
                    const auto len = std::snprintf(line, sizeof(line), "%08X %08X\n",
                                                   g_adopt_keys[i].lo, g_adopt_keys[i].hi);
                    if (len > 0) {
                        std::fwrite(line, 1, static_cast<std::size_t>(len), f);
                    }
                    ++cnt;
                }
                std::fclose(f);
                flushed = n;
                log::get()->info("Adopt: dumped {} keys to file", cnt);
            }
        }

        static void adopt_precreate() {
            const auto reg = g_last_registry.load(std::memory_order_relaxed);
            const bool world_ok = (std::fabs(g_last_pos.x) + std::fabs(g_last_pos.y) +
                                   std::fabs(g_last_pos.z)) > 20.0F;
            if (reg == 0 || !world_ok) {
                // keep armed, retry - the registry is captured at the first world load
                static std::int64_t last_note = 0;
                LARGE_INTEGER       now {};
                QueryPerformanceCounter(&now);
                const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
                if (freq > 0 && now.QuadPart - last_note > freq * 10) {
                    last_note = now.QuadPart;
                    log::get()->info("Adopt: waiting (registry=0x{:X} world={}) - plants when "
                                     "in-world",
                                     reg, world_ok ? 1 : 0);
                }
                return;
            }
            g_adopt_armed   = false;
            g_adopt_created = true;
            // candidates = keys with NO entity right now (genuinely fresh). Sources: the keys file
            // (earlier sessions / other regions) + this session's record.
            static std::uint32_t cand_lo[256];
            static std::uint32_t cand_hi[256];
            int                  ncand = 0;
            const auto           add_cand = [&](std::uint32_t klo, std::uint32_t khi) -> void {
                if (ncand >= 256 || (klo == 0 && khi == 0)) {
                    return;
                }
                for (int j = 0; j < ncand; ++j) {
                    if (cand_lo[j] == klo && cand_hi[j] == khi) {
                        return;
                    }
                }
                if (registry_find2(g_exe_base + 0x61F160, reg, klo, khi) != 0) {
                    return; // entity exists - not a fresh target
                }
                cand_lo[ncand] = klo;
                cand_hi[ncand] = khi;
                ++ncand;
            };
            if (std::FILE *f = std::fopen(k_adopt_keys_path, "r")) {
                char line[64];
                int  ln = 0;
                while (ncand < 256 && std::fgets(line, sizeof(line), f) != nullptr) {
                    ++ln;
                    if ((ln % 3) != 0) {
                        continue;
                    }
                    std::uint32_t kl = 0;
                    std::uint32_t kh = 0;
                    if (std::sscanf(line, "%x %x", &kl, &kh) == 2) {
                        add_cand(kl, kh);
                    }
                }
                std::fclose(f);
                log::get()->info("Adopt: file scan {} lines -> {} fresh so far", ln, ncand);
            } else {
                log::get()->info("Adopt: no keys file yet");
            }
            {
                const auto nkeys = g_adopt_key_n.load(std::memory_order_relaxed);
                for (int i = 0; i < nkeys && i < 8192 && ncand < 256; i += 2) {
                    add_cand(g_adopt_keys[i].lo, g_adopt_keys[i].hi);
                }
            }
            if (ncand == 0) {
                log::get()->warn("Adopt: no fresh targets (every known key still has an entity) "
                                 "- nothing planted; visit a NEW region first, restart, retry.");
                return;
            }
            const auto    stride  = static_cast<std::uint32_t>(ncand) / 32U + 1U;
            const auto    only_lo = g_adopt_only_lo.load(std::memory_order_relaxed);
            const auto    only_hi = g_adopt_only_hi.load(std::memory_order_relaxed);
            const auto    skip_lo = g_adopt_skip_lo.load(std::memory_order_relaxed);
            const auto    skip_hi = g_adopt_skip_hi.load(std::memory_order_relaxed);
            const int     max_n   = std::clamp(g_adopt_max.load(std::memory_order_relaxed), 0, 32);
            const int     cap     = (max_n > 0) ? max_n : 32;
            std::uint32_t want_lo[32] = {};
            std::uint32_t want_hi[32] = {};
            int           want = 0;
            for (int i = 0; i < ncand && want < cap; i += static_cast<int>(stride)) {
                if (only_lo != 0 && (cand_lo[i] != only_lo || cand_hi[i] != only_hi)) {
                    continue;
                }
                if (skip_lo != 0 && cand_lo[i] == skip_lo && cand_hi[i] == skip_hi) {
                    continue;
                }
                want_lo[want] = cand_lo[i];
                want_hi[want] = cand_hi[i];
                ++want;
            }
            log::get()->info(
                "Adopt: {} fresh targets, planting {} (only=0x{:X}:0x{:X} skip=0x{:X}:0x{:X}) reg=0x{:X}",
                ncand, want, only_lo, only_hi, skip_lo, skip_hi, reg);
            int made = 0;
            for (int i = 0; i < want; ++i) {
                const auto e = spawn_keyed2(g_exe_base + 0x6201A0, reg, 0x0984415EU, want_lo[i],
                                            want_hi[i]);
                auto       p = reinterpret_cast<std::uintptr_t>(e);
                if (p < 0x10000 || !readable(p + 0x100, 4)) {
                    p = registry_find2(g_exe_base + 0x61F160, reg, want_lo[i], want_hi[i]);
                }
                if (p >= 0x10000 && readable(p + 0x100, 4)) {
                    g_adopt_shells[made]      = p;
                    g_adopt_shell_lo[made]    = want_lo[i];
                    g_adopt_shell_hi[made]    = want_hi[i];
                    g_adopt_shell_state[made] = 0;
                    log::get()->info("Adopt: shell[{}] 0x{:X} key=(0x{:X},0x{:X})", made, p,
                                     want_lo[i], want_hi[i]);
                    ++made;
                } else {
                    log::get()->warn("Adopt: create failed key=(0x{:X},0x{:X})", want_lo[i],
                                     want_hi[i]);
                }
            }
            g_adopt_shell_n = made;
            log::get()->info("Adopt: pre-create done - {} fresh shells planted. Now TRAVEL to the "
                             "region those keys belong to.",
                             made);
        }

        // If an adopted shell filled into a rendered body, deliver it next to the player so the
        // win is visible: repeat the proven transform write for ~1 s (stream bodies accept it).
        static void adopt_deliver_step() {
            if (g_adopt_deliver_target == 0 || g_adopt_deliver_tries <= 0) {
                return;
            }
            const auto p = g_adopt_deliver_target;
            --g_adopt_deliver_tries;
            if (!readable(p + 0x10, 0x44)) {
                return;
            }
            alignas(16) float mm[16];
            std::memcpy(mm, reinterpret_cast<const void *>(p + 0x10), sizeof(mm));
            mm[12] = g_last_pos.x + 2.5F;
            mm[13] = g_last_pos.y;
            mm[14] = g_last_pos.z;
            mm[15] = 1.0F;
            std::memcpy(reinterpret_cast<void *>(p + 0x10), mm, sizeof(mm));
            const Vec3 pp {mm[12], mm[13], mm[14]};
            std::memcpy(reinterpret_cast<void *>(p + 0x40), &pp, sizeof(pp));
            if (g_adopt_deliver_tries == 0) {
                log::get()->info("Adopt: delivered 0x{:X} to ({:.1f},{:.1f}) - LOOK 2.5 m EAST", p,
                                 static_cast<double>(mm[12]), static_cast<double>(mm[13]));
            }
        }

        static void adopt_watch() {
            if (g_adopt_shell_n == 0) {
                return;
            }
            static std::int64_t last_qpc = 0;
            const auto          freq = g_qpc_freq.load(std::memory_order_relaxed);
            LARGE_INTEGER       now {};
            QueryPerformanceCounter(&now);
            if (freq > 0 && last_qpc != 0 && now.QuadPart - last_qpc < freq * 2) {
                return;
            }
            last_qpc = now.QuadPart;
            for (int i = 0; i < g_adopt_shell_n; ++i) {
                const auto p = g_adopt_shells[i];
                if (!readable(p, 4)) {
                    continue;
                }
                const auto vt = mem::read<std::uint32_t>(p);
                if (vt < 0x10000U) {
                    if (g_adopt_shell_state[i] != 0xFFFFFFFFU) {
                        g_adopt_shell_state[i] = 0xFFFFFFFFU;
                        log::get()->info("Adopt: shell[{}] 0x{:X} freed/cleared (vt=0x{:X})", i, p,
                                         vt);
                    }
                    continue;
                }
                if (!readable(p + 0x50, 0xA0)) {
                    continue;
                }
                const auto    ch  = mem::read<std::uint16_t>(p + 0x66);
                const auto    f50 = mem::read<std::uint32_t>(p + 0x50);
                const auto    f7c = mem::read<float>(p + 0x7C);
                const auto    w5c = mem::read<std::uint32_t>(p + 0x5C);
                const auto    fac = mem::read<std::uint32_t>(p + 0xAC);
                const auto    fb0 = mem::read<std::uint32_t>(p + 0xB0);
                const auto    fd4 = mem::read<std::uint32_t>(p + 0xD4);
                const auto    fe8 = mem::read<std::uint32_t>(p + 0xE8);
                std::uint32_t f7c_bits = 0;
                std::memcpy(&f7c_bits, &f7c, 4);
                const auto h = (vt * 31U) ^ (f50 * 131U) ^ f7c_bits ^ (w5c * 7U) ^ (fac * 17U) ^
                               (fb0 * 37U) ^ (static_cast<std::uint32_t>(ch) << 20) ^ (fd4 * 11U) ^
                               (fe8 * 3U);
                if (h != g_adopt_shell_state[i]) {
                    g_adopt_shell_state[i] = h;
                    if (g_adopt_watch_logs < 200) {
                        ++g_adopt_watch_logs;
                        log::get()->info(
                            "Adopt: shell[{}] 0x{:X} ch={} f50=0x{:X} f7c={:.2f} w5C=0x{:X} "
                            "fAC=0x{:X} fB0=0x{:X} fD4=0x{:X} fE8=0x{:X}",
                            i, p, ch, f50, static_cast<double>(f7c), w5c, fac, fb0, fd4, fe8);
                    }
                    if (fac && ch >= 16 && std::fabs(f7c + 0.5F) < 0.01F &&
                        g_adopt_deliver_target == 0) {
                        g_adopt_deliver_target = p;
                        g_adopt_deliver_tries  = 60;
                        log::get()->info("*** Adopt: shell[{}] 0x{:X} became a RENDERED BODY - "
                                         "delivering to the player ***",
                                         i, p);
                    }
                }
            }
        }

        static void adopt_tick() {
            adopt_dump_keys();
            // burst summaries (logged once per completed burst)
            {
                const auto cur    = g_adopt_burst.load(std::memory_order_relaxed);
                auto       logged = g_adopt_logged_burst.load(std::memory_order_relaxed);
                while (logged + 1 < cur && logged + 1 < 128) {
                    const auto b = logged + 1;
                    if (g_adopt_burst_count[b] != 0) {
                        log::get()->info("Adopt: burst {} done keys={} first=(0x{:X},0x{:X})", b,
                                         g_adopt_burst_count[b], g_adopt_burst_first_lo[b],
                                         g_adopt_burst_first_hi[b]);
                    }
                    ++logged;
                }
                g_adopt_logged_burst.store(logged, std::memory_order_relaxed);
            }
            if (g_adopt_armed && !g_adopt_created) {
                adopt_precreate();
            }
            adopt_watch();
            adopt_deliver_step();
        }

        // In-hook create: call the engine's spawn API right now (valid container context),
        // bracketed by the engine's own job-context push/pop, then REGISTER the created entity
        // (FUN_0051d290) - the step that actually puts it into the world's systems.
        auto do_spawn_replay(std::uintptr_t group, std::uint32_t target) -> void {
            log::get()->info("SpawnReplay: group=0x{:X} target=0x{:X} calling spawn API ...", group,
                             target);
            std::uintptr_t created = 0;
            // job-context push (engine's own bracket around entity creation)
            using PushFn = void(__cdecl *)(unsigned char, unsigned char);
            if (g_exe_base != 0) {
                reinterpret_cast<PushFn>(g_exe_base + 0x62D5A0)(0, 1);
            }
            const int rc = spawn_call_helper(g_exe_base + 0x1FD730, group, target, &created);
            if (g_exe_base != 0) {
                using PopFn = void(__cdecl *)();
                reinterpret_cast<PopFn>(g_exe_base + 0x62F320)();
            }
            log::get()->info("SpawnReplay: rc={} created=0x{:X}", rc, created);
            if (created == 0 || !readable(created, 8)) {
                return;
            }
            log::get()->info("SpawnReplay: created vt=0x{:X} +4=0x{:X}",
                             static_cast<std::uintptr_t>(mem::read<std::uint32_t>(created)),
                             mem::read<std::uintptr_t>(created + 4));
            // The registration expects the entity's identity marker pointer at +0xC8
            // (&DAT_04dd5f8c) - engine-created entities always carry it; ours lacks it.
            if (readable(created + 0xC8, 4)) {
                mem::write<std::uint32_t>(created + 0xC8, 0x04DD5F8C);
            }
            // REGISTER the entity into the world systems (the missing step).
            static int reg_rc = -1;
            if (g_exe_base != 0) {
                reg_rc = spawn_reg_helper(g_exe_base + 0x11D290, created);
                log::get()->info("SpawnReplay: register rc={}", reg_rc);
            }
            if (target == 0x462A56BC) {
                g_created_a.store(created, std::memory_order_relaxed);
            } else {
                g_created_b.store(created, std::memory_order_relaxed);
            }
        }

        // Place a created body at the player +3 m (translation +0x40, facing +0x100, +0x10).
        auto place_body(std::uintptr_t created) -> void {
            if (created == 0 || !readable(created + 0x100, 16)) {
                return;
            }
            Vec3 here = g_last_pos;
            here.x += 3.0F;
            if (!finite3(here)) {
                return;
            }
            mem::write<Vec3>(created + 0x40, here);
            mem::write<Vec4>(created + 0x100, g_last_quat);
            mem::write<Vec3>(created + 0x10, here);
            log::get()->info("SpawnReplay: placed 0x{:X} at ({:.1f},{:.1f},{:.1f})", created,
                             here.x, here.y, here.z);
        }

        // The circling driver: once created entities exist, drive them in a circle around the
        // player using the co-op ghost's proven transform writes (pos +0x40, yaw rows +0x10/+0x20).
        static DWORD WINAPI replay_thread(LPVOID /*unused*/) {
            float    angle = 0.0F;
            int      ticks = 0;
            for (int i = 0; i < 12000; ++i) { // up to ~10 min at 50 ms
                Sleep(50);
                const auto a = g_created_a.load(std::memory_order_relaxed);
                const auto b = g_created_b.load(std::memory_order_relaxed);
                if (a == 0 && b == 0) {
                    continue;
                }
                const auto px = g_last_pos.x;
                const auto py = g_last_pos.y;
                const auto pz = g_last_pos.z;
                if ((px * px + py * py + pz * pz) <= 4.0F) {
                    continue;
                }
                angle += 0.04F;
                const auto drive = [&](std::uintptr_t e, const float phase, const float radius) {
                    if (e == 0 || !readable(e + 0x4C, 4)) {
                        return;
                    }
                    const auto x = px + radius * std::cos(angle + phase);
                    const auto y = py + radius * std::sin(angle + phase);
                    auto *const pos = reinterpret_cast<float *>(e + 0x40);
                    pos[0]          = x;
                    pos[1]          = y;
                    pos[2]          = pz;
                    // face the player
                    const auto yaw = std::atan2(py - y, px - x) + 1.5707963F;
                    const auto c   = std::cos(yaw);
                    const auto s   = std::sin(yaw);
                    auto *const r0 = reinterpret_cast<float *>(e + 0x10);
                    auto *const r1 = reinterpret_cast<float *>(e + 0x20);
                    r0[0] = c; r0[1] = s; r0[2] = 0.0F; r0[3] = 0.0F;
                    r1[0] = -s; r1[1] = c; r1[2] = 0.0F; r1[3] = 0.0F;
                };
                drive(a, 0.0F, 3.0F);
                drive(b, 3.14159F, 3.5F);
                if (++ticks % 40 == 0) { // every ~2 s
                    const auto read_pos = [](std::uintptr_t e) -> Vec3 {
                        if (e == 0 || !readable(e + 0x48, 4)) {
                            return {};
                        }
                        return mem::read<Vec3>(e + 0x40);
                    };
                    const auto pa = read_pos(a);
                    const auto pb = read_pos(b);
                    log::get()->info("SpawnReplay: circling a=({:.1f},{:.1f},{:.1f}) b=({:.1f},{:.1f},{:.1f}) player=({:.1f},{:.1f},{:.1f})",
                                     pa.x, pa.y, pa.z, pb.x, pb.y, pb.z, px, py, pz);
                }
            }
            log::get()->info("SpawnReplay: circling thread done");
            return 0;
        }

        // Capture the REAL spawn calls: hook the spawn-by-template API FUN_005fd730 and log
        // its args (the template hash id!) + caller as the game spawns NPCs around the player.
        struct ProbeSpawnApi {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                g_last_spawn_arg.store(mem::read<std::uint32_t>(r.esp + 4),
                                       std::memory_order_relaxed);
                const auto n = g_new_logs.fetch_add(1, std::memory_order_relaxed);
                if (n < 300) {
                    const auto ret = mem::read<std::uintptr_t>(r.esp);
                    log::get()->info("SpawnApi: this=0x{:X} arg=0x{:X} ret=0x{:X}", r.ecx,
                                     mem::read<std::uintptr_t>(r.esp + 4), ret);
                }
                // === THE HIJACK ===
                // Rewrite the template-hash argument of a live engine spawn call: the engine's
                // own streaming pipeline then spawns OUR archetype - full create + transform +
                // children + registration, all done by the engine itself.
                const auto c  = g_replay_count.fetch_add(1, std::memory_order_relaxed);
                auto       st = g_replay_state.load(std::memory_order_relaxed);
                std::uint32_t hijack = 0;
                if (st == 0 && c >= 5) {
                    hijack = 0x462A56BC;
                } else if (st == 1 && c >= 15) {
                    hijack = 0x4718F87C;
                }
                if (hijack != 0 && g_replay_state.compare_exchange_strong(st, st + 1)) {
                    g_hijack_target.store(hijack == 0x462A56BC ? 1 : 2, std::memory_order_relaxed);
                    mem::write<std::uint32_t>(r.esp + 4, hijack);
                    g_expect_return.store(true, std::memory_order_relaxed);
                    log::get()->info("SpawnReplay: HIJACKED a live spawn call -> 0x{:X}", hijack);
                }
            }
        };

        // Capture the requesters of the node-copy primitive FUN_00503600 - those are the
        // engine's actual character-creation callers (the free-roam spawn paths).
        struct ProbeCopy {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto n = g_new_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 300) {
                    return;
                }
                const auto ret = mem::read<std::uintptr_t>(r.esp);
                log::get()->info("SpawnWho2: copy this=0x{:X} ret=0x{:X} a1=0x{:X} a2=0x{:X}", r.ecx,
                                 ret, mem::read<std::uintptr_t>(r.esp + 4),
                                 mem::read<std::uintptr_t>(r.esp + 8));
            }
        };

        // Capture the true spawn requesters: hook the descriptor allocator FUN_00a38120 and
        // log its caller whenever the descriptor = a character/node class.
        // Broadened alloc trace (v10): log the FIRST occurrence of every unique
        // (class-ctor, caller) pair seen while the capture is armed - a complete map of the
        // object-creation call graph. (Entity body ctor = 0x52B750, desc 0x2760EF0.)
        struct ProbeAlloc {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto desc = mem::read<std::uintptr_t>(r.esp + 4);
                if (desc < 0x10000 || !readable(desc + 0x34, 4)) {
                    return;
                }
                const auto ctor = mem::read<std::uint32_t>(desc + 0x30);
                if (ctor < 0x401000 || ctor > 0x2400000) {
                    return;
                }
                const auto ret =
                    static_cast<std::uint32_t>(mem::read<std::uintptr_t>(r.esp));
                const auto n = g_alloc_pair_n.load(std::memory_order_relaxed);
                for (int i = 0; i < n && i < 768; ++i) {
                    if (g_alloc_pairs[i].ctor == ctor && g_alloc_pairs[i].ret == ret) {
                        ++g_alloc_pairs[i].count;
                        return;
                    }
                }
                if (n >= 768) {
                    return;
                }
                auto &p = g_alloc_pairs[n];
                p.ctor = ctor;
                p.ret = ret;
                p.desc = static_cast<std::uint32_t>(desc);
                p.count = 1;
                g_alloc_pair_n.store(n + 1, std::memory_order_relaxed);
                log::get()->info("AllocTrace: pair#{} ctor=0x{:X} ret=0x{:X} desc=0x{:X}", n + 1,
                                 ctor, ret, static_cast<std::uint32_t>(desc));
            }
        };

        // v11: the Entity class constructor (VA 0x52B750, desc 0x2760EF0) hooked directly so
        // EVERY Entity-object creation is caught with its caller - regardless of the path.
        // The citizens' builder will appear here; its caller RVA is the target.
        struct ProbeEntCtor {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto n = g_entctor_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 2000) {
                    return;
                }
                log::get()->info("EntCtor: ret=0x{:X} this=0x{:X}",
                                 static_cast<std::uintptr_t>(mem::read<std::uintptr_t>(r.esp)),
                                 static_cast<std::uintptr_t>(r.ecx));
            }
        };

        // B1 probe: log every character-node construction (ctor FUN_0052a4a0) with its caller.
        // Re-armed for GAMEPLAY capture: silent during load, active in the capture window
        // (the crowd streamer's spawn calls reveal the free-roam spawn path).
        struct ProbeNodeCtor {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto n = g_node_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 1000) {
                    return;
                }
                const auto ret = mem::read<std::uintptr_t>(r.esp);
                const auto a1  = mem::read<std::uintptr_t>(r.esp + 4);
                const auto a2  = mem::read<std::uintptr_t>(r.esp + 8);
                log::get()->info("SpawnProbe: node ctor this=0x{:X} ret=0x{:X} a1=0x{:X} a2=0x{:X}",
                                 r.ecx, ret, a1, a2);
            }
        };

        // B2 probe: log every generic class instantiation (FUN_00a359c0) with its class
        // descriptor (param_4 = [esp+0xC]) and the descriptor's first dwords (hash/size/ctor).
        struct ProbeNew {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (!g_spawn_capture.load(std::memory_order_relaxed)) {
                    return;
                }
                const auto n = g_new_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 60) {
                    return;
                }
                const auto desc = mem::read<std::uintptr_t>(r.esp + 0x0C);
                std::uint32_t d0 = 0, d1 = 0, d2 = 0, d3 = 0;
                if (desc >= 0x10000) {
                    d0 = mem::read<std::uint32_t>(desc);
                    d1 = mem::read<std::uint32_t>(desc + 4);
                    d2 = mem::read<std::uint32_t>(desc + 8);
                    d3 = mem::read<std::uint32_t>(desc + 0x0C);
                }
                log::get()->info("SpawnProbe: new desc=0x{:X} d=0x{:X} 0x{:X} 0x{:X} 0x{:X} ret=0x{:X}",
                                 desc, d0, d1, d2, d3, mem::read<std::uintptr_t>(r.esp));
            }
        };

        // StateProbe: read-only locomotion-state sampler (cap 4000 entries, 10 Hz, on change).
        auto state_probe_tick(const Vec3 &pos) -> void {
            if (g_sp_count >= 4000) {
                return;
            }
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            if (freq <= 0 || (g_sp_last_qpc != 0 && now.QuadPart - g_sp_last_qpc < freq / 10)) {
                return;
            }
            refresh_act_ctl(pos);
            const auto ctl = g_act_ctl;
            if (ctl == 0 || !readable(ctl + 0x8D0, 0x18) || !readable(ctl + 0x138, 4)) {
                return;
            }
            std::uint8_t raw[0x18];
            bool         same = true;
            for (int i = 0; i < 0x18; i++) {
                raw[i] = mem::read<std::uint8_t>(ctl + 0x8D0 + i);
                if (raw[i] != g_sp_last[i]) {
                    same = false;
                }
            }
            const auto f138 = mem::read<std::uint32_t>(ctl + 0x138);
            if (same && f138 == g_sp_last_f138) {
                g_sp_last_qpc = now.QuadPart;
                return;
            }
            for (int i = 0; i < 0x18; i++) {
                g_sp_last[i] = raw[i];
            }
            g_sp_last_f138 = f138;
            g_sp_last_qpc  = now.QuadPart;
            g_sp_count++;
            const char *digits = "0123456789abcdef";
            char        hex[0x31];
            for (int i = 0; i < 0x18; i++) {
                hex[i * 2]     = digits[raw[i] >> 4];
                hex[i * 2 + 1] = digits[raw[i] & 0xFU];
            }
            hex[0x30] = 0;
            log::get()->info(
                "StateProbe: ctl=0x{:X} b8D0..8E8={} f138=0x{:X} blend={} hang={} phase={}",
                ctl, hex, f138, raw[4], raw[8], raw[0x10]);
        }

        // CullWatch (P1 oracle): samples the ghost body's lifecycle fields at 10 Hz and logs
        // only CHANGES - vtable, children count (+0x66), scene-ref fields (+0x68/+0xC8/+0xE8),
        // the moment the object goes unreadable (freed), or a body replace/loss. This is what
        // tells the zone-crossing test apart: destroyed vs detached vs merely re-picked.
        auto cull_watch_tick() -> void {
            LARGE_INTEGER now {};
            QueryPerformanceCounter(&now);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            if (freq <= 0) {
                return;
            }
            if (g_cw_last_qpc != 0 && now.QuadPart - g_cw_last_qpc < freq / 10) {
                return;
            }
            g_cw_last_qpc = now.QuadPart;

            const auto gs   = games::ac::blackflag::coop::ghost::status();
            const auto body = gs.have_body ? gs.body : 0;

            if (body != g_cw_body) {
                if (g_cw_body != 0) {
                    log::get()->info(
                        "CullWatch: body 0x{:X} -> 0x{:X} ({}), last vt=0x{:X} ch={} f68=0x{:X} "
                        "fC8=0x{:X} fE8=0x{:X}{}",
                        g_cw_body, body, gs.have_body ? "replace" : "LOST",
                        g_cw_last.vt, g_cw_last.children, g_cw_last.f68, g_cw_last.fc8, g_cw_last.fe8,
                        g_cw_dead ? " (was freed/unreadable)" : "");
                }
                g_cw_body = body;
                g_cw_dead = false;
                g_cw_last = {};
                if (body != 0) {
                    log::get()->info("CullWatch: watching body 0x{:X}", body);
                }
                return;
            }
            if (body == 0 || g_cw_dead) {
                return;
            }
            if (!readable(body + 0xF0, 4)) {
                log::get()->warn(
                    "CullWatch: body 0x{:X} UNREADABLE (freed/unmapped); last vt=0x{:X} ch={} "
                    "f68=0x{:X} fC8=0x{:X} fE8=0x{:X}",
                    body, g_cw_last.vt, g_cw_last.children, g_cw_last.f68, g_cw_last.fc8, g_cw_last.fe8);
                g_cw_dead = true;
                return;
            }
            CwSample s {};
            s.valid    = true;
            s.vt       = mem::read<std::uint32_t>(body);
            s.children = mem::read<std::uint16_t>(body + 0x66);
            s.f68      = mem::read<std::uint32_t>(body + 0x68);
            s.fc8      = mem::read<std::uint32_t>(body + 0xC8);
            s.fe8      = mem::read<std::uint32_t>(body + 0xE8);
            if (g_cw_last.valid) {
                if (s.vt != g_cw_last.vt) {
                    log::get()->info("CullWatch: 0x{:X} vt 0x{:X} -> 0x{:X}", body, g_cw_last.vt, s.vt);
                }
                if (s.children != g_cw_last.children) {
                    log::get()->info("CullWatch: 0x{:X} children {} -> {}", body, g_cw_last.children,
                                     s.children);
                }
                if (s.f68 != g_cw_last.f68) {
                    log::get()->info("CullWatch: 0x{:X} f68 0x{:X} -> 0x{:X}", body, g_cw_last.f68,
                                     s.f68);
                }
                if (s.fc8 != g_cw_last.fc8) {
                    log::get()->info("CullWatch: 0x{:X} fC8 0x{:X} -> 0x{:X}", body, g_cw_last.fc8,
                                     s.fc8);
                }
                if (s.fe8 != g_cw_last.fe8) {
                    log::get()->info("CullWatch: 0x{:X} fE8 0x{:X} -> 0x{:X}", body, g_cw_last.fe8,
                                     s.fe8);
                }
            }
            g_cw_last = s;
        }

        struct SampleCamera {
            [[maybe_unused]] static constexpr std::string_view name = "PlayerTransform";

            [[maybe_unused]] static void operator()(mem::Registers & /*regs*/) {
                Vec3 pos {};
                Vec4 quat {0.0F, 0.0F, 0.0F, 1.0F};
                bool have = false;
                std::uintptr_t mgr = 0;

                if (g_cam_mgr_slot != 0 && readable(g_cam_mgr_slot, 4)) {
                    mgr = mem::read<std::uintptr_t>(g_cam_mgr_slot);
                }

                // Preferred: the player's own body transform (feet + facing quat).
                have = read_body_transform(mgr, pos, quat);

                // Fallback: the camera ring (previous behaviour).
                if (!have && mgr != 0 && readable(mgr + k_counter_off, 4)) {
                    const auto idx =
                        mem::read<std::uint32_t>(mgr + k_counter_off) % k_ring_len;
                    const auto p = mgr + k_pos_ring + (idx * k_ring_stride);
                    const auto q = mgr + k_quat_ring + (idx * k_ring_stride);
                    if (readable(p, 12) && readable(q, 16)) {
                        pos  = mem::read<Vec3>(p);
                        quat = mem::read<Vec4>(q);
                        have = finite3(pos);
                    }
                }

                // B4 read side: player locomotion fields -> packed anim_state.
                // Layout (shared with the ghost replay): blend<<24 | phase<<16 | flags(3)<<8 | hang.
                // Fields mapped from live captures 2026-10-08 (see MODLOG B4 table).
                if (have && g_act_read_enabled) {
                    refresh_act_ctl(pos);
                    if (g_act_ctl != 0) {
                        const auto phase = mem::read<std::uint8_t>(g_act_ctl + 0x8E0);
                        const auto hang  = mem::read<std::uint8_t>(g_act_ctl + 0x8D8);
                        const auto blend = mem::read<std::uint8_t>(g_act_ctl + 0x8D4);
                        const auto f8d0  = mem::read<std::uint32_t>(g_act_ctl + 0x8D0);
                        const auto fl    = (mem::read<std::uint32_t>(g_act_ctl + 0x138) & 1U) |
                                           ((f8d0 & 1U) << 1) |
                                           (((f8d0 >> 8) & 1U) << 2);
                        g_last_anim_state = (static_cast<std::uint32_t>(blend) << 24) |
                                            (static_cast<std::uint32_t>(phase) << 16) |
                                            (static_cast<std::uint32_t>(fl) << 8) |
                                            hang;
                    }
                }

                using namespace games::ac::blackflag::coop;
                publish(pos.x, pos.y, pos.z, quat.x, quat.y, quat.z, quat.w, g_last_anim_state);
                poll();
                {
                    std::vector<CoopEvent> events;
                    if (drain_events(events) > 0) {
                        for (const auto &ev : events) {
                            log::get()->info("CoopNet: received event kind={} id={} from={} len={}",
                                             ev.kind, ev.event_id, ev.from, ev.len);
                            games::ac::blackflag::coop::combat::on_event(ev);
                        }
                    }
                }
                if (have) {
                    g_world_seen.store(true, std::memory_order_relaxed);
                    // v5: only accept a real world position (rejects the (0,0,0) / Animus
                    // loading-screen values so spawned objects are placed next to the player).
                    if ((std::fabs(pos.x) + std::fabs(pos.y) + std::fabs(pos.z)) > 20.0F) {
                        g_last_pos = pos;
                        LARGE_INTEGER pt {};
                        QueryPerformanceCounter(&pt);
                        g_last_pos_t0 = pt.QuadPart;
                    }
                    g_last_quat = quat;
                    static bool logged_ct = false;
                    if (!logged_ct) {
                        logged_ct = true;
                        log::get()->info("ThreadCensus: camera hook on thread {}",
                                         GetCurrentThreadId());
                    }
                    if (g_clone_test.load(std::memory_order_relaxed)) {
                        clone_test_start(); // plugin thread - the game never blocks
                    }
                }
                if (have) {
                    ghost::tick(pos.x, pos.y, pos.z, latest_remote());
                    nav::tick(pos.x, pos.y, pos.z);
                    if (g_clone_live.load(std::memory_order_relaxed)) {
                        clone_live_tick(pos);
                    }
                    if (g_spawn_test.load(std::memory_order_relaxed) && !g_spawn_test_done) {
                        spawn_test_tick(pos);
                    }
                    if (g_spawnq_pending && g_spawnq_obj != 0) {
                        const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                        LARGE_INTEGER nowt {};
                        QueryPerformanceCounter(&nowt);
                        const bool fresh = g_last_pos_t0 != 0 && freq > 0 &&
                                           (nowt.QuadPart - g_last_pos_t0) <= freq * 3;
                        const bool valid =
                            (std::fabs(g_last_pos.x) + std::fabs(g_last_pos.y) +
                             std::fabs(g_last_pos.z)) > 20.0F;
                        if (fresh && valid && readable(g_spawnq_obj + 0x10, 0x40)) {
                            alignas(16) float mm[16];
                            std::memcpy(mm,
                                        reinterpret_cast<const void *>(g_spawnq_obj + 0x10),
                                        sizeof(mm));
                            mm[12] = g_last_pos.x + 2.5F;
                            mm[13] = g_last_pos.y;
                            mm[14] = g_last_pos.z;
                            mm[15] = 1.0F;
                            std::memcpy(reinterpret_cast<void *>(g_spawnq_obj + 0x10), mm,
                                        sizeof(mm));
                            g_spawnq_pending = false;
                            log::get()->info("SpawnTest v5: DEFERRED placement done at "
                                             "({:.1f},{:.1f}) - LOOK 2.5 m EAST",
                                             static_cast<double>(mm[12]),
                                             static_cast<double>(mm[13]));
                        }
                    }
                    if (g_spawnq_stage == 1 && g_spawnq_obj != 0) {
                        const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                        LARGE_INTEGER nowt {};
                        QueryPerformanceCounter(&nowt);
                        const auto el = (freq > 0) ? (nowt.QuadPart - g_spawnq_t0) / freq : 0;
                        if (g_spawnq_step == 0 && el >= 1) {
                            g_spawnq_step = 1;
                            spawnq_fields("SpawnTest v3: obj@1s", g_spawnq_obj);
                        } else if (g_spawnq_step == 1 && el >= 4) {
                            g_spawnq_step = 2;
                            spawnq_fields("SpawnTest v3: obj@4s", g_spawnq_obj);
                            if (!g_v16_done && g_v16_obj != 0) {
                                g_v16_done = true;
                                attach_graphics_try(g_v16_obj);
                            }
                        } else if (g_spawnq_step == 2 && el >= 10) {
                            g_spawnq_step = 3;
                            spawnq_fields("SpawnTest v3: obj@10s", g_spawnq_obj);
                        } else if (g_spawnq_step == 3 && el >= 30) {
                            g_spawnq_step = 4;
                            spawnq_fields("SpawnTest v3: obj@30s", g_spawnq_obj);
                        } else if (g_spawnq_step == 4 && el >= 60) {
                            g_spawnq_step = 5;
                            spawnq_fields("SpawnTest v3: obj@60s", g_spawnq_obj);
                        }
                    }
                    // v18: record-handle share (MODLOG 49 exp A): find a RENDERED body near the
                    // player and give the clone its +0xC8 record handle (refcount incremented),
                    // so the record-driven passes treat the clone like that world entity.
                    if (!g_hswap_done && g_hswap_clone != 0) {
                        const auto    freq = g_qpc_freq.load(std::memory_order_relaxed);
                        LARGE_INTEGER nowt {};
                        QueryPerformanceCounter(&nowt);
                        if (freq > 0 && nowt.QuadPart - g_spawnq_t0 >= freq * 4) {
                            g_clone_live_cand_n = 0;
                            const auto hs_end = (g_hswap_cursor + (8U << 20U)) < 0x50000000U
                                                    ? g_hswap_cursor + (8U << 20U)
                                                    : 0x50000000U;
                            clone_live_scan(g_hswap_cursor, hs_end, g_last_pos);
                            g_hswap_cursor = hs_end;
                            for (int i = 0; i < g_clone_live_cand_n; ++i) {
                                const auto &cd = g_clone_live_cands[i];
                                if (cd.addr == g_hswap_clone) {
                                    continue;
                                }
                                if (cd.ch < 16 || cd.ch > 30) {
                                    continue;
                                }
                                if (std::fabs(cd.f7c + 0.5F) > 0.01F) {
                                    continue;
                                }
                                if (!readable(cd.addr + 0xCC, 4)) {
                                    continue;
                                }
                                const auto fac = mem::read<std::uint32_t>(cd.addr + 0xAC);
                                if (!fac) {
                                    continue; // must be a RENDERED body (graphics bound)
                                }
                                const auto hd = mem::read<std::uint32_t>(cd.addr + 0xC8);
                                if (!hd || !readable(hd + 8, 4)) {
                                    continue;
                                }
                                const auto rc = mem::read<std::uint32_t>(hd + 4);
                                (void)poke_u32(hd + 4, rc + 1);
                                const auto oldh = mem::read<std::uint32_t>(g_hswap_clone + 0xC8);
                                (void)poke_u32(g_hswap_clone + 0xC8, hd);
                                g_hswap_done = true;
                                log::get()->info(
                                    "HShare: body 0x{:X} handle=0x{:X} (rc {}->{}) -> clone 0x{:X} "
                                    "(old=0x{:X})",
                                    cd.addr, hd, rc, rc + 1, g_hswap_clone, oldh);
                                spawnq_fields("HShare: clone after swap", g_hswap_clone);
                                break;
                            }
                            if (!g_hswap_done && g_hswap_cursor >= 0x50000000U) {
                                g_hswap_done = true;
                                log::get()->warn("HShare: no rendered body found");
                            }
                        }
                    }
                    adopt_tick();
                }
                if (g_cull_watch.load(std::memory_order_relaxed)) {
                    cull_watch_tick();
                }
                state_probe_tick(pos);
                {
                    const auto in_world = have && ((std::fabs(pos.x) + std::fabs(pos.y) +
                                                    std::fabs(pos.z)) > 1.0F);
                    games::ac::blackflag::coop::combat::tick(in_world);
                }

                // P2: feed the marker overlay. Camera pose from the manager ring (the same
                // history the read path uses); ghost position from the driven body.
                {
                    float cpos[3] = {pos.x, pos.y, pos.z};
                    float cquat[4] = {quat.x, quat.y, quat.z, quat.w};
                    if (mgr != 0 && readable(mgr + k_counter_off, 4)) {
                        const auto idx =
                            mem::read<std::uint32_t>(mgr + k_counter_off) % k_ring_len;
                        const auto rp = mgr + k_pos_ring + (idx * k_ring_stride);
                        const auto rq = mgr + k_quat_ring + (idx * k_ring_stride);
                        if (readable(rp, 12) && readable(rq, 16)) {
                            const Vec3 cp = mem::read<Vec3>(rp);
                            const Vec4 cq = mem::read<Vec4>(rq);
                            if (finite3(cp)) {
                                cpos[0]  = cp.x;
                                cpos[1]  = cp.y;
                                cpos[2]  = cp.z;
                                cquat[0] = cq.x;
                                cquat[1] = cq.y;
                                cquat[2] = cq.z;
                                cquat[3] = cq.w;
                            }
                        }
                    }
                    float gpos[3] = {0.0F, 0.0F, 0.0F};
                    bool  gvalid  = false;
                    const auto gs2 = ghost::status();
                    if (gs2.have_body && readable(gs2.body + 0x48, 4)) {
                        const Vec3 gp = mem::read<Vec3>(gs2.body + 0x40);
                        if (finite3(gp)) {
                            gpos[0] = gp.x;
                            gpos[1] = gp.y;
                            gpos[2] = gp.z;
                            gvalid  = true;
                        }
                    }
                    const float ppos[3] = {pos.x, pos.y, pos.z};
                    overlay::update(cpos, cquat, gpos, gvalid, ppos);
                }

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

                const auto remote = latest_remote();
                if (have) {
                    const auto gs  = ghost::status();
                    const auto ses = session();
                    log::get()->info(
                        "PlayerTransform: pos=({:.1f},{:.1f},{:.1f}) quat=({:.3f},{:.3f},{:.3f},{:.3f}) "
                        "mgr=0x{:X} peer={} est={} {} '{}' body={}@{:X} fresh={} d={:.1f} "
                        "act=0x{:X} ph={} hang={} fl={} bl={}",
                        pos.x, pos.y, pos.z, quat.x, quat.y, quat.z, quat.w, mgr,
                        remote.valid ? 1 : 0, ses.established ? 1 : 0,
                        ses.is_host ? "host" : "guest", ses.peer_name,
                        gs.have_body ? 1 : 0, gs.body,
                        gs.peer_fresh ? 1 : 0, gs.dist, g_last_anim_state,
                        (g_last_anim_state >> 16) & 0xFF, g_last_anim_state & 0xFF,
                        (g_last_anim_state >> 8) & 0x7, (g_last_anim_state >> 24) & 0xFF);
                } else {
                    log::get()->info("PlayerTransform: no transform yet (mgr=0x{:X})", mgr);
                }
            }
        };

        // --- DamageProbe (dev): pin the exact damage-apply path ------------------------------
        // All four targets are thiscall (ecx = object, args on the stack). We log the value
        // and the RETURN ADDRESS: the caller's RVA identifies the damage/health pipeline.
        // FUN_011484b0 (RVA 0xD484B0): the raw SetLife store (u16 @ this+0x5C).
        struct ProbeSetLife {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (g_dmg_probe_logs.load(std::memory_order_relaxed) > 400) {
                    return;
                }
                g_dmg_probe_logs.fetch_add(1, std::memory_order_relaxed);
                const auto self = r.ecx;
                const auto ret  = mem::read<std::uintptr_t>(r.esp);
                const auto val  = mem::read<std::uint16_t>(r.esp + 4);
                const auto vt   = mem::read<std::uintptr_t>(self);
                log::get()->info(
                    "DamageProbe: SetLife this=0x{:X} vt=0x{:X} val={} ret=0x{:X}", self, vt,
                    val, ret);
            }
        };

        // FUN_019fb4c0 (RVA 0x15FB4C0): the NPC-interface clamped setter (+0x5C) with notify.
        struct ProbeSetLifeN {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (g_dmg_probe_logs.load(std::memory_order_relaxed) > 800) {
                    return;
                }
                g_dmg_probe_logs.fetch_add(1, std::memory_order_relaxed);
                const auto self = r.ecx;
                const auto ret  = mem::read<std::uintptr_t>(r.esp);
                const auto val  = mem::read<std::int32_t>(r.esp + 4);
                const auto vt   = mem::read<std::uintptr_t>(self);
                log::get()->info(
                    "DamageProbe: SetLifeN this=0x{:X} vt=0x{:X} val={} ret=0x{:X}", self, vt,
                    val, ret);
            }
        };

        // FUN_019fb280 / FUN_019fb2a0 (RVA 0x15FB280 / 0x15FB2A0): the health service sends a
        // message to its owner (FUN_009f6210/6230 -> AbstractEntityAI) - suspected on damage.
        struct ProbeMsgA {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (g_dmg_probe_logs.load(std::memory_order_relaxed) > 1100) {
                    return;
                }
                g_dmg_probe_logs.fetch_add(1, std::memory_order_relaxed);
                const auto self = r.ecx;
                const auto ret  = mem::read<std::uintptr_t>(r.esp);
                const auto a1   = mem::read<std::uintptr_t>(r.esp + 4);
                log::get()->info("DamageProbe: MsgA this=0x{:X} a1=0x{:X} ret=0x{:X}", self, a1,
                                 ret);
            }
        };

        struct ProbeMsgB {
            [[maybe_unused]] static void operator()(mem::Registers &r) {
                if (g_dmg_probe_logs.load(std::memory_order_relaxed) > 1400) {
                    return;
                }
                g_dmg_probe_logs.fetch_add(1, std::memory_order_relaxed);
                const auto self = r.ecx;
                const auto ret  = mem::read<std::uintptr_t>(r.esp);
                const auto a1   = mem::read<std::uintptr_t>(r.esp + 4);
                log::get()->info("DamageProbe: MsgB this=0x{:X} a1=0x{:X} ret=0x{:X}", self, a1,
                                 ret);
            }
        };
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_log_hz.store(cfg.log_hz.get(), std::memory_order_relaxed);
        g_act_scan_allowed.store(cfg.act_scan.get(), std::memory_order_relaxed);
        {
            const auto parse_key = [](const std::string &s, std::atomic<std::uint32_t> &lo,
                                      std::atomic<std::uint32_t> &hi) -> void {
                unsigned a = 0, b = 0;
                if (std::sscanf(s.c_str(), "%8x:%8x", &a, &b) == 2) {
                    lo.store(a, std::memory_order_relaxed);
                    hi.store(b, std::memory_order_relaxed);
                } else {
                    lo.store(0, std::memory_order_relaxed);
                    hi.store(0, std::memory_order_relaxed);
                }
            };
            parse_key(cfg.adopt_only.get(), g_adopt_only_lo, g_adopt_only_hi);
            parse_key(cfg.adopt_skip.get(), g_adopt_skip_lo, g_adopt_skip_hi);
            g_adopt_max.store(cfg.adopt_max.get(), std::memory_order_relaxed);
        }

        games::ac::blackflag::coop::NetConfig net;
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
        net.player_name = cfg.player_name.get();
        net.is_host = cfg.is_host.get();
        net.send_hz   = cfg.send_hz.get();
        games::ac::blackflag::coop::configure(net);
        games::ac::blackflag::coop::ghost::set_enabled(cfg.body_drive.get());
        games::ac::blackflag::coop::ghost::set_anim_drive(cfg.anim_drive.get());
        games::ac::blackflag::coop::ghost::set_anim_probe(cfg.anim_probe.get());
        games::ac::blackflag::coop::ghost::set_api_move(cfg.api_move.get());
        games::ac::blackflag::coop::ghost::set_params(cfg.body_min_children.get(),
                                                      static_cast<float>(cfg.body_max_dist.get()));
        g_clone_test.store(cfg.clone_test.get(), std::memory_order_relaxed);
        {
            const bool on = cfg.clone_live.get();
            if (on && !g_clone_live.load(std::memory_order_relaxed)) {
                g_clone_live_stage = 0; // rising edge re-arms the one-shot
            }
            g_clone_live.store(on, std::memory_order_relaxed);
        }
        {
            const bool on = cfg.spawn_test.get();
            if (on && !g_spawn_test.load(std::memory_order_relaxed)) {
                g_spawn_test_done = false; // rising edge re-arms the one-shot
            }
            g_spawn_test.store(on, std::memory_order_relaxed);
        }
        {
            const bool on = cfg.adopt_test.get();
            if (on && !g_adopt_test.load(std::memory_order_relaxed)) {
                g_adopt_armed   = true; // v19 rising edge: pre-create on the next tick
                g_adopt_created = false;
            }
            if (!on) {
                g_adopt_armed = false;
            }
            g_adopt_test.store(on, std::memory_order_relaxed);
        }
        g_cull_watch.store(cfg.cull_watch.get(), std::memory_order_relaxed);
        games::ac::blackflag::coop::combat::set_enabled(cfg.combat_sync.get());
        games::ac::blackflag::coop::nav::set_test(cfg.nav_test.get());
        games::ac::blackflag::coop::combat::set_kill_test(cfg.combat_kill_test.get());
        games::ac::blackflag::coop::overlay::set_enabled(cfg.marker_enabled.get());
        games::ac::blackflag::coop::overlay::set_params(cfg.marker_fov.get(),
                                                        cfg.marker_size.get(),
                                                        cfg.marker_player.get());

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
        g_cam_mgr_slot = base + k_cam_mgr_rva;
        g_exe_base     = base;
        const auto hook_addr = base + k_upd_cam_rva;
        LARGE_INTEGER lq {};
        QueryPerformanceCounter(&lq);
        g_load_qpc.store(lq.QuadPart, std::memory_order_relaxed);

        log::get()->info("PlayerTransform: base 0x{:X} hook 0x{:X} camMgrSlot 0x{:X}",
                         base, hook_addr, g_cam_mgr_slot);

        auto hook = mem::make_hook<SampleCamera>(hook_addr);
        if (!hook) {
            log::get()->error("PlayerTransform: hook failed: {}", hook.error());
            return false;
        }
        g_hook = std::move(*hook);

        // P2: install the DXGI Present hook for the partner marker overlay.
        // Gated on the config: with markers off (default and current test builds) nothing is
        // hooked or initialized at all.
        if (games::ac::blackflag::registry().config<Tag>().marker_enabled.get()) {
            games::ac::blackflag::coop::overlay::init();
        }

        // DamageProbe (dev): log health-setter + notify calls to pin the damage-apply path.
        // Enable with [Coop] ProbeDamage=true. Read-only pass-through probes.
        if (games::ac::blackflag::registry().config<Tag>().probe_damage.get()) {
            const auto setlife_addr = base + 0xD484B0; // FUN_011484b0: raw SetLife store (+0x5C)
            auto       h_setlife    = mem::make_hook<ProbeSetLife>(setlife_addr);
            if (!h_setlife) {
                log::get()->error("DamageProbe: SetLife hook failed: {}", h_setlife.error());
            } else {
                g_probe_setlife = std::move(*h_setlife);
                log::get()->info("DamageProbe: SetLife probe armed at 0x{:X}", setlife_addr);
            }
            const auto setlife_n_addr = base + 0x15FB4C0; // FUN_019fb4c0: clamped setter + notify
            auto       h_setlife_n    = mem::make_hook<ProbeSetLifeN>(setlife_n_addr);
            if (!h_setlife_n) {
                log::get()->error("DamageProbe: SetLifeN hook failed: {}", h_setlife_n.error());
            } else {
                g_probe_setlife_n = std::move(*h_setlife_n);
                log::get()->info("DamageProbe: SetLifeN probe armed at 0x{:X}", setlife_n_addr);
            }
            const auto msg_a_addr = base + 0x15FB280; // FUN_019fb280: health -> AI message (A)
            auto       h_msg_a    = mem::make_hook<ProbeMsgA>(msg_a_addr);
            if (!h_msg_a) {
                log::get()->error("DamageProbe: MsgA hook failed: {}", h_msg_a.error());
            } else {
                g_probe_msg_a = std::move(*h_msg_a);
                log::get()->info("DamageProbe: MsgA probe armed at 0x{:X}", msg_a_addr);
            }
            const auto msg_b_addr = base + 0x15FB2A0; // FUN_019fb2a0: health -> AI message (B)
            auto       h_msg_b    = mem::make_hook<ProbeMsgB>(msg_b_addr);
            if (!h_msg_b) {
                log::get()->error("DamageProbe: MsgB hook failed: {}", h_msg_b.error());
            } else {
                g_probe_msg_b = std::move(*h_msg_b);
                log::get()->info("DamageProbe: MsgB probe armed at 0x{:X}", msg_b_addr);
            }
        }

        // NavWatch (dev): read-only hooks capturing real navigation calls (targets as templates).
        // Enable with [Coop] NavWatch=true.
        if (games::ac::blackflag::registry().config<Tag>().nav_watch.get()) {
            games::ac::blackflag::coop::nav::install_watch(base);
        }

        // SpawnWatch (dev): read-only hook capturing the streamer's own spawn calls (hash harvest).
        if (games::ac::blackflag::registry().config<Tag>().spawn_watch.get()) {
            auto h = mem::make_hook<ProbeSpawnCall>(base + 0x1FD730);
            if (!h) {
                log::get()->error("SpawnWatch: hook failed: {}", h.error());
            } else {
                g_probe_spawn_call = std::move(*h);
                log::get()->info("SpawnWatch: streamer spawn hooked @0x{:X}", base + 0x1FD730);
            }
        }

        // B1: node-ctor probe (FUN_0052a4a0, RVA 0x12A4A0) - logs spawn callers at load.
        const auto probe_addr = base + 0x12A4A0;
        auto       probe      = mem::make_hook<ProbeNodeCtor>(probe_addr);
        if (!probe) {
            log::get()->error("PlayerTransform: node-ctor probe hook failed: {}", probe.error());
        } else {
            g_probe = std::move(*probe);
            log::get()->info("PlayerTransform: node-ctor probe armed at 0x{:X}", probe_addr);
        }

        // B2: generic-instantiation probe DISABLED (suspected thunk entry caused 1-fps menu +
        // crash). Re-enable later by hooking past the entry jump.

        // B3: main-thread hook for the clone test. FUN_00407390 = the per-frame game update
        // called inside the window loop FUN_004060a0 (runs until WM_QUIT = the whole session).
        // Hook it, NOT the loop entry - a mid-hook on the entry only fires once (back-edge).
        const auto main_addr = base + 0x7390;
        auto       main_hook = mem::make_hook<ProbeMain>(main_addr);
        if (!main_hook) {
            log::get()->error("PlayerTransform: main-loop hook failed: {}", main_hook.error());
        } else {
            g_probe_main = std::move(*main_hook);
            log::get()->info("PlayerTransform: main-loop hook armed at 0x{:X}", main_addr);
        }

        // Clone-call probe (FUN_006deff0, RVA 0x2DEFF0): log every engine-side clone invocation.
        const auto clone_addr = base + 0x2DEFF0;
        auto       clone_hook = mem::make_hook<ProbeClone>(clone_addr);
        if (!clone_hook) {
            log::get()->error("PlayerTransform: clone-probe hook failed: {}", clone_hook.error());
        } else {
            g_probe_new = std::move(*clone_hook);
            log::get()->info("PlayerTransform: clone-probe armed at 0x{:X}", clone_addr);
        }

        // CloneTest micro-probes: log the clone chain's steps (gated on CloneTest).
        const auto install_probe = [&](const char *tag, std::uintptr_t rva, auto *holder,
                                       auto &&mk) -> void {
            const auto addr = base + rva;
            auto       h    = mem::make_hook<decltype(mk)>(addr);
            if (!h) {
                log::get()->error("PlayerTransform: {} probe hook failed: {}", tag, h.error());
            } else {
                *holder = std::move(*h);
                log::get()->info("PlayerTransform: {} probe armed at 0x{:X}", tag, addr);
            }
        };
        install_probe("job-post", 0x62DAE0, &g_probe_jobpost, ProbeJobPost {});
        install_probe("job-desc", 0x62DBD0, &g_probe_jobdesc, ProbeJobDesc {});
        install_probe("job-ctx", 0x62D4F0, &g_probe_jobctx, ProbeJobCtx {});
        install_probe("alloc", 0x638120, &g_probe_alloc, ProbeAlloc {});
        install_probe("new", 0x6359C0, &g_probe_inst, ProbeNew {});
        // v11 entctor hook REVERTED: hooking the Entity ctor (0x52B750) hung the game at
        // startup (windowless, log stopped right after plugin init). Do not re-enable as-is.
        install_probe("copy", 0x103600, &g_probe_copy, ProbeCopy {});
        install_probe("spawnapi", 0x1FD730, &g_probe_spawnapi, ProbeSpawnApi {});
        install_probe("spawnret", 0x202CE0, &g_probe_spawnret, ProbeSpawnRet {});
        install_probe("masscreate", 0x6201A0, &g_probe_masscreate, ProbeMassCreate {});
        install_probe("reqwatch", 0x16D9190, &g_probe_reqwatch, ProbeReqWatch {});
        install_probe("animapply", 0x16C1AD0, &g_probe_animapply, ProbeAnimApply {});
        install_probe("animwrite", 0x16B52C0, &g_probe_animwrite, ProbeAnimWrite {});
        g_jobenq_addr = base + 0x639360; // FUN_00a39360 - patched to ret 0x14 during the clone

        on_reload(games::ac::blackflag::registry().config<Tag>());
        log::get()->info("PlayerTransform: installed");
        return true;
    }
} // namespace hooks
