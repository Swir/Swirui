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
![Progress](https://img.shields.io/badge/project%20progress-37%25-00BFFF)

</div>

---

## Project progress

**37% — 0.3 Alpha Visual Engine underway; retained depth, parallax and reflections are verified**

`[███████░░░░░░░░░░░░░] 37%`

**Completed:** `0.1 Alpha — Foundation` ✅ · `0.2 Alpha — Native Window + First Renderer` ✅  
**Current milestone:** `0.3 Alpha — Visual Engine` 🚧

Progress only increases for implemented and verified roadmap work. Ideas, mockups and unfinished experiments do not count.

## What is SwirUI?

SwirUI is being built as a complete Python application framework rather than a visual skin over Tkinter, Qt or another widget toolkit. The architecture separates the public Python API, reactive runtime, native platform layer, retained rendering model and native GPU core so each layer can evolve without forcing application code to change.

The long-term goal is a framework that combines a simple Python developer experience with native windows, GPU rendering, responsive layouts, rich effects, animation, professional widgets, accessibility, visual tooling, packaging and AI-assisted development.

SwirUI is currently **pre-alpha**. APIs may change while the native renderer and component system are being developed.

## What already works

- application and window lifecycle
- component tree with cycle protection and reparenting
- event system with direct, capture, target and bubble phases
- thread-safe reactive `State`
- runtime configuration and visual-quality profiles
- renderer and platform abstractions
- retained `RenderTree`
- renderer-ready `SceneGraph`
- geometry and RGBA/HEX color primitives
- **backend-neutral `Path2D` polygon geometry with deterministic convex/concave tessellation**
- **SceneNodeKind.PATH → Python WgpuRenderer → persistent Rust/wgpu triangle rendering**
- path-aware hit testing, clipping, cumulative opacity and reusable native shape buffers
- **retained `PerspectivePlane` projection that compiles logical-DIP 3D tilt/depth into ordinary clipped GPU `Path2D` geometry**
- **bounded live-pointer `Parallax` that maps logical viewport input into deterministic perspective tilt while reusing the persistent path pipeline**
- **quality-aware retained `Reflection` bands compiled into clipped, non-interactive linear-gradient/path geometry**
- **immutable multi-stop linear and radial gradients compiled into retained clipped GPU path geometry**
- **rectangular mesh gradients with bilinear color-lattice sampling and deterministic retained GPU cells**
- **retained `DropShadow`, `Glow`, `DynamicShadow` and source-driven `Bloom` effects flowing through the persistent GPU rectangle batch**
- **retained `AdaptiveLighting` with directional shadow/highlight lobes driven by logical-DIP elevation, light direction and altitude**
- **deterministic retained `Noise` / grain overlays with quality-aware sample budgets and no per-frame random generation**
- **quality-aware effect budgets spanning Performance / Balanced / Quality / Ultra / Cinematic profiles**
- **persistent offscreen scene target plus separable GPU scene-blur postprocess on Windows**
- **painter-order `BackdropBlur` boundaries that blur only already-painted background content while keeping later foreground content sharp**
- **retained `FrostedGlass` and `Acrylic` materials composed from native GPU backdrop blur, tint, border and luminosity layers**
- **deterministic acrylic micro-grain with visual-quality-aware retained density and no per-frame random generation or image uploads**
- invalidation-driven `FrameScheduler`
- backend-neutral `RenderSurface` lifecycle
- render scheduling connected to `AppConfig.target_fps`
- **runtime target-FPS retargeting for existing and future windows**
- **deadline-aware event-loop pacing for 120 / 144+ Hz targets**
- **display-aware per-window pacing capped to the active monitor refresh rate**
- **automatic scheduler retargeting when a native window changes displays**
- frame-time telemetry with configured/effective target FPS, active display refresh, instantaneous/smoothed FPS and pacing error
- deterministic headless backend for tests, servers and CI without a display
- **direct native Win32 backend via Python `ctypes`**
- real Win32 window creation without Tkinter, Qt or SDL
- **direct native Linux/X11 backend via Python `ctypes` + system libX11**
- real X11 window create/map/title/resize/hide/destroy lifecycle verified under Xvfb
- normalized X11 resize, focus, pointer, keyboard, text-input and WM_DELETE_WINDOW close events
- Linux automatically selects X11 when `DISPLAY` is available and retains the headless backend otherwise
- X11 Tab / Shift+Tab key normalization compatible with SwirUI's keyboard-focus traversal
- **direct native macOS Cocoa/AppKit backend via Python `ctypes` + Objective-C runtime**
- real NSWindow create/show/title/resize/hide/destroy lifecycle verified on macOS CI
- CoreGraphics display discovery with primary-display, backing-scale and refresh-rate metadata
- normalized Cocoa pointer, keyboard, text-input, focus, resize and close events
- Retina-safe physical-pixel ↔ Cocoa-point conversion that preserves public logical-DIP geometry
- Cocoa display/scale transitions normalized into the same backend-neutral display and DPI event contract
- **DPI-aware decorated-window sizing that preserves the requested renderable client area exactly**
- **exact physical client-area dimensions across creation and programmatic resize**
- **logical client geometry preserved across Win32 DPI transitions**
- **DPI-aware native minimum-track sizing through `WM_GETMINMAXINFO`**
- native Windows event pump
- normalized close, resize, focus, mouse, keyboard and text-input events
- **normalized Win32 ordinary and system-key messages with Shift/Ctrl/Alt/Meta state captured at dispatch time**
- **Win32 multi-monitor enumeration with virtual-desktop geometry, work areas, per-display scale and refresh rate**
- **per-window active-display mapping plus normalized movement/display-change transitions**
- **logical-DIP public window and SceneGraph geometry with explicit logical ↔ physical conversion helpers**
- **native physical resize and pointer coordinates normalized back into logical DIPs before layout/input routing**
- **per-monitor DPI scaling for rounded rectangles, paths, shaped text, images and clip rectangles before GPU submission**
- per-window effective scale reporting and normalized `WM_DPICHANGED` events
- x64-safe Win32 handle bindings
- visible SceneGraph bring-up renderer for Windows
- **Rust 2024 native core with wgpu 30 + PyO3**
- **real wgpu surface creation from SwirUI's Win32 HWND**
- **GPU adapter/device/queue creation and swapchain configuration**
- **verified GPU clear → submit → present on Windows CI**
- **persistent wgpu context per native window**
- **persistent surface/device/queue/pipeline reuse across frames and resize**
- **configurable AutoVsync / AutoNoVsync presentation with maximum-frame-latency control**
- runtime native presentation reconfiguration verified on a real Win32/wgpu context
- **instanced anti-aliased rounded-rectangle GPU pipeline**
- **per-corner `CornerRadius` rendered by a WGSL SDF shader**
- **native shaped text rendering with glyphon + cosmic-text**
- **persistent font system, glyph atlas, viewport and Swash cache**
- Unicode shaping and text rendering verified on a real Win32 HWND
- **persistent RGBA8 GPU image resources with cached wgpu textures/views/bind groups**
- **content-addressed image cache sharing byte-identical native GPU textures across logical resource ids**
- reference-safe image aliases, transactional multi-context upload rollback and cache telemetry
- **SceneNodeKind.IMAGE → Python resource registry → Rust/wgpu texture submission**
- linear texture sampling, alpha blending and per-image opacity
- registered image resources survive repeated frames and surface resize inside the persistent GPU context
- rounded rectangles, paths, images and shaped text rendered in the same native GPU scene
- **hierarchical `clip_to_bounds` clipping with cumulative ancestor opacity**
- clip-aware rectangles, filled paths, glyphon text bounds and image UV cropping in the native GPU scene
- clip-aware SceneGraph hit testing and fully clipped subtree pruning
- automatic renderer selection: wgpu first on Windows, temporary GDI preview fallback when the native core is unavailable
- z-aware SceneGraph hit testing with painter-order handling
- SceneNode-to-Component mapping by stable key
- routed pointer input through **capture → target → bubble** phases
- pointer target/path enrichment plus `pointer_enter` / `pointer_leave` transitions
- **focusable component contract with pointer-down focus handoff and deterministic focus traversal**
- **Tab / Shift+Tab keyboard-only traversal with hidden/disabled ancestry pruning and stale-focus healing**
- **preventable framework default actions through `Event.prevent_default()` without stopping propagation**
- **routed keyboard and text-input events through the focused component path**
- **backend-neutral accessibility roles and immutable semantic-tree snapshots**
- accessible names/descriptions plus enabled, focusable and focused semantic state with hidden-subtree pruning
- propagation cancellation with `Event.stop_propagation()`
- **retained-runtime performance budgets for 1024-node traversal, hit-testing and retained reflection tessellation workloads**
- median / p95 / worst-case / throughput benchmark reporting with machine-readable CI artifacts
- **integrated real-Windows 0.2 gate covering mixed GPU shapes/text/images/paths, exact client resize, persistent context reuse and routed native pointer/focus input**
- ABI3 native wheel build for Python 3.11+
- real Linux X11 native-window smoke tests on Python 3.14
- real macOS Cocoa native-window + Retina logical-geometry smoke tests on Python 3.14
- Windows native + rounded-GPU + path + shaped-text + image + clipping + mixed-DPI + presentation/display + keyboard/system-key smoke tests on Python 3.14
- **real Win32/wgpu smoke coverage for retained linear, radial and mesh gradients**
- **real Win32/wgpu smoke coverage for retained depth, perspective, pointer-driven parallax and specular reflections across persistent frames**
- **real Win32/wgpu smoke coverage for adaptive lighting, glow, source-driven bloom and deterministic retained noise**
- **real Win32/wgpu smoke coverage for painter-order background blur, frosted glass and acrylic across persistent frames**
- Ruff, Mypy, coverage and Python 3.11–3.14 CI

## Native and GPU demos

Install SwirUI in development mode:

```powershell
git clone https://github.com/Swir/Swirui.git
cd Swirui
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

The native Win32 lifecycle/input demo is:

```powershell
python examples/native_window_demo.py
```

To run the Rust/wgpu demos, install Maturin and the native core inside the same virtual environment:

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
python examples/high_refresh_demo.py
```

The rectangle demo submits prepared SwirUI rectangles into the persistent Rust/wgpu backend. Filled rectangles are batched into one instanced draw call and per-corner radii are evaluated in the fragment shader with anti-aliased SDF edges. The path demo exercises deterministic convex/concave `Path2D` tessellation and the full `SceneGraph → Python → Rust/wgpu` filled-triangle path with clipping and alpha compositing. The gradient demos exercise multi-stop linear, radial and rectangular color-lattice mesh gradients through the retained path pipeline. The depth demo exercises logical-DIP perspective projection, depth translation and live pointer-driven parallax while reusing the same clipped retained `Path2D` GPU path. The reflection demo animates a quality-aware retained specular band through the same clipped linear-gradient/path pipeline without introducing a separate renderer path. The dynamic-effects, bloom, noise and adaptive-lighting demos exercise retained directional lighting, glow, explicit source-driven bloom and deterministic quality-aware grain while preserving the same persistent GPU context. The scene-blur demo exercises the persistent offscreen target and separable full-scene GPU postprocess. The backdrop-blur demo exercises rounded painter-order background-only blur, while the glass-materials demo composes that verified native boundary into frosted glass and acrylic with sharp foreground content. The text demo exercises Unicode shaping through glyphon/cosmic-text and a persistent glyph atlas. The image demo generates RGBA pixels in memory, registers them once and reuses cached native textures; byte-identical image registrations under different logical ids share one retained native texture. The high-refresh demo follows the active display refresh rate automatically. Scene geometry remains authored in logical DIPs while native Win32 input and persistent GPU surfaces operate in physical pixels.

The Linux backend currently provides native X11 windows and normalized input/lifecycle events. The macOS backend provides native Cocoa/AppKit windows, display/Retina scaling and normalized input/lifecycle events. GPU/wgpu presentation on Linux and macOS, plus Wayland support, are not claimed yet.

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

When the native GPU extension is installed on Windows, `App()` selects the wgpu renderer automatically. Explicit renderer injection remains available for tests and custom backends. Linux/X11 and macOS/Cocoa currently provide native window/input backends while retaining the headless renderer until their wgpu presentation paths are implemented and verified.

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
        │     ├── Win32 backend ✅
        │     ├── Linux X11 backend ✅ window/input
        │     └── macOS Cocoa backend ✅ window/input/Retina
        ├── exact DPI-aware Win32 client geometry ✅
        ├── logical-DIP ↔ physical-pixel boundary ✅
        ├── per-window active display + scale + refresh tracking ✅
        ├── Render Tree ✅
        ├── Scene Graph ✅
        ├── Path2D polygon geometry + tessellation ✅
        ├── retained perspective + pointer parallax geometry ✅
        ├── retained reflection gradient/path geometry ✅
        ├── z-aware + clip-aware + path-aware Scene hit testing ✅
        ├── SceneNode → Component mapping ✅
        ├── Render Surface lifecycle ✅
        ├── display-aware deadline Frame Scheduler ✅
        ├── pointer capture / target / bubble routing ✅
        └── focused keyboard / text-input routing + Tab traversal ✅
        │
Renderer Layer
        │
        ├── GPU surface / swapchain ✅ Windows
        ├── persistent per-window GPU context ✅ Windows
        ├── DPI-scaled physical GPU submission ✅ Windows
        ├── VSync / present-mode policy ✅ Windows
        ├── instanced anti-aliased rounded rectangles ✅
        ├── filled convex/concave Path2D triangles ✅
        ├── retained depth / perspective / parallax paths ✅
        ├── retained specular reflections ✅
        ├── retained linear / radial / mesh gradients ✅
        ├── retained shadows / glow / source bloom ✅
        ├── adaptive directional lighting + retained grain ✅
        ├── persistent offscreen target + separable scene blur ✅ Windows
        ├── painter-order rounded backdrop/background blur ✅ Windows
        ├── retained frosted glass + acrylic materials ✅ Windows
        ├── shaped text + persistent glyph atlas ✅
        ├── persistent content-addressed RGBA image cache ✅
        ├── hierarchical clipping / opacity compositing ✅
        └── advanced materials / custom shaders 🚧
        │
Native Core
        │
        └── Rust + wgpu + PyO3 ✅ foundation online
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
- **SwirUI Studio** — future drag-and-drop visual builder with editable Python output.
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

The 0.2 Alpha native/runtime gate is verified complete. Windows has the persistent wgpu renderer and integrated mixed-scene native gate; Linux has a real direct X11 native window/input path under Xvfb; macOS has a direct Cocoa/AppKit native window/input path with Retina logical-geometry verification. Cross-platform GPU presentation beyond Windows remains future work and is not implied by the native-window milestone.

0.3 is now active. Retained **linear / radial / mesh gradients**, **depth and perspective**, **pointer-driven parallax**, **reflections**, **dynamic shadows**, **adaptive directional lighting**, **glow**, explicit **source-driven bloom**, deterministic **noise / grain**, **painter-order background blur**, **frosted glass** and **acrylic-like materials** are implemented and verified through the clipped, HiDPI-aware persistent GPU scene pipeline, including real Win32/wgpu smoke coverage. Perspective, parallax and reflections compile into ordinary retained `Path2D`/gradient geometry, so they inherit the existing clipping, compositing, hit-testing and mixed-DPI contracts without a parallel rendering backend. Backdrop regions reuse persistent native blur/compositor resources, lighting and grain reuse retained rectangle batches, and material foreground content remains sharp above deterministic tint, border, luminosity and quality-aware grain layers. The next high-impact work is effect caching for unchanged backdrop/material regions so expensive intermediate blur work can be reused safely across high-refresh frames, followed by a reusable color-filter/custom-shader path. Native accessibility adapters, Wayland/Linux expansion, macOS GPU presentation and continued measured performance work remain important cross-cutting follow-ups without reopening the completed 0.2 gate.

See **[ROADMAP.md](ROADMAP.md)** for the full development plan.

## Quality policy

Every significant runtime change is expected to pass:

```text
Ruff
Mypy
pytest + coverage
Python 3.11
Python 3.12
Python 3.13
Python 3.14
retained-runtime performance budgets + JSON report artifact
accessibility semantic-tree tests
cargo check
cargo test
Linux real-X11 native-window smoke test under Xvfb
macOS real-Cocoa native-window + Retina logical-geometry smoke test
Windows native smoke test
Windows integrated 0.2 mixed-scene + exact-client + routed-input gate
Windows active-display / refresh-rate mapping smoke test
Windows WM_DISPLAYCHANGE / WM_DPICHANGED normalization smoke tests
Windows keyboard / system-key normalization smoke test
Windows wgpu clear/present smoke test
Windows persistent rounded-rectangle GPU draw smoke test
Windows filled Path2D SceneGraph → Python → Rust/wgpu smoke test
Windows retained linear / radial / mesh gradient GPU smoke tests
Windows retained depth / perspective / parallax / reflection GPU smoke test
Windows retained adaptive-lighting / glow / bloom / noise GPU smoke test
Windows retained backdrop/background-blur + glass/acrylic GPU smoke test
Windows shaped-text SceneGraph → Python → Rust/wgpu smoke test
Windows image-resource SceneGraph → Python → Rust/wgpu smoke test
Windows clipped mixed-scene GPU smoke test
Windows mixed-DPI logical-DIP → physical-GPU smoke test
Windows presentation-policy reconfiguration smoke test
Display-aware high-refresh runtime pacing tests
Routed keyboard focus / text-input / preventable Tab traversal tests
```

SwirUI will not claim to outperform another framework without reproducible measurements. The first CI guardrails cover retained SceneGraph traversal and pointer hit testing over a 1024-node scene plus deterministic 96-step reflection tessellation. Planned expansion includes startup time, RAM, CPU/GPU usage, frame time, input latency, component creation, large lists and animation performance.

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