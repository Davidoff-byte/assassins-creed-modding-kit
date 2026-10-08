// P2: partner marker overlay (D3D11 / DXGI Present hook).
// Renders a small diamond marker above the driven ghost body (the "partner"), and optionally
// a calibration marker above the local player. Projection is done from the camera pose we
// already read each frame plus a configurable vertical FOV.
#pragma once

namespace games::ac::blackflag::coop::overlay {
    // One-time: installs the Present hook via a hidden dummy swapchain. Safe to call at install.
    void init();

    void set_enabled(bool on);
    // fov_y_deg: vertical FOV for the projection (tune live); size_px: marker half-size in pixels;
    // draw_player: also draw the calibration marker over the LOCAL player.
    void set_params(float fov_y_deg, float size_px, bool draw_player);

    // Game thread, each frame: stash the data the render-thread hook needs.
    void update(const float cam_pos[3], const float cam_quat[4],
                const float ghost_pos[3], bool ghost_valid,
                const float player_pos[3]);
} // namespace games::ac::blackflag::coop::overlay
