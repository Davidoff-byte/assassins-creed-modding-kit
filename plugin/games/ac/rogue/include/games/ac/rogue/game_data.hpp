#pragma once

#include <cstdint>

#include <array>
#include <optional>
#include <string_view>

#include "games/game_data.hpp"

namespace games::ac {
    struct Rogue {};
} // namespace games::ac

namespace games {
    template<>
    struct game_data<ac::Rogue> {
        static constexpr std::string_view name     = "Rogue";
        static constexpr std::string_view exe_name = "ACC.exe";

        static constexpr float k_default_aspect          = 16.0F / 9.0F;
        static constexpr float k_inv_default_aspect      = 9.0F / 16.0F;
        static constexpr float k_inv_base_width          = 1.0F / 1280.0F;
        static constexpr float k_inv_base_height         = 1.0F / 720.0F;
        static constexpr float k_fov_base_zoom           = 0.768F;
        static constexpr float k_triple_screen_threshold = 4.0F;
        static constexpr float k_float_tolerance         = 1e-6F;

        struct ResolvedAddresses {
            std::optional<std::uintptr_t> viewport_ratio_load;
            std::optional<std::uintptr_t> viewport_ratio_mul;
            std::optional<std::uintptr_t> scaling_branch_start;
            std::optional<std::uintptr_t> scaling_branch_end;
            std::optional<std::uintptr_t> display_flag;
            std::optional<std::uintptr_t> fov_store;
            std::optional<std::uintptr_t> coord_transform;
            std::optional<std::uintptr_t> scaling_offsets;
            std::optional<std::uintptr_t> game_unpause;
            std::optional<std::uintptr_t> game_pause;
            std::optional<std::uintptr_t> game_pause2;
            std::optional<std::uintptr_t> get_game_id;
            std::optional<std::uintptr_t> lang_bf_write;
            std::optional<std::uintptr_t> lang_setup;
            std::optional<std::uintptr_t> get_language;
            std::optional<std::uintptr_t> fps_timing_ptr;
            std::optional<std::uintptr_t> fps_cap_mulss;
            std::optional<std::uintptr_t> game_state_global;
            std::optional<std::uintptr_t> loc_init;
            std::optional<std::uintptr_t> mode_get_by_index;
            std::optional<std::uintptr_t> mode_list_build;
            std::optional<std::uintptr_t> mode_list_reserve_site;
            std::optional<std::uintptr_t> camera_manager_load;
            std::optional<std::uintptr_t> track_weight_site;
            std::optional<std::uintptr_t> camera_interpolate;
            std::optional<std::uintptr_t> mouse_state_update;
            std::optional<std::uintptr_t> weapon_class_get;
            std::optional<std::uintptr_t> set_fight_type;
            std::optional<std::uintptr_t> set_weapon_pose;
            std::optional<std::uintptr_t> apply_weapon_type;
            std::optional<std::uintptr_t> ai_update_camera;
            std::optional<std::uintptr_t> player_by_index;
            // Combat trace (AC Rogue single-player RE): parry/counter call chain.
            std::optional<std::uintptr_t> combat_parry;
            std::optional<std::uintptr_t> combat_counter_fail;
            std::optional<std::uintptr_t> combat_grab_countered;
            std::optional<std::uintptr_t> combat_weapon_setup;
            std::optional<std::uintptr_t> combat_pose_a;
            std::optional<std::uintptr_t> combat_pose_b;
            std::optional<std::uintptr_t> combat_fa1;
            std::optional<std::uintptr_t> combat_fa2;
            std::optional<std::uintptr_t> combat_fa3;
            std::optional<std::uintptr_t> combat_fa4;
            std::optional<std::uintptr_t> combat_fa5;
            std::optional<std::uintptr_t> combat_fa6;
            std::optional<std::uintptr_t> combat_fa7;
            std::optional<std::uintptr_t> combat_fa8;
            std::optional<std::uintptr_t> combat_fa9;
            // Counter-window phases: the `cmp [obj+0x230], id` immediates inside the
            // four parry classifiers FUN_142052de0/e10/e40/e70 (ids 0x1F6..0x1F9).
            std::optional<std::uintptr_t> counter_phase_1f6;
            std::optional<std::uintptr_t> counter_phase_1f7;
            std::optional<std::uintptr_t> counter_phase_1f8;
            std::optional<std::uintptr_t> counter_phase_1f9;
            // Counter decision layer (diagnostics): fight-strategy resolvers that
            // return 2 (counter) / 3 (block), and the combat action resolver.
            std::optional<std::uintptr_t> counter_resolver_a; // FUN_1418038d0
            std::optional<std::uintptr_t> counter_resolver_b; // FUN_14183b970
            std::optional<std::uintptr_t> counter_can;        // FUN_1417f6fa0
            std::optional<std::uintptr_t> combat_resolve;     // FUN_141869550
            // AI aggression: the fight-action availability gate FUN_14183b970(actor,
            // action) that decides whether a fight action may start (returns 2/3 =
            // allowed). Detoured to always allow for NPC actors.
            std::optional<std::uintptr_t> ai_action_avail; // FUN_14183b970
            // Tool-object probe: FUN_141e6bea0 + 0x3a (`test rcx,rcx`) where rcx is
            // the local player's current tool object.
            std::optional<std::uintptr_t> knife_probe; // FUN_141e6bea0 + 0x3a
            // Same function, entry (rcx = &slot; *rcx = holder/entity).
            std::optional<std::uintptr_t> knife_entity; // FUN_141e6bea0
            // HUD/ammo quantity accessors: FUN_1410f7460(id, actor) -> current,
            // FUN_1410f73d0(actor, id) -> max.
            std::optional<std::uintptr_t> knife_qty;     // FUN_1410f7460
            std::optional<std::uintptr_t> knife_qty_max; // FUN_1410f73d0
        };

