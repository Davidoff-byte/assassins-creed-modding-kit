// P2 partner-marker overlay for AC4 Black Flag (32-bit, D3D11).
//
// Hook strategy: create a hidden dummy device+swapchain to obtain the real
// IDXGISwapChain::Present function address, then install a SafetyHook mid-hook on that
// FUNCTION (not the vtable slot). The callback runs before the original Present body and
// execution continues into it - no vtable calls, no re-entrancy.
//
// Rendering: two screen-space diamond quads (partner = cyan over the ghost body, calibration
// = yellow over the local player), projected with our own math from the camera pose +
// configurable vertical FOV. d3d11 / d3dcompiler are loaded dynamically; shaders compile at
// first present.
#include "games/ac/blackflag/coop/overlay.hpp"

#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>

#include <Windows.h>
#include <d3d11.h>
#include <dxgi.h>

#include "core/logger.hpp" // IWYU pragma: keep

#include "core/mem/hook.hpp"
#include "core/mem/write.hpp"

namespace games::ac::blackflag::coop::overlay {
    namespace {
        constexpr int kVtblPresent = 8; // IDXGISwapChain::Present

        using CreateFn  = HRESULT(WINAPI *)(IDXGIAdapter *, D3D_DRIVER_TYPE, HMODULE, UINT,
                                            const D3D_FEATURE_LEVEL *, UINT, UINT,
                                            const DXGI_SWAP_CHAIN_DESC *, IDXGISwapChain **,
                                            ID3D11Device **, D3D_FEATURE_LEVEL *,
                                            ID3D11DeviceContext **);
        using CompileFn = HRESULT(WINAPI *)(LPCVOID, SIZE_T, LPCSTR, const D3D_SHADER_MACRO *,
                                            ID3DInclude *, LPCSTR, LPCSTR, UINT, UINT,
                                            ID3DBlob **, ID3DBlob **);

        std::atomic<bool>  g_enabled {false};
        std::atomic<float> g_fov {55.0F};
        std::atomic<float> g_size {16.0F};
        std::atomic<bool>  g_draw_player {true};

        struct FrameData {
            float cam_pos[3] {};
            float cam_quat[4] {0.0F, 0.0F, 0.0F, 1.0F};
            float ghost_pos[3] {};
            float player_pos[3] {};
            float fwd_sign = 1.0F; // +-1, auto-corrected in update()
            bool  ghost_valid = false;
        };
        FrameData g_frame; // game thread writes, render thread reads (benign torn read at worst)

        IDXGISwapChain     *g_swap = nullptr;
        ID3D11Device       *g_dev  = nullptr;
        ID3D11DeviceContext *g_ctx = nullptr;
        mem::MidHook        g_present_hook;

        ID3D11RenderTargetView *g_rtv = nullptr;
        void                   *g_bb_cache = nullptr;
        UINT                    g_bb_w = 0;
        UINT                    g_bb_h = 0;

        ID3D11VertexShader *g_vs = nullptr;
        ID3D11PixelShader  *g_ps = nullptr;
        ID3D11InputLayout  *g_layout = nullptr;
        ID3D11Buffer       *g_vb = nullptr;
        ID3D11BlendState   *g_blend = nullptr;
        ID3D11DepthStencilState *g_dss = nullptr;

        bool g_res_ready  = false;
        bool g_res_failed = false;
        bool g_logged_first_draw = false;

        struct Vertex {
            float x;
            float y;
            float r;
            float g;
            float b;
            float a;
        };

        auto rot_axis(const float q[4], const float v[3], float out[3]) -> void {
            // out = q * v * q^-1 (v treated as a pure quaternion)
            const float qx = q[0];
            const float qy = q[1];
            const float qz = q[2];
            const float qw = q[3];
            const float ix = qw * v[0] + qy * v[2] - qz * v[1];
            const float iy = qw * v[1] + qz * v[0] - qx * v[2];
            const float iz = qw * v[2] + qx * v[1] - qy * v[0];
            const float iw = -qx * v[0] - qy * v[1] - qz * v[2];
            out[0] = ix * qw + iw * -qx + iy * -qz - iz * -qy;
            out[1] = iy * qw + iw * -qy + iz * -qx - ix * -qz;
            out[2] = iz * qw + iw * -qz + ix * -qy - iy * -qx;
        }

