#include "games/ac/rogue/hooks/combat_tweaks.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <thread>
#include <vector>

#include <Windows.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/write.hpp"

#include "games/ac/rogue/registry.hpp"

namespace hooks {
    namespace {
        using Tag = games::ac::rogue::CombatTweaksHook;

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
        std::atomic<bool>  g_apply_no_block {false};
        std::atomic<float> g_block_hold {999.0F};
        std::atomic<float> g_counter_input {-1.0F};
        std::atomic<float> g_ai_aggression {1.0F};
        std::atomic<bool>  g_no_chain {false};
        std::atomic<std::uintptr_t> g_block_addr {0};
#pragma clang diagnostic pop

        // True if the 11-float OpenWindowRatio run sits within 0x100 bytes before `hit`.
        // Identifies the real FightSettings object (rejects false positives).
        auto has_owr_before(std::uintptr_t hit) -> bool {
            const float owr[11] = {0.75F, 0.75F, 0.5F, 0.6F, 0.7F, 0.75F, 0.4F, 0.75F, 0.35F, 0.75F, 0.3F};
            constexpr std::size_t olen = sizeof(owr);
            constexpr std::size_t back = 0x100;
            if (hit < back) {
                return false;
            }
            std::array<std::uint8_t, back + olen> buf {};
            SIZE_T                                got = 0;
            if (ReadProcessMemory(GetCurrentProcess(),
                                  reinterpret_cast<LPCVOID>(hit - back),
                                  buf.data(),
                                  buf.size(),
                                  &got) == 0 ||
                got < buf.size()) {
                return false;
            }
            std::uint8_t needle[olen];
            std::memcpy(needle, owr, olen);
            for (std::size_t i = 0; i + olen <= buf.size(); ++i) {
                if (buf[i] == needle[0] && std::memcmp(buf.data() + i, needle, olen) == 0) {
                    return true;
                }
            }
            return false;
        }

        // Search committed writable regions for the 7-float counter run. Returns the
        // address of the run, or 0 if not exactly one hit. Reads via ReadProcessMemory so a
        // guard/unreadable page cannot fault the (unguarded) scan thread.
        auto find_counter_block() -> std::uintptr_t {
            const float           pat[7] = {0.3F, 0.04F, 0.012F, 0.8F, 0.3F, 0.2F, 0.2F};
            constexpr std::size_t plen   = sizeof(pat);
            std::uint8_t          needle[plen];
            std::memcpy(needle, pat, plen);

            HANDLE self = GetCurrentProcess();
            SYSTEM_INFO si {};
            GetSystemInfo(&si);
            auto addr = reinterpret_cast<std::uintptr_t>(si.lpMinimumApplicationAddress);
            const auto maxa = reinterpret_cast<std::uintptr_t>(si.lpMaximumApplicationAddress);

            constexpr std::size_t     k_chunk = 8U << 20;
            std::vector<std::uint8_t> buf(k_chunk);
            std::vector<std::uintptr_t> found;
            int                       regions = 0;
            MEMORY_BASIC_INFORMATION  mbi {};
            while (addr < maxa &&
                   VirtualQuery(reinterpret_cast<LPCVOID>(addr), &mbi, sizeof(mbi)) != 0) {
                const auto base = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
                const auto size = static_cast<std::size_t>(mbi.RegionSize);
                const bool ok =
                    mbi.State == MEM_COMMIT &&
                    (mbi.Protect & (PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READWRITE |
                                    PAGE_EXECUTE_WRITECOPY)) != 0 &&
                    (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) == 0;
                if (ok && size >= plen) {
                    ++regions;
                    std::size_t off = 0;
                    while (off < size && found.size() < 16) {
                        const std::size_t len = std::min<std::size_t>(k_chunk, size - off);
                        SIZE_T            got = 0;
                        if (ReadProcessMemory(self,
                                              reinterpret_cast<LPCVOID>(base + off),
                                              buf.data(),
                                              len,
                                              &got) == 0 ||
                            got < plen) {
                            break;
                        }
                        const auto n = static_cast<std::size_t>(got);
                        for (std::size_t i = 0; i + plen <= n; ++i) {
                            if (buf[i] == needle[0] && std::memcmp(buf.data() + i, needle, plen) == 0) {
                                const auto a = base + off + i;
                                if (found.empty() || a - found.back() >= plen) {
                                    found.push_back(a);
                                }
                                i += plen - 1;
                            }
                        }
                        if (len < k_chunk) {
                            break;
                        }
                        off += k_chunk - (plen - 1);
                    }
                }
                if (size == 0) {
                    break;
                }
                addr = base + size;
                if (found.size() >= 16) {
                    break;
                }
            }
            // Keep only hits that sit just after the OpenWindowRatio run (the real object).
            std::uintptr_t chosen = 0;
            int            good   = 0;
            for (const auto a : found) {
                if (has_owr_before(a)) {
                    chosen = a;
                    ++good;
                }
            }
            log::get()->info("CombatTweaks: scan regions={} hits={} owr-qualified={} first=0x{:X}",
                             regions,
                             found.size(),
                             good,
                             chosen);
            return good == 1 ? chosen : 0;
        }

        auto read_floats(std::uintptr_t addr, float *out) -> bool {
            SIZE_T got = 0;
            return ReadProcessMemory(GetCurrentProcess(),
                                     reinterpret_cast<LPCVOID>(addr),
                                     out,
                                     sizeof(float) * 8,
                                     &got) != 0 &&
                   got == sizeof(float) * 8;
        }