        // Builder that fills the display mode list. The reserve site inside it hands
        // over the vector growth helper and the allocator it is called with.
        static constexpr std::string_view k_mode_list_build_sig =
            "48 89 4C 24 08 55 56 57 41 54 48 8D 6C 24 ? 48 81 EC 88 00 00 00 48 8B F1 45 33 "
            "E4 4C 8D 45 ? 66 44 89 A1 B2 01 00 00";

        // clang-format off
        static constexpr auto scan_entries = std::to_array<ScanEntry<ResolvedAddresses>>({
            {.name="VIEWPORT_RATIO_LOAD", .field=&ResolvedAddresses::viewport_ratio_load,    .offset=0x05,  .bytes="0F 28 E8 EB ? F3 0F 10 05 ? ? ? ? F3 0F 5E C1 F3 0F 59 C4"},
            {.name="VIEWPORT_RATIO_MUL",  .field=&ResolvedAddresses::viewport_ratio_mul,     .offset=0x00,  .bytes="F3 0F 59 25 ? ? ? ? EB ? 0F 28 E5"},
            {.name="SCALING_BRANCH",      .field=&ResolvedAddresses::scaling_branch_start,   .offset=0x00,  .bytes="45 0F 2F C1 41 0F 28 F0 41 0F 28 F9 76 ? 41 0F 28 F8 F3 0F 59 3D"},
            {.name="SCALING_BRANCH",      .field=&ResolvedAddresses::scaling_branch_end,     .offset=0x52,  .bytes="45 0F 2F C1 41 0F 28 F0 41 0F 28 F9 76 ? 41 0F 28 F8 F3 0F 59 3D"},
            {.name="DISPLAY_FLAG",        .field=&ResolvedAddresses::display_flag,           .offset=0x00,  .bytes="0F 2F C8 73 ? 8B D6 F3 0F 59 15"},
            {.name="FOV_STORE",           .field=&ResolvedAddresses::fov_store,              .offset=0x05,  .bytes="89 43 40 EB 05 F3 0F 11 73 40 48 8D 54 24 40"},
            {.name="COORD_TRANSFORM",     .field=&ResolvedAddresses::coord_transform,        .offset=0x00,  .bytes="0F 28 D0 F3 0F 59 15 ? ? ? ? 0F 2F CA 77"},
            {.name="SCALING_OFFSETS",     .field=&ResolvedAddresses::scaling_offsets,        .offset=0x00,  .bytes="F3 0F 11 4C 24 30 F3 0F 59 05 ? ? ? ? F3 0F 11 44 24 34"},
            {.name="GAME_UNPAUSE",        .field=&ResolvedAddresses::game_unpause,           .offset=0x00,  .bytes="C6 81 C0 02 00 00 00 48 8B 91 90 02 00 00 48 8B D9"},
            {.name="GAME_PAUSE",          .field=&ResolvedAddresses::game_pause,             .offset=0x11,  .bytes="48 C1 E1 20 48 C1 F9 3F 48 23 08 48 39 4A 18 75 08 41 C6 80 C0 02 00 00 01"},
            {.name="GAME_PAUSE2",         .field=&ResolvedAddresses::game_pause2,            .offset=0x06,  .bytes="48 39 46 18 75 ? C6 87 C0 02 00 00 01 48 8B 74 24"},
            {.name="GET_GAME_ID",         .field=&ResolvedAddresses::get_game_id,            .offset=0x00,  .bytes="48 83 EC 28 B9 ? ? ? ? E8 ? ? ? ? 84 C0 74 ? E8 ? ? ? ? 33 C9 84 C0 0F 95 C1 8D 81 ? ? ? ?"},
            {.name="LANG_BF_WRITE",       .field=&ResolvedAddresses::lang_bf_write,          .offset=0x05,  .bytes="0F B6 44 24 ? 89 3D ? ? ? ? 89 1D ? ? ? ? 89 05"},
            {.name="LANG_SETUP",          .field=&ResolvedAddresses::lang_setup,             .offset=0x00,  .bytes="8B CB E8 ? ? ? ? E8 ? ? ? ? 8B C8 E8 ? ? ? ?"},
            {.name="GET_LANGUAGE",        .field=&ResolvedAddresses::get_language,           .offset=0x00,  .bytes="48 83 EC 28 8B 05 ? ? ? ? 83 F8 17 7C"},
            {.name="FPS_TIMING_PTR",      .field=&ResolvedAddresses::fps_timing_ptr,         .offset=0x0C,  .bytes="C3 CC CC CC CC CC CC CC CC CC CC CC 48 8B 0D ? ? ? ? E9"},
            {.name="FPS_CAP_MULSS",       .field=&ResolvedAddresses::fps_cap_mulss,          .offset=0x15,  .bytes="48 8B 05 ? ? ? ? F3 48 0F 2A C0 48 85 C0 79 04 F3 0F 58 C1 F3 0F 59 05 ? ? ? ? 33 D2 0F 2F C7"},
            {.name="GAME_STATE_GLOBAL",   .field=&ResolvedAddresses::game_state_global,      .offset=0x00,  .bytes="48 8B 05 ? ? ? ? C6 80 C8 02 00 00 00 C3"},
            {.name="LOC_INIT",            .field=&ResolvedAddresses::loc_init,               .offset=0x00,  .bytes="40 53 48 83 EC ? 48 8B D9 48 89 0D"},
            {.name="MODE_GET_BY_INDEX",   .field=&ResolvedAddresses::mode_get_by_index,      .offset=0x00,  .bytes="4C 8B 91 08 0A 00 00 6B D2 1C 66 0F EF C9 66 0F EF C0 49 8B 82 A8 01 00 00"},
            {.name="MODE_LIST_BUILD",     .field=&ResolvedAddresses::mode_list_build,        .offset=0x000, .bytes=k_mode_list_build_sig},
            {.name="MODE_LIST_RESERVE",   .field=&ResolvedAddresses::mode_list_reserve_site, .offset=0x304, .bytes=k_mode_list_build_sig},
            {.name="CAMERA_MANAGER_LOAD", .field=&ResolvedAddresses::camera_manager_load,    .offset=0x00,  .bytes="48 8B 05 ? ? ? ? 49 8B F9 49 8B F0 48 8B 58 38"},
            {.name="TRACK_WEIGHT_SITE",   .field=&ResolvedAddresses::track_weight_site,      .offset=0x05,  .bytes="E8 ? ? ? ? 48 8B 43 08 8B 08 0F 28 D0 83 E1 07"},
            {.name="CAMERA_INTERPOLATE",  .field=&ResolvedAddresses::camera_interpolate,     .offset=0x00,  .bytes="44 0F 29 84 24 ? ? ? ? 44 0F 28 C0 E8"},
            {.name="MOUSE_STATE_UPDATE",  .field=&ResolvedAddresses::mouse_state_update,     .offset=0x01E, .bytes="4C 8D 87 80 21 02 00 48 8D 97 A8 23 02 00 48 8B CF E8 ? ? ? ? 48 8B CF E8 ? ? ? ? 48 8B 5C 24 40 0F 57 F6 48 85 F6"},
            {.name="WEAPON_CLASS_GET",    .field=&ResolvedAddresses::weapon_class_get,       .offset=0x00,  .bytes="40 53 48 83 EC 20 48 8B 81 E8 01 00 00 C7 44 24 30 01 00 00 00 48 8B D9 48 8B 48 08"},
            {.name="SET_FIGHT_TYPE",      .field=&ResolvedAddresses::set_fight_type,         .offset=0x00,  .bytes="40 53 48 83 EC 20 8D 42 FF 48 8B D9 83 F8 0B 76 04 85 D2 75 43 0F B6 81 1C 02 00 00 84 C0 74 33"},
            {.name="SET_WEAPON_POSE",     .field=&ResolvedAddresses::set_weapon_pose,        .offset=0x00,  .bytes="40 53 55 48 83 EC 28 48 8B 81 E8 01 00 00 41 0F B6 E8 8B DA 48 8B 48 08"},
            {.name="APPLY_WEAPON_TYPE",   .field=&ResolvedAddresses::apply_weapon_type,      .offset=0x00,  .bytes="40 55 57 41 54 48 83 EC 40 45 8B E0 8B EA 48 8B F9 41 83 F8 02 75 09 83 FA 19"},
            // AccCoop M2: the per-frame camera task. Its prologue loads the camera
            // manager global with `mov rdi,[rip+disp32]` at +0x1A (disp32 at +0x1D).
            {.name="AI_UPDATE_CAMERA",    .field=&ResolvedAddresses::ai_update_camera,        .offset=0x00,  .bytes="48 83 EC 28 48 89 7C 24 20 E8 ? ? ? ? 48 8B 0D ? ? ? ? E8 ? ? ? ? 48 8B 3D ? ? ? ? 48 8B 47 70"},
            // AccCoop A1: FUN_140346aa0 = player object by index. Its two rip-relative
            // loads give the global player array (slot at +0x0D) and count (slot at +0x03).
            {.name="PLAYER_BY_INDEX",     .field=&ResolvedAddresses::player_by_index,          .offset=0x00,  .bytes="0F B7 05 ? ? ? ? 3B C8 73 13 48 8B 05 ? ? ? ? 8D 0C CD 00 00 00 00 48 8B 04 01 C3"},
            // ---- combat trace (functions from acrogue RE) ----
            {.name="COMBAT_PARRY",          .field=&ResolvedAddresses::combat_parry,          .offset=0x00, .bytes="48 89 5C 24 18 48 89 6C 24 20 57 41 54 41 55 48 83 EC 30 48 8B 01 4D 8B E9"},
            {.name="COMBAT_COUNTER_FAIL",   .field=&ResolvedAddresses::combat_counter_fail,   .offset=0x00, .bytes="48 89 5C 24 10 48 89 74 24 18 57 48 81 EC 70 01 00 00 0F 29 B4 24 60 01 00 00 48 8B F9"},
            {.name="COMBAT_GRAB_COUNTERED", .field=&ResolvedAddresses::combat_grab_countered, .offset=0x00, .bytes="48 8B C4 48 89 58 10 48 89 70 18 55 57 41 54 48 8D A8 F8 FE FF FF 48 81 EC 10 02 00 00"},
            {.name="COMBAT_WEAPON_SETUP",   .field=&ResolvedAddresses::combat_weapon_setup,   .offset=0x00, .bytes="48 89 5C 24 10 48 89 6C 24 18 56 57 41 54 48 83 EC 20 48 8B D9 48 81 C1 58 09 00 00"},
            {.name="COMBAT_POSE_A",         .field=&ResolvedAddresses::combat_pose_a,         .offset=0x00, .bytes="40 53 56 48 81 EC 08 01 00 00 45 33 C9 48 8B F1 48 8B 09 41 8D 51 0B 45 33 C0"},
            {.name="COMBAT_POSE_B",         .field=&ResolvedAddresses::combat_pose_b,         .offset=0x00, .bytes="48 89 5C 24 18 55 56 57 41 54 41 55 41 56 41 57 48 83 EC 60 0F 29 74 24 50"},
            {.name="COMBAT_FA1",            .field=&ResolvedAddresses::combat_fa1,            .offset=0x00, .bytes="48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 78 3B F0 FF"},
            {.name="COMBAT_FA2",            .field=&ResolvedAddresses::combat_fa2,            .offset=0x00, .bytes="48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 C6 81 A1 12 00 00 00"},
            {.name="COMBAT_FA3",            .field=&ResolvedAddresses::combat_fa3,            .offset=0x00, .bytes="48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 B8 38 F0 FF"},
            {.name="COMBAT_FA4",            .field=&ResolvedAddresses::combat_fa4,            .offset=0x00, .bytes="48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 98 37 F0 FF"},
            {.name="COMBAT_FA5",            .field=&ResolvedAddresses::combat_fa5,            .offset=0x00, .bytes="48 89 5C 24 08 57 48 81 EC D0 00 00 00 48 8B F9 48 8B 09 E8 A8 35 F0 FF"},
            {.name="COMBAT_FA6",            .field=&ResolvedAddresses::combat_fa6,            .offset=0x00, .bytes="48 8B C4 48 89 58 08 48 89 70 10 57 48 81 EC 90 00 00 00 49 8B F0 48 8B FA 48 8B D9"},
            {.name="COMBAT_FA7",            .field=&ResolvedAddresses::combat_fa7,            .offset=0x00, .bytes="4C 8B DC 49 89 5B 18 55 56 57 48 81 EC F0 00 00 00 48 8B 81 E0 01 00 00"},
            {.name="COMBAT_FA8",            .field=&ResolvedAddresses::combat_fa8,            .offset=0x00, .bytes="4C 8B DC 56 57 48 81 EC 88 00 00 00 48 8B 81 E0 01 00 00 49 89 5B 10"},
            {.name="COMBAT_FA9",            .field=&ResolvedAddresses::combat_fa9,            .offset=0x00, .bytes="48 8B C4 48 89 58 08 4C 89 48 20 4C 89 40 18 55 56 57 41 54 41 55 41 56 41 57"},
            // ---- counter window (parry classifier compare immediates at +0x1C) ----
            {.name="COUNTER_PHASE_1F6",     .field=&ResolvedAddresses::counter_phase_1f6,     .offset=0x1C, .bytes="48 8B 01 48 8D 88 30 02 00 00 48 39 88 70 0B 00 00 75 07 48 8D 88 D0 06 00 00 81 39 F6 01 00 00 0F 94 C0 C3"},
            {.name="COUNTER_PHASE_1F7",     .field=&ResolvedAddresses::counter_phase_1f7,     .offset=0x1C, .bytes="48 8B 01 48 8D 88 30 02 00 00 48 39 88 70 0B 00 00 75 07 48 8D 88 D0 06 00 00 81 39 F7 01 00 00 0F 94 C0 C3"},
            {.name="COUNTER_PHASE_1F8",     .field=&ResolvedAddresses::counter_phase_1f8,     .offset=0x1C, .bytes="48 8B 01 48 8D 88 30 02 00 00 48 39 88 70 0B 00 00 75 07 48 8D 88 D0 06 00 00 81 39 F8 01 00 00 0F 94 C0 C3"},
            {.name="COUNTER_PHASE_1F9",     .field=&ResolvedAddresses::counter_phase_1f9,     .offset=0x1C, .bytes="48 8B 01 48 8D 88 30 02 00 00 48 39 88 70 0B 00 00 75 07 48 8D 88 D0 06 00 00 81 39 F9 01 00 00 0F 94 C0 C3"},
            // ---- counter decision layer (diagnostics) ----
            {.name="COUNTER_RESOLVER_A",    .field=&ResolvedAddresses::counter_resolver_a,    .offset=0x00, .bytes="40 53 48 83 EC 20 83 7A 34 03 48 8B D9 75 1F E8 6C DF 8E 00"},
            {.name="COUNTER_RESOLVER_B",    .field=&ResolvedAddresses::counter_resolver_b,    .offset=0x00, .bytes="48 89 5C 24 10 48 89 6C 24 18 56 57 41 55 48 83 EC 20 48 8B 01 48 8B F2 48 8B F9 4C"},
            {.name="COUNTER_CAN",           .field=&ResolvedAddresses::counter_can,           .offset=0x00, .bytes="40 53 48 83 EC 20 48 8B D9 E8 A2 A8 8F 00 48 05 20 11 00 00 80 78 18 00 74 40 48 8B"},
            {.name="COMBAT_RESOLVE",        .field=&ResolvedAddresses::combat_resolve,        .offset=0x00, .bytes="4C 8B DC 48 81 EC 88 00 00 00 48 8B 01 49 89 5B 10 49 89 6B F8 4C 8B 90 E8 01 00 00"},
            // ---- AI aggression: fight-action availability gate ----
            // FUN_14183b970(actor, action) -> 2/3 = the action may start.
            {.name="AI_ACTION_AVAIL",       .field=&ResolvedAddresses::ai_action_avail,       .offset=0x00, .bytes="48 89 5C 24 10 48 89 6C 24 18 56 57 41 55 48 83 EC 20 48 8B 01 48 8B F2 48 8B F9 4C 8B 80 E8 01 00 00 49 8B 68 08"},
            // ---- throwing-knife tool-object probe (diagnostic) ----
            {.name="KNIFE_PROBE",           .field=&ResolvedAddresses::knife_probe,           .offset=0x3A, .bytes="40 57 48 83 EC 20 48 8B 09 48 8B FA 48 85 C9 74 3D 48 8B 49 40 48 89 5C 24 30 48 8B 1D 17 A8 51 01 48 8B 01 FF 50 60 0F B6 4B 65 48 8B 5C 24 30"},
            {.name="KNIFE_ENTITY",          .field=&ResolvedAddresses::knife_entity,          .offset=0x00, .bytes="40 57 48 83 EC 20 48 8B 09 48 8B FA 48 85 C9 74 3D 48 8B 49 40 48 89 5C 24 30 48 8B 1D 17 A8 51 01 48 8B 01 FF 50 60 0F B6 4B 65 48 8B 5C 24 30"},
            // ---- throwing-knife quantity accessors ----
            {.name="KNIFE_QTY",             .field=&ResolvedAddresses::knife_qty,             .offset=0x00, .bytes="40 53 48 83 EC 20 8B D9 48 8B CA E8 20 11 FE FE 48 85 C0 74 71 48 8B C8 E8 13 CB 00 FF 48 8B C8 48 85 C0 74 61 48 8B 00 33 D2 FF"},
            {.name="KNIFE_QTY_MAX",         .field=&ResolvedAddresses::knife_qty_max,         .offset=0x00, .bytes="40 53 48 83 EC 20 8B DA E8 B3 11 FE FE 48 85 C0 74 71 48 8B C8 E8 A6 CB 00 FF 48 8B C8 48 85 C0 74 61 48 8B 00 33 D2 FF"}
        });
        // clang-format on
    };

    static_assert(ValidGameData<ac::Rogue>);
} // namespace games