        auto project(const float p[3], const FrameData &f, float w, float h, float &sx, float &sy)
            -> bool {
            const float ax_r[3] = {1.0F, 0.0F, 0.0F};
            const float ax_u[3] = {0.0F, 1.0F, 0.0F};
            const float ax_f[3] = {0.0F, 0.0F, 1.0F};
            float right[3];
            float up[3];
            float fwd[3];
            rot_axis(f.cam_quat, ax_r, right);
            rot_axis(f.cam_quat, ax_u, up);
            rot_axis(f.cam_quat, ax_f, fwd);
            fwd[0] *= f.fwd_sign;
            fwd[1] *= f.fwd_sign;
            fwd[2] *= f.fwd_sign;

            const float d[3] = {p[0] - f.cam_pos[0], p[1] - f.cam_pos[1], p[2] - f.cam_pos[2]};
            const float depth = d[0] * fwd[0] + d[1] * fwd[1] + d[2] * fwd[2];
            if (depth <= 0.25F) {
                return false;
            }
            const float cx = d[0] * right[0] + d[1] * right[1] + d[2] * right[2];
            const float cy = d[0] * up[0] + d[1] * up[1] + d[2] * up[2];
            const float tan_half = std::tan(g_fov.load(std::memory_order_relaxed) * 0.5F *
                                            (3.14159265F / 180.0F));
            if (tan_half <= 0.01F) {
                return false;
            }
            const float aspect = w / h;
            const float nx = (cx / depth) / (tan_half * aspect);
            const float ny = (cy / depth) / tan_half;
            sx = (nx + 1.0F) * 0.5F * w;
            sy = (1.0F - ny) * 0.5F * h;
            return true;
        }

        auto make_resources() -> void {
            if (g_res_ready || g_res_failed) {
                return;
            }
            HMODULE comp = LoadLibraryA("d3dcompiler_47.dll");
            if (comp == nullptr) {
                comp = LoadLibraryA("d3dcompiler_43.dll");
            }
            const auto compile = comp != nullptr
                                     ? reinterpret_cast<CompileFn>(
                                           GetProcAddress(comp, "D3DCompile"))
                                     : nullptr;
            if (compile == nullptr || g_dev == nullptr) {
                log::get()->error("Overlay: no d3dcompiler available");
                g_res_failed = true;
                return;
            }

            const char *src =
                "struct VSIn { float2 pos : POSITION; float4 col : COLOR; };\n"
                "struct VSOut { float4 pos : SV_Position; float4 col : COLOR; };\n"
                "VSOut vs_main(VSIn i) { VSOut o; o.pos = float4(i.pos, 0, 1); o.col = i.col; "
                "return o; }\n"
                "float4 ps_main(VSOut i) : SV_Target { return i.col; }\n";

            ID3DBlob *vs_blob = nullptr;
            ID3DBlob *ps_blob = nullptr;
            if (FAILED(compile(src, std::strlen(src), nullptr, nullptr, nullptr, "vs_main", "vs_4_0",
                               0, 0, &vs_blob, nullptr))) {
                log::get()->error("Overlay: vs compile failed");
                g_res_failed = true;
                return;
            }
            if (FAILED(compile(src, std::strlen(src), nullptr, nullptr, nullptr, "ps_main", "ps_4_0",
                               0, 0, &ps_blob, nullptr))) {
                log::get()->error("Overlay: ps compile failed");
                vs_blob->Release();
                g_res_failed = true;
                return;
            }

            const bool ok =
                SUCCEEDED(g_dev->CreateVertexShader(vs_blob->GetBufferPointer(),
                                                    vs_blob->GetBufferSize(), nullptr, &g_vs)) &&
                SUCCEEDED(g_dev->CreatePixelShader(ps_blob->GetBufferPointer(),
                                                   ps_blob->GetBufferSize(), nullptr, &g_ps));
            if (ok) {
                const D3D11_INPUT_ELEMENT_DESC elems[] = {
                    {"POSITION", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA,
                     0},
                    {"COLOR", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 8,
                     D3D11_INPUT_PER_VERTEX_DATA, 0},
                };
                g_dev->CreateInputLayout(elems, 2, vs_blob->GetBufferPointer(),
                                         vs_blob->GetBufferSize(), &g_layout);
            }
            vs_blob->Release();
            ps_blob->Release();
            if (!ok || g_layout == nullptr) {
                log::get()->error("Overlay: shader create failed");
                g_res_failed = true;
                return;
            }

            D3D11_BUFFER_DESC bd {};
            bd.ByteWidth = sizeof(Vertex) * 6;
            bd.Usage = D3D11_USAGE_DYNAMIC;
            bd.BindFlags = D3D11_BIND_VERTEX_BUFFER;
            bd.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
            if (FAILED(g_dev->CreateBuffer(&bd, nullptr, &g_vb))) {
                log::get()->error("Overlay: vb failed");
                g_res_failed = true;
                return;
            }

            D3D11_BLEND_DESC bld {};
            bld.RenderTarget[0].BlendEnable = TRUE;
            bld.RenderTarget[0].SrcBlend = D3D11_BLEND_SRC_ALPHA;
            bld.RenderTarget[0].DestBlend = D3D11_BLEND_INV_SRC_ALPHA;
            bld.RenderTarget[0].BlendOp = D3D11_BLEND_OP_ADD;
            bld.RenderTarget[0].SrcBlendAlpha = D3D11_BLEND_ONE;
            bld.RenderTarget[0].DestBlendAlpha = D3D11_BLEND_INV_SRC_ALPHA;
            bld.RenderTarget[0].BlendOpAlpha = D3D11_BLEND_OP_ADD;
            bld.RenderTarget[0].RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_ALL;
            g_dev->CreateBlendState(&bld, &g_blend);

            D3D11_DEPTH_STENCIL_DESC dsd {};
            dsd.DepthEnable = FALSE;
            dsd.StencilEnable = FALSE;
            g_dev->CreateDepthStencilState(&dsd, &g_dss);

            g_res_ready = true;
            log::get()->info("Overlay: resources ready");
        }