        // The FightPacingSetting tiers sit just after the counter block in the same object.
        // indices: 0/1 FightActions Max/Min, 2/3 KillStreakActions, 4/5 FightDecisions, 6/7 KillStreakDecisions.
        void apply_tiers(std::uintptr_t run) {
            const float agg      = g_ai_aggression.load(std::memory_order_relaxed);
            const bool  no_chain = g_no_chain.load(std::memory_order_relaxed);
            if (agg >= 0.999F && !no_chain) {
                return;
            }
            const std::uintptr_t addrs[2] = {run + 0x29C, run + 0x34C};
            const char          *names[2] = {"LowHealth", "Basic"};
            for (int t = 0; t < 2; ++t) {
                float v[8];
                if (!read_floats(addrs[t], v)) {
                    continue;
                }
                if (v[0] < 0.05F || v[0] > 3.5F || v[4] < 0.05F || v[4] > 3.5F) {
                    log::get()->warn("CombatTweaks: tier {} looks wrong ({:.2f},{:.2f}) - skip",
                                     names[t],
                                     v[0],
                                     v[4]);
                    continue;
                }
                v[0] *= agg;
                v[1] *= agg;
                v[4] *= agg;
                v[5] *= agg;
                if (no_chain) {
                    v[2] = 5.0F;
                    v[3] = 5.0F;
                    v[6] = 5.0F;
                    v[7] = 5.0F;
                }
                for (int i = 0; i < 8; ++i) {
                    mem::write<float>(addrs[t] + (static_cast<std::uintptr_t>(i) * sizeof(float)), v[i]);
                }
                log::get()->info(
                    "CombatTweaks: tier {} -> [{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f}]",
                    names[t],
                    v[0],
                    v[1],
                    v[2],
                    v[3],
                    v[4],
                    v[5],
                    v[6],
                    v[7]);
            }
        }

        auto apply_once() -> bool {
            const auto run = find_counter_block();
            if (run == 0) {
                return false;
            }
            g_block_addr.store(run, std::memory_order_relaxed);
            const auto btn = run + (games::ac::rogue::k_idx_time_button_held * sizeof(float));
            const auto civ = run + (games::ac::rogue::k_idx_counter_input_val * sizeof(float));
            log::get()->info("CombatTweaks: counter block 0x{:X} (buttonHeld=0x{:X}, inputValid=0x{:X})",
                             run,
                             btn,
                             civ);

            if (g_apply_no_block.load(std::memory_order_relaxed)) {
                const float v = g_block_hold.load(std::memory_order_relaxed);
                if (mem::write<float>(btn, v)) {
                    log::get()->info("CombatTweaks: TimeButtonHeldForParry -> {:.1f} (block disabled)", v);
                }
            }
            const float cv = g_counter_input.load(std::memory_order_relaxed);
            if (cv >= 0.0F) {
                if (mem::write<float>(civ, cv)) {
                    log::get()->info("CombatTweaks: TimeCounterInputIsValid -> {:.3f}", cv);
                }
            }
            apply_tiers(run);
            return true;
        }
    } // namespace

    void HookTraits<Tag>::on_reload(const Config &cfg) {
        g_apply_no_block.store(cfg.no_block.get(), std::memory_order_relaxed);
        g_block_hold.store(cfg.block_hold_seconds.get(), std::memory_order_relaxed);
        g_counter_input.store(cfg.counter_input_valid.get(), std::memory_order_relaxed);
        g_ai_aggression.store(cfg.ai_aggression.get(), std::memory_order_relaxed);
        g_no_chain.store(cfg.no_chain_kills.get(), std::memory_order_relaxed);
        log::get()->info("CombatTweaks: no_block={} hold={:.1f} input_valid={:.2f} aggression={:.2f} no_chain={}",
                         cfg.no_block.get() ? "on" : "off",
                         cfg.block_hold_seconds.get(),
                         cfg.counter_input_valid.get(),
                         cfg.ai_aggression.get(),
                         cfg.no_chain_kills.get() ? "on" : "off");
        // If we already located the block, re-apply immediately on reload.
        if (const auto run = g_block_addr.load(std::memory_order_relaxed); run != 0) {
            const auto btn = run + (games::ac::rogue::k_idx_time_button_held * sizeof(float));
            const auto civ = run + (games::ac::rogue::k_idx_counter_input_val * sizeof(float));
            if (g_apply_no_block.load(std::memory_order_relaxed)) {
                mem::write<float>(btn, g_block_hold.load(std::memory_order_relaxed));
            }
            const float cv = g_counter_input.load(std::memory_order_relaxed);
            if (cv >= 0.0F) {
                mem::write<float>(civ, cv);
            }
            apply_tiers(run);
        }
    }

    auto HookTraits<Tag>::install(const Addrs &addrs) -> bool {
        (void)addrs;
        on_reload(games::ac::rogue::registry().config<Tag>());
        // The settings object does not exist at process init; locate it later off the
        // game thread so we never stall a frame.
        std::thread([]() -> void {
            for (int attempt = 0; attempt < 12; ++attempt) {
                std::this_thread::sleep_for(std::chrono::seconds(12));
                if (apply_once()) {
                    return;
                }
            }
            log::get()->warn("CombatTweaks: counter block not found after retries - skipped");
        }).detach();
        log::get()->info("CombatTweaks: installed (background locate scheduled)");
        return true;
    }
} // namespace hooks
