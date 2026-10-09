// BFCoop nav drive: engine-native NPC navigation (CSrvNavigation::NavigateTo) — makes an NPC
// walk to a point with its own locomotion animations instead of being teleport-driven.
//
// PC-verified 2026-10-08 (live disassembly; see bf-coop/logs/ai/NAV_RESEARCH.md):
//   NavigateTo(this, NavigationTarget const*, speed, boolA, boolB, ctxID) @RVA 0x1385ED0
//   __thiscall, callee pops 0x14; returns 0 = accepted, 7 = invalid target.
//   NavigationTarget: +0x00 type (1 = Position), +0x10 Vector4 position, +0x20 reach,
//   +0x40 = unset sentinel (0x80000000 lanes). CSrvNavigation class id = 0x6328D910.
#pragma once

#include <cstdint>

namespace games::ac::blackflag::coop::nav {
    // [Coop] NavWatch — boot-gated read-only watcher: hooks CSrvNavigation::NavigateTo and
    // NPCNavigation::NavigateTo to capture real call arguments and engine-built targets.
    void install_watch(std::uintptr_t exe_base);

    // [Coop] NavTest — dev one-shot: find a CSrvNPCHealth-anchored NPC, resolve its
    // CSrvNavigation service and issue NavigateTo(player position). Fires once per enable.
    void set_test(bool on);

    // Called every frame from the PlayerTransform hook (game thread) while in world.
    void tick(float px, float py, float pz);
} // namespace games::ac::blackflag::coop::nav