        auto draw_diamond(float sx, float sy, float half, const float rgba[4]) -> void {
            if (g_vb == nullptr || g_ctx == nullptr || g_bb_w == 0 || g_bb_h == 0) {
                return;
            }
            const auto ndc_x = [&](float px) -> float {
                return (px / static_cast<float>(g_bb_w)) * 2.0F - 1.0F;
            };
            const auto ndc_y = [&](float py) -> float {
                return 1.0F - (py / static_cast<float>(g_bb_h)) * 2.0F;
            };
            const float pts[4][2] = {
                {sx, sy - half}, {sx + half, sy}, {sx, sy + half}, {sx - half, sy}};
            const int order[6] = {0, 1, 2, 0, 2, 3};
            D3D11_MAPPED_SUBRESOURCE ms {};
            if (FAILED(g_ctx->Map(g_vb, 0, D3D11_MAP_WRITE_DISCARD, 0, &ms))) {
                return;
            }
            auto *v = static_cast<Vertex *>(ms.pData);
            for (int i = 0; i < 6; ++i) {
                const auto &pt = pts[order[i]];
                v[i] = Vertex {ndc_x(pt[0]), ndc_y(pt[1]), rgba[0], rgba[1], rgba[2], rgba[3]};
            }
            g_ctx->Unmap(g_vb, 0);
            const UINT stride = sizeof(Vertex);
            const UINT offset = 0;
            g_ctx->IASetVertexBuffers(0, 1, &g_vb, &stride, &offset);
            g_ctx->Draw(6, 0);
        }

