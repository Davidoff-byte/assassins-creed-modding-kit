#include "games/ac/blackflag/hooks/player_transform.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
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
        std::atomic<std::int64_t> g_qpc_freq {0};
        std::atomic<std::int64_t> g_last_log {0};
        std::atomic<int>          g_spawn_logs {0};
        std::atomic<int>          g_new_logs {0};
        mem::MidHook              g_hook;
        mem::MidHook              g_probe;
        mem::MidHook              g_probe_new;
        mem::MidHook              g_probe_main;
        mem::MidHook              g_probe_jobpost;
        mem::MidHook              g_probe_jobdesc;
        mem::MidHook              g_probe_jobctx;
        mem::MidHook              g_probe_alloc;
        mem::MidHook              g_probe_copy;
        mem::MidHook              g_probe_spawnapi;
        mem::MidHook              g_probe_spawnret;
        mem::MidHook              g_probe_masscreate;
        mem::MidHook              g_probe_setlife;
        mem::MidHook              g_probe_setlife_n;
        mem::MidHook              g_probe_msg_a;
        mem::MidHook              g_probe_msg_b;
        std::atomic<int>          g_dmg_probe_logs {0};
        std::atomic<bool>         g_world_seen {false};
        std::atomic<bool>         g_spawn_capture {false};
        std::uintptr_t            g_jobenq_addr = 0;
        std::uintptr_t            g_exe_base    = 0;
        Vec3                      g_last_pos {0.0F, 0.0F, 0.0F};
        Vec4                      g_last_quat {0.0F, 0.0F, 0.0F, 1.0F};

        static DWORD WINAPI replay_thread(LPVOID); // defined below (spawn replay)

        static std::uintptr_t registry_find_helper(std::uintptr_t fn, std::uint32_t k1,
                                                   std::uint32_t k2); // defined below
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
        std::atomic<std::int64_t> g_load_qpc {0};
        std::uint32_t  g_last_anim_state = 0;
        bool           g_act_read_enabled = false; // TODO: re-enable with incremental scan + backoff

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
            thread_census_tick();
            Sleep(20000); // let the world finish loading - page churn slows the scan 5x
            clone_test_tick();
            // Arm the gameplay spawn capture: walk around and the crowd streamer's node
            // creations get logged (read-only) - that's the free-roam spawn path.
            Sleep(20000);
            g_spawn_logs.store(0, std::memory_order_relaxed);
            g_spawn_capture.store(true, std::memory_order_relaxed);
            log::get()->info("SpawnCapture: armed - walk around town for ~60 s");
            // === THE ENTITY SPAWN v3: create + FETCH VIA THE REGISTRY (FUN_00a201a0 is void;
            // its return value is meaningless). One spawn only (less render risk).
            Sleep(30000);
            const std::uint32_t klo = 0x7A3C9E01;
            const std::uint32_t khi = 7;
            if (g_exe_base != 0) {
                log::get()->info("EntitySpawn: create Entity key=(0x{:X},{}) ...", klo, khi);
                spawn_keyed_helper(g_exe_base + 0x6201A0, 0x0984415E, klo, khi);
                const auto found = registry_find_helper(g_exe_base + 0x61F160, klo, khi);
                log::get()->info("EntitySpawn: registry find -> 0x{:X}", found);
                if (found >= 0x10000 && readable(found + 0x148, 4)) {
                    log::get()->info(
                        "EntitySpawn: vt=0x{:X} children={} f7c={:.2f} mark=0x{:X} d4=0x{:X}",
                        static_cast<std::uintptr_t>(mem::read<std::uint32_t>(found)),
                        mem::read<std::uint16_t>(found + 0x66),
                        static_cast<double>(mem::read<float>(found + 0x7C)),
                        mem::read<std::uintptr_t>(found + 0xC8),
                        mem::read<std::uintptr_t>(found + 4));
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

        auto find_player_ctl(const Vec3 &pos) -> std::uintptr_t {
            std::uintptr_t best  = 0;
            float         bestd = 64.0F; // 8 m squared
            LARGE_INTEGER t0 {};
            QueryPerformanceCounter(&t0);
            const auto freq = g_qpc_freq.load(std::memory_order_relaxed);
            std::uintptr_t addr = 0x10000;
            while (addr < 0x7FFF0000) {
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
            const auto dt = now.QuadPart - g_act_last_qpc;
            const bool rescan = dt > freq * 10; // full rescan every 10 s
            if (g_act_ctl != 0 && !rescan) {
                if (g_act_node != 0 && readable(g_act_node + 0x68, 4) &&
                    mem::read<std::uint32_t>(g_act_node + 0x68) == 0x04DD5F8C) {
                    return; // node still alive, keep the cached controller
                }
            }
            g_act_last_qpc = now.QuadPart;
            g_act_ctl      = find_player_ctl(pos);
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
                const auto n = g_spawn_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 300) {
                    return;
                }
                const auto a1 = mem::read<std::uintptr_t>(r.esp + 4);
                const auto a2 = mem::read<std::uintptr_t>(r.esp + 8);
                const auto a3 = mem::read<std::uintptr_t>(r.esp + 0x0C);
                const auto a4 = mem::read<std::uintptr_t>(r.esp + 0x10);
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
                if (ctor != 0x0052A4A0 && ctor != 0x00503330 && ctor != 0x006DEFA0 &&
                    ctor != 0x00504880) {
                    return;
                }
                const auto n = g_new_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 300) {
                    return;
                }
                const auto ret = mem::read<std::uintptr_t>(r.esp);
                log::get()->info("SpawnWho: desc=0x{:X} ctor=0x{:X} ret=0x{:X} alloc=0x{:X}", desc,
                                 static_cast<std::uintptr_t>(ctor), ret,
                                 mem::read<std::uintptr_t>(r.esp + 8));
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
                const auto n = g_spawn_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 300) {
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
                const auto n = g_new_logs.fetch_add(1, std::memory_order_relaxed);
                if (n >= 400) {
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

                // B4 read side: player action state -> packed anim_state.
                if (have && g_act_read_enabled) {
                    refresh_act_ctl(pos);
                    if (g_act_ctl != 0) {
                        const auto phase = mem::read<std::uint8_t>(g_act_ctl + 0x8E0);
                        const auto hang  = mem::read<std::uint8_t>(g_act_ctl + 0x8D8);
                        const auto fl    = (mem::read<std::uint32_t>(g_act_ctl + 0x138) & 1U) |
                                           ((mem::read<std::uint32_t>(g_act_ctl + 0x8D0) & 1U) << 1);
                        g_last_anim_state = (static_cast<std::uint32_t>(phase) << 16) |
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
                    g_last_pos = pos;
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
                }
                if (g_cull_watch.load(std::memory_order_relaxed)) {
                    cull_watch_tick();
                }
                state_probe_tick(pos);
                games::ac::blackflag::coop::combat::tick();

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
                        "act=0x{:X} ph={} hang={} fl={}",
                        pos.x, pos.y, pos.z, quat.x, quat.y, quat.z, quat.w, mgr,
                        remote.valid ? 1 : 0, ses.established ? 1 : 0,
                        ses.is_host ? "host" : "guest", ses.peer_name,
                        gs.have_body ? 1 : 0, gs.body,
                        gs.peer_fresh ? 1 : 0, gs.dist, g_last_anim_state,
                        (g_last_anim_state >> 16) & 0xFF, g_last_anim_state & 0xFF,
                        (g_last_anim_state >> 8) & 0x3);
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
        games::ac::blackflag::coop::ghost::set_api_move(cfg.api_move.get());
        games::ac::blackflag::coop::ghost::set_params(cfg.body_min_children.get(),
                                                      static_cast<float>(cfg.body_max_dist.get()));
        g_clone_test.store(cfg.clone_test.get(), std::memory_order_relaxed);
        g_cull_watch.store(cfg.cull_watch.get(), std::memory_order_relaxed);
        games::ac::blackflag::coop::combat::set_enabled(cfg.combat_sync.get());
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
        install_probe("copy", 0x103600, &g_probe_copy, ProbeCopy {});
        install_probe("spawnapi", 0x1FD730, &g_probe_spawnapi, ProbeSpawnApi {});
        install_probe("spawnret", 0x202CE0, &g_probe_spawnret, ProbeSpawnRet {});
        install_probe("masscreate", 0x6201A0, &g_probe_masscreate, ProbeMassCreate {});
        g_jobenq_addr = base + 0x639360; // FUN_00a39360 - patched to ret 0x14 during the clone

        on_reload(games::ac::blackflag::registry().config<Tag>());
        log::get()->info("PlayerTransform: installed");
        return true;
    }
} // namespace hooks
