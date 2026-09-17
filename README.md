<div align="center">

<img src="assets/swirui-icon.svg" width="136" alt="SwirUI icon">

# ⚡ SwirUI

### Next-generation Python UI framework for native, reactive and GPU-first desktop applications.

**Beautiful by default. Native at the core. Built for the future.**

[![CI](https://github.com/Swir/Swirui/actions/workflows/ci.yml/badge.svg)](https://github.com/Swir/Swirui/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)
![Windows Native](https://img.shields.io/badge/Windows-Win32%20native-0078D4?logo=windows11&logoColor=white)
![Linux Native](https://img.shields.io/badge/Linux-X11%20native-FCC624?logo=linux&logoColor=black)
![macOS Native](https://img.shields.io/badge/macOS-Cocoa%20native-000000?logo=apple&logoColor=white)
![GPU](https://img.shields.io/badge/GPU-wgpu%2030-6E56CF)
![Status](https://img.shields.io/badge/status-pre--alpha-7C3AED)
![Progress](https://img.shields.io/badge/project%20progress-38%25-00BFFF)

</div>

---

## Project progress

**38% — 0.3 Alpha Visual Engine underway; native GPU color filters are now verified**

`[████████░░░░░░░░░░░░] 38%`

**Completed:** `0.1 Alpha — Foundation` ✅ · `0.2 Alpha — Native Window + First Renderer` ✅  
**Current milestone:** `0.3 Alpha — Visual Engine` 🚧

Progress only increases for implemented and verified roadmap work. Ideas, mockups, documentation-only changes and unfinished experiments do not count.

## What is SwirUI?

SwirUI is being built as a complete Python application framework rather than a visual skin over Tkinter, Qt or another widget toolkit. Python remains the public developer API while Rust, wgpu and PyO3 own performance-critical native rendering work.

The long-term goal is a framework that combines a simple Python developer experience with native windows, GPU rendering, responsive layouts, rich effects, animation, professional widgets, accessibility, visual tooling, packaging and AI-assisted development.

SwirUI is currently **pre-alpha**. APIs may change while the renderer, component system and Visual Engine are being developed.

## What already works

### Runtime and native windows

- application and window lifecycle
- component tree with cycle protection and reparenting
- direct/capture/target/bubble event routing
- thread-safe reactive `State`
- invalidation-driven `FrameScheduler`
- runtime target-FPS retargeting and frame-time telemetry
- display-aware frame pacing capped to the active monitor refresh rate
- automatic scheduler retargeting across display changes
- direct Win32 backend via Python `ctypes`
- direct Linux/X11 backend via Python `ctypes` + system libX11
- direct macOS Cocoa/AppKit backend via Python `ctypes` + Objective-C runtime
- logical-DIP public geometry with native physical-pixel conversion
- exact Win32 client-area sizing and DPI-aware minimum-track sizing
- Win32 per-monitor DPI, multi-monitor mapping and display-refresh discovery
- Retina-safe Cocoa logical geometry
- normalized pointer, keyboard, text-input, focus, resize and close events
- keyboard focus routing, Tab / Shift+Tab traversal and preventable default actions
- backend-neutral accessibility roles and semantic-tree snapshots

### Retained renderer

- retained `RenderTree` and renderer-ready `SceneGraph`
- `Path2D` convex/concave polygon tessellation and path-aware hit testing
- hierarchical clipping and cumulative opacity composition
- persistent per-window Rust/wgpu context on Windows
- GPU surface/swapchain, adapter/device/queue creation and present-mode reconfiguration
- instanced anti-aliased rounded rectangles with per-corner radii
- shaped Unicode text through glyphon/cosmic-text with persistent glyph resources
- persistent content-addressed RGBA image cache with logical aliases and telemetry
- clipped rounded rectangles, filled paths, text and images in one GPU scene
- native VSync / AutoNoVSync presentation policy and maximum-frame-latency control
- persistent offscreen scene target and separable Gaussian scene blur
- painter-order rounded backdrop blur that keeps later foreground content sharp

### 0.3 Visual Engine

- immutable multi-stop linear and radial gradients
- rectangular mesh gradients with deterministic retained tessellation
- `PerspectivePlane` depth projection
- bounded pointer-driven `Parallax`
- quality-aware retained `Reflection`
- retained `DropShadow`, `Glow`, `DynamicShadow` and source-driven `Bloom`
- `AdaptiveLighting` with directional shadow/highlight lobes
- deterministic quality-aware `Noise` / grain
- retained `FrostedGlass` and `Acrylic` materials over native backdrop blur
- deterministic acrylic micro-grain
- **immutable composable `ColorFilter` affine RGBA transforms**
- **persistent native Rust/wgpu color-filter postprocess after scene/backdrop blur**
- presets/composition for brightness, contrast, saturation, grayscale, sepia, invert, opacity and hue rotation
- visual-quality budgets spanning Performance / Balanced / Quality / Ultra / Cinematic for implemented retained effects

The Windows renderer currently owns the verified wgpu presentation path. Linux/X11 and macOS/Cocoa provide real native window/input backends; GPU presentation on those platforms and Wayland remain future work and are not claimed yet.

## Native and GPU demos

Install SwirUI in development mode:

```powershell
git clone https://github.com/Swir/Swirui.git
cd Swirui
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Native Win32 lifecycle/input demo:

```powershell
python examples/native_window_demo.py
```

For Rust/wgpu demos, install the native core in the same environment:

```powershell
python -m pip install maturin==1.15.0
cd native
maturin develop --release
cd ..
python examples/gpu_rectangles_demo.py
python examples/gpu_text_demo.py
python examples/gpu_image_demo.py
python examples/gpu_paths_demo.py
python examples/gpu_gradients_demo.py
python examples/gpu_radial_gradients_demo.py
python examples/gpu_mesh_gradients_demo.py
python examples/gpu_depth_demo.py
python examples/gpu_reflections_demo.py
python examples/gpu_shadows_demo.py
python examples/gpu_dynamic_effects_demo.py
python examples/gpu_bloom_demo.py
python examples/gpu_noise_demo.py
python examples/gpu_adaptive_lighting_demo.py
python examples/gpu_scene_blur_demo.py
python examples/gpu_backdrop_blur_demo.py
python examples/gpu_glass_materials_demo.py
python examples/gpu_color_filters_demo.py
python examples/high_refresh_demo.py
```

The demos exercise the same retained scene contracts used by applications. Geometry remains authored in logical DIPs while native surfaces and GPU submission operate in physical pixels. The color-filter demo exercises the persistent affine RGBA postprocess after scene/backdrop composition without recreating the per-window wgpu context.

## Foundation API

```python
from swirui import App, AppConfig, Component, State, Window

counter = State(0)

app = App(
    name="SwirUI Demo",
    config=AppConfig(target_fps=120),
)
window = Window(
    title="Future starts here",
    width=1100,
    height=720,
)

root = Component("dashboard")
window.set_root(root)
app.add_window(window)

counter.subscribe(lambda value: print("Counter:", value))
counter.set(1)

app.run()
```

When the native GPU extension is installed on Windows, `App()` selects the wgpu renderer automatically. Explicit renderer injection remains available for tests and custom backends.

## Architecture

```text
Python Application API
        │
        ├── App / Window lifecycle
        ├── Components / Routed Events ✅
        ├── Accessibility semantics ✅
        ├── Reactive State
        └── Runtime configuration
        │
SwirUI Runtime
        │
        ├── Native Platform Backends
        │     ├── Win32 ✅
        │     ├── Linux X11 ✅ window/input
        │     └── macOS Cocoa ✅ window/input/Retina
        ├── logical DIP ↔ physical pixel boundary ✅
        ├── per-window display / scale / refresh tracking ✅
        ├── Render Tree / Scene Graph ✅
        ├── Path2D tessellation ✅
        ├── retained depth / parallax / reflection geometry ✅
        ├── z/clip/path-aware hit testing ✅
        ├── SceneNode → Component mapping ✅
        └── display-aware frame scheduling ✅
        │
Renderer Layer
        │
        ├── persistent wgpu surface/context ✅ Windows
        ├── VSync / present-mode policy ✅ Windows
        ├── rounded rectangles / paths / shaped text / images ✅
        ├── gradients / depth / reflections ✅
        ├── shadows / glow / source bloom / lighting / grain ✅
        ├── offscreen target + separable scene blur ✅ Windows
        ├── painter-order backdrop blur ✅ Windows
        ├── frosted glass + acrylic ✅ Windows
        ├── affine RGBA color-filter postprocess ✅ Windows
        └── custom shader effects / full effect caching 🚧
        │
Native Core
        │
        └── Rust 2024 + wgpu 30 + PyO3 ✅
        │
GPU / Operating System
```

## Design goals

- **Future-grade visuals** — glass, blur, glow, mesh gradients, depth, lighting and shaders.
- **GPU-first rendering** — designed for modern displays and high refresh rates.
- **Simple Python API** — powerful UI without excessive boilerplate.
- **Reactive by default** — state changes should update only what needs to change.
- **Native desktop integration** — real operating-system windows and input pipelines.
- **Responsive layouts** — compact windows through 4K and ultrawide displays.
- **Professional widgets** — DataGrid, docking, charts, media, editor, terminal and 3D viewport.
- **Developer tooling** — hot reload, inspector, profiler, testing and packaging.
- **Accessibility and i18n** — first-class architecture rather than late add-ons.
- **Measured performance** — reproducible benchmarks instead of unsupported claims.

## Planned ecosystem

```text
SwirUI Framework
├── SwirUI Renderer
├── SwirUI Visual Engine
├── SwirUI Components
├── SwirUI Studio
├── SwirUI CLI
├── SwirUI Inspector
├── SwirUI AI Builder
├── SwirUI Package Builder
└── SwirUI Marketplace
```

## Current milestone: 0.3 Alpha — Visual Engine

The 0.2 Alpha native/runtime gate is verified complete. 0.3 is active and now includes verified gradients, depth/perspective, parallax, reflections, dynamic shadows, adaptive lighting, glow, source-driven bloom, deterministic grain, background blur, frosted glass, acrylic-like materials and native GPU color filters.

The native color-filter path uses one composable affine RGBA transform over the final retained scene, runs after scene/backdrop blur, and reuses persistent per-window postprocess resources. It has Python API tests, renderer lifecycle coverage and a real Win32/wgpu smoke gate.

The next high-impact work is safe effect caching for unchanged retained/material/backdrop work across high-refresh frames, followed by reusable custom-shader effects. Adaptive quality must become framework-wide and automatic before its roadmap item is considered complete. Native accessibility adapters, Wayland/Linux expansion, macOS GPU presentation and continued measured performance work remain important cross-cutting follow-ups without reopening the completed 0.2 gate.

See **[ROADMAP.md](ROADMAP.md)** for the full development plan.

## Quality policy

Every significant runtime change is expected to pass:

```text
Ruff
Mypy strict mode
pytest + coverage
Python 3.11
Python 3.12
Python 3.13
Python 3.14
retained-runtime performance budgets + JSON report artifact
accessibility semantic-tree tests
cargo check
cargo test
Maturin / PyO3 native build
Linux real-X11 native-window smoke test under Xvfb
macOS real-Cocoa native-window + Retina logical-geometry smoke test
Windows native smoke test
Windows integrated 0.2 mixed-scene + exact-client + routed-input gate
Windows active-display / refresh-rate mapping smoke test
Windows WM_DISPLAYCHANGE / WM_DPICHANGED normalization smoke tests
Windows keyboard / system-key normalization smoke test
Windows wgpu clear/present smoke test
Windows persistent rounded-rectangle GPU draw smoke test
Windows filled Path2D smoke test
Windows retained gradient smoke tests
Windows retained depth / parallax / reflection smoke test
Windows retained adaptive-lighting / glow / bloom / noise smoke test
Windows retained backdrop blur + glass/acrylic smoke test
Windows native GPU color-filter postprocess smoke test
Windows shaped-text smoke test
Windows image-resource smoke test
Windows clipped mixed-scene smoke test
Windows mixed-DPI smoke test
Windows presentation-policy reconfiguration smoke test
Display-aware high-refresh pacing tests
Routed keyboard focus / text-input / preventable Tab traversal tests
```

SwirUI will not claim to outperform another framework without reproducible measurements. Current CI guardrails cover retained 1024-node SceneGraph traversal, pointer hit testing and deterministic reflection tessellation. Planned expansion includes startup time, RAM, CPU/GPU usage, frame time, input latency, component creation, large lists and animation performance.

## Repository layout

```text
Swirui/
├── .github/workflows/      # Python, Rust and native platform/GPU CI
├── assets/                 # SwirUI visual assets and icon
├── benchmarks/             # reproducible performance budgets and scenarios
├── docs/                   # architecture and design documentation
├── examples/               # native and GPU examples
├── native/                 # Rust + wgpu + PyO3 GPU core
├── src/swirui/             # framework source
├── tests/                  # automated tests
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
└── pyproject.toml
```

---

<div align="center">

### ⚡ SwirUI

**Designed and developed by [Swir](https://github.com/Swir)**

</div>