        auto draw_overlay(IDXGISwapChain *sc) -> void {
            if (g_res_failed || g_ctx == nullptr || g_dev == nullptr) {
                return;
            }
            if (!g_res_ready) {
                make_resources();
                if (!g_res_ready) {
                    return;
                }
            }
            ID3D11Texture2D *bb = nullptr;
            if (FAILED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), reinterpret_cast<void **>(&bb))) ||
                bb == nullptr) {
                return;
            }
            D3D11_TEXTURE2D_DESC desc {};
            bb->GetDesc(&desc);
            g_bb_w = desc.Width;
            g_bb_h = desc.Height;
            if (static_cast<void *>(bb) != g_bb_cache) {
                if (g_rtv != nullptr) {
                    g_rtv->Release();
                    g_rtv = nullptr;
                }
                g_dev->CreateRenderTargetView(bb, nullptr, &g_rtv);
                g_bb_cache = static_cast<void *>(bb);
            }
            bb->Release();
            if (g_rtv == nullptr) {
                return;
            }

            ID3D11RenderTargetView *old_rtv = nullptr;
            ID3D11DepthStencilView *old_dsv = nullptr;
            g_ctx->OMGetRenderTargets(1, &old_rtv, &old_dsv);
            UINT nvp = 1;
            D3D11_VIEWPORT old_vp {};
            g_ctx->RSGetViewports(&nvp, &old_vp);

            g_ctx->OMSetRenderTargets(1, &g_rtv, nullptr);
            const D3D11_VIEWPORT vp {0.0F, 0.0F, static_cast<float>(g_bb_w),
                                     static_cast<float>(g_bb_h), 0.0F, 1.0F};
            g_ctx->RSSetViewports(1, &vp);
            const float bf[4] = {0.0F, 0.0F, 0.0F, 0.0F};
            if (g_blend != nullptr) {
                g_ctx->OMSetBlendState(g_blend, bf, 0xffffffffU);
            }
            if (g_dss != nullptr) {
                g_ctx->OMSetDepthStencilState(g_dss, 0);
            }
            g_ctx->IASetInputLayout(g_layout);
            g_ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            g_ctx->VSSetShader(g_vs, nullptr, 0);
            g_ctx->PSSetShader(g_ps, nullptr, 0);

            const FrameData f = g_frame; // snapshot
            const float size  = g_size.load(std::memory_order_relaxed);
            const float w     = static_cast<float>(g_bb_w);
            const float h     = static_cast<float>(g_bb_h);
            const float cyan[4]   = {0.20F, 0.85F, 1.00F, 0.85F};
            const float yellow[4] = {1.00F, 0.85F, 0.20F, 0.80F};
            float sx = 0.0F;
            float sy = 0.0F;
            if (f.ghost_valid && project(f.ghost_pos, f, w, h, sx, sy)) {
                draw_diamond(sx, sy - size * 1.6F, size, cyan);
                draw_diamond(sx, sy - size * 1.6F, size * 0.55F, yellow);
            }
            if (g_draw_player.load(std::memory_order_relaxed) &&
                project(f.player_pos, f, w, h, sx, sy)) {
                draw_diamond(sx, sy - size * 1.2F, size * 0.8F, yellow);
            }

            g_ctx->OMSetRenderTargets(1, &old_rtv, old_dsv);
            if (old_rtv != nullptr) {
                old_rtv->Release();
            }
            if (old_dsv != nullptr) {
                old_dsv->Release();
            }
            if (nvp > 0) {
                g_ctx->RSSetViewports(nvp, &old_vp);
            }
        }

        // SafetyHook mid-hook: runs at Present's entry (stdcall: args on the stack,
        // this = [esp+4]), then the original Present body continues.
        struct PresentCallback {
            static void operator()(mem::Registers &r) {
                const auto sc = reinterpret_cast<IDXGISwapChain *>(
                    mem::read<std::uintptr_t>(r.esp + 4));
                if (sc == nullptr) {
                    return;
                }
                if (g_swap == nullptr) {
                    g_swap = sc;
                    if (SUCCEEDED(sc->GetDevice(__uuidof(ID3D11Device),
                                                reinterpret_cast<void **>(&g_dev))) &&
                        g_dev != nullptr) {
                        g_dev->GetImmediateContext(&g_ctx);
                    }
                    log::get()->info("Overlay: Present hit (swapchain 0x{:X} dev=0x{:X})",
                                     reinterpret_cast<std::uintptr_t>(sc),
                                     reinterpret_cast<std::uintptr_t>(g_dev));
                }
                if (sc == g_swap && g_enabled.load(std::memory_order_relaxed)) {
                    draw_overlay(sc);
                    if (!g_logged_first_draw) {
                        g_logged_first_draw = true;
                        log::get()->info("Overlay: first draw");
                    }
                }
            }
        };
    } // namespace

    void init() {
        static bool once = false;
        if (once) {
            return;
        }
        once = true;

        HMODULE d3d11 = LoadLibraryA("d3d11.dll");
        const auto create =
            d3d11 != nullptr
                ? reinterpret_cast<CreateFn>(GetProcAddress(d3d11, "D3D11CreateDeviceAndSwapChain"))
                : nullptr;
        if (create == nullptr) {
            log::get()->error("Overlay: d3d11 unavailable");
            return;
        }

        WNDCLASSEXA wc {};
        wc.cbSize = sizeof(wc);
        wc.lpfnWndProc = DefWindowProcA;
        wc.lpszClassName = "ACBFMarkerOverlayWnd";
        RegisterClassExA(&wc);
        HWND hwnd = CreateWindowExA(0, wc.lpszClassName, "", WS_OVERLAPPED, 0, 0, 2, 2, nullptr,
                                    nullptr, nullptr, nullptr);
        if (hwnd == nullptr) {
            log::get()->error("Overlay: dummy window failed");
            return;
        }

        DXGI_SWAP_CHAIN_DESC sd {};
        sd.BufferCount = 1;
        sd.BufferDesc.Width = 2;
        sd.BufferDesc.Height = 2;
        sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
        sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
        sd.OutputWindow = hwnd;
        sd.SampleDesc.Count = 1;
        sd.Windowed = TRUE;
        sd.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;

        IDXGISwapChain *sc = nullptr;
        ID3D11Device *dev = nullptr;
        ID3D11DeviceContext *ctx = nullptr;
        const HRESULT hr = create(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0,
                                  D3D11_SDK_VERSION, &sd, &sc, &dev, nullptr, &ctx);
        if (FAILED(hr) || sc == nullptr) {
            log::get()->error("Overlay: dummy swapchain failed (0x{:X})", static_cast<unsigned>(hr));
            DestroyWindow(hwnd);
            return;
        }

        void **vtbl = *reinterpret_cast<void ***>(sc);
        const auto present_addr = reinterpret_cast<std::uintptr_t>(vtbl[kVtblPresent]);
        auto hook = mem::make_hook<PresentCallback>(present_addr);
        if (!hook) {
            log::get()->error("Overlay: Present hook failed: {}", hook.error());
        } else {
            g_present_hook = std::move(*hook);
            log::get()->info("Overlay: Present hook installed at 0x{:X}", present_addr);
        }

        sc->Release();
        dev->Release();
        ctx->Release();
        DestroyWindow(hwnd);
    }

    void set_enabled(bool on) {
        const bool prev = g_enabled.exchange(on, std::memory_order_relaxed);
        if (prev != on) {
            log::get()->info("Overlay: marker {}", on ? "enabled" : "disabled");
        }
    }

    void set_params(float fov_y_deg, float size_px, bool draw_player) {
        if (fov_y_deg > 20.0F && fov_y_deg < 120.0F) {
            g_fov.store(fov_y_deg, std::memory_order_relaxed);
        }
        if (size_px > 2.0F && size_px < 128.0F) {
            g_size.store(size_px, std::memory_order_relaxed);
        }
        g_draw_player.store(draw_player, std::memory_order_relaxed);
    }

    void update(const float cam_pos[3], const float cam_quat[4], const float ghost_pos[3],
                bool ghost_valid, const float player_pos[3]) {
        std::memcpy(g_frame.cam_pos, cam_pos, sizeof(g_frame.cam_pos));
        std::memcpy(g_frame.cam_quat, cam_quat, sizeof(g_frame.cam_quat));
        std::memcpy(g_frame.ghost_pos, ghost_pos, sizeof(g_frame.ghost_pos));
        std::memcpy(g_frame.player_pos, player_pos, sizeof(g_frame.player_pos));
        g_frame.ghost_valid = ghost_valid;

        // Auto-correct the forward sign: the camera should be looking at the player.
        const float ax_f[3] = {0.0F, 0.0F, 1.0F};
        float fwd[3];
        rot_axis(cam_quat, ax_f, fwd);
        const float dx = player_pos[0] - cam_pos[0];
        const float dy = player_pos[1] - cam_pos[1];
        const float dz = player_pos[2] - cam_pos[2];
        if (fwd[0] * dx + fwd[1] * dy + fwd[2] * dz < 0.0F) {
            g_frame.fwd_sign = -1.0F;
        } else {
            g_frame.fwd_sign = 1.0F;
        }
    }
} // namespace games::ac::blackflag::coop::overlay
