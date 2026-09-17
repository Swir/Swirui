<div align="center">

<img src="assets/swirui-icon.svg" width="136" alt="SwirUI icon">

# ⚡ SwirUI

### Next-generation Python UI framework for native, reactive and GPU-first desktop applications.

**Beautiful by default. Native at the core. Built for the future.**

[![CI](https://github.com/Swir/Swirui/actions/workflows/ci.yml/badge.svg)](https://github.com/Swir/Swirui/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)
![Windows Native](https://img.shields.io/badge/Windows-Win32%20native-0078D4?logo=windows11&logoColor=white)
![GPU](https://img.shields.io/badge/GPU-wgpu%2030-6E56CF)
![Status](https://img.shields.io/badge/status-pre--alpha-7C3AED)
![Progress](https://img.shields.io/badge/project%20progress-22%25-00BFFF)

</div>

---

## Project progress

**22% — 0.2 Alpha: Native Window + First Renderer in progress**

`[████░░░░░░░░░░░░░░░░] 22%`

**Completed:** `0.1 Alpha — Foundation` ✅  
**Current milestone:** `0.2 Alpha — Native Window + First Renderer` 🚧

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
- invalidation-driven `FrameScheduler`
- backend-neutral `RenderSurface` lifecycle
- render scheduling connected to `AppConfig.target_fps`
- **runtime target-FPS retargeting for existing and future windows**
- **deadline-aware event-loop pacing for 120 / 144+ Hz targets**
- **display-aware per-window pacing capped to the active monitor refresh rate**
- **automatic scheduler retargeting when a native window changes displays**
- frame-time telemetry with configured/effective target FPS, active display refresh, instantaneous/smoothed FPS and pacing error
- deterministic headless backend for tests and CI
- **direct native Win32 backend via Python `ctypes`**
- real Win32 window creation without Tkinter, Qt or SDL
- **DPI-aware decorated-window sizing that preserves the requested renderable client area exactly**
- **exact physical client-area dimensions across creation and programmatic resize**
- **logical client geometry preserved across Win32 DPI transitions**
- **DPI-aware native minimum-track sizing through `WM_GETMINMAXINFO`**
- native Windows event pump
- normalized close, resize, focus, mouse, keyboard and text-input events
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
- **routed keyboard and text-input events through the focused component path**
- **backend-neutral accessibility roles and immutable semantic-tree snapshots**
- accessible names/descriptions plus enabled, focusable and focused semantic state with hidden-subtree pruning
- propagation cancellation with `Event.stop_propagation()`
- **retained-runtime performance budgets for 1024-node traversal and hit-testing workloads**
- median / p95 / worst-case / throughput benchmark reporting with machine-readable CI artifacts
- **integrated real-Windows 0.2 gate covering mixed GPU shapes/text/images/paths, exact client resize, persistent context reuse and routed native pointer/focus input**
- ABI3 native wheel build for Python 3.11+
- Windows native + rounded-GPU + path + shaped-text + image + clipping + mixed-DPI + presentation/display smoke tests on Python 3.14
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
python examples/high_refresh_demo.py
```

The rectangle demo submits prepared SwirUI rectangles into the persistent Rust/wgpu backend. Filled rectangles are batched into one instanced draw call and per-corner radii are evaluated in the fragment shader with anti-aliased SDF edges. The path demo exercises deterministic convex/concave `Path2D` tessellation and the full `SceneGraph → Python → Rust/wgpu` filled-triangle path with clipping and alpha compositing. The text demo exercises Unicode shaping through glyphon/cosmic-text and a persistent glyph atlas. The image demo generates RGBA pixels in memory, registers them once and reuses cached native textures; byte-identical image registrations under different logical ids share one retained native texture. The high-refresh demo follows the active display refresh rate automatically. Scene geometry remains authored in logical DIPs while native Win32 input and persistent GPU surfaces operate in physical pixels.

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
        ├── Native Platform Backend
        │     └── Win32 backend ✅
        ├── exact DPI-aware Win32 client geometry ✅
        ├── logical-DIP ↔ physical-pixel boundary ✅
        ├── per-window active display + scale + refresh tracking ✅
        ├── Render Tree ✅
        ├── Scene Graph ✅
        ├── Path2D polygon geometry + tessellation ✅
        ├── z-aware + clip-aware + path-aware Scene hit testing ✅
        ├── SceneNode → Component mapping ✅
        ├── Render Surface lifecycle ✅
        ├── display-aware deadline Frame Scheduler ✅
        ├── pointer capture / target / bubble routing ✅
        └── focused keyboard / text-input routing ✅
        │
Renderer Layer
        │
        ├── GPU surface / swapchain ✅
        ├── persistent per-window GPU context ✅
        ├── DPI-scaled physical GPU submission ✅
        ├── VSync / present-mode policy ✅
        ├── instanced anti-aliased rounded rectangles ✅
        ├── filled convex/concave Path2D triangles ✅
        ├── shaped text + persistent glyph atlas ✅
        ├── persistent content-addressed RGBA image cache ✅
        ├── hierarchical clipping / opacity compositing ✅
        └── effects / shaders
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

## Current 0.2 Alpha focus

The native Windows foundation, exact DPI-aware client geometry, persistent wgpu renderer, rounded and general filled GPU shapes, shaped GPU text, persistent content-addressed GPU images, hierarchical clipping/compositing, routed pointer/keyboard input, explicit present-mode policy, robust logical-DIP/physical-pixel HiDPI handling, multi-monitor discovery and display-aware high-refresh pacing are verified. A real Windows integration gate now exercises the mixed GPU scene, exact resize behavior, persistent context reuse and native routed input together. Retained-runtime performance budgets and the first backend-neutral accessibility semantic contract are also verified. The largest remaining 0.2 hardening work is:

1. deeper focus management, keyboard-only navigation and native accessibility adapters
2. continued measured retained-runtime/input optimization under CI budgets
3. cross-platform native backend expansion after the Windows gate is hardened

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
Windows native smoke test
Windows integrated 0.2 mixed-scene + exact-client + routed-input gate
Windows active-display / refresh-rate mapping smoke test
Windows WM_DISPLAYCHANGE / WM_DPICHANGED normalization smoke tests
Windows wgpu clear/present smoke test
Windows persistent rounded-rectangle GPU draw smoke test
Windows filled Path2D SceneGraph → Python → Rust/wgpu smoke test
Windows shaped-text SceneGraph → Python → Rust/wgpu smoke test
Windows image-resource SceneGraph → Python → Rust/wgpu smoke test
Windows clipped mixed-scene GPU smoke test
Windows mixed-DPI logical-DIP → physical-GPU smoke test
Windows presentation-policy reconfiguration smoke test
Display-aware high-refresh runtime pacing tests
Routed keyboard focus / text-input tests
```

SwirUI will not claim to outperform another framework without reproducible measurements. The first CI guardrails cover retained SceneGraph traversal and pointer hit testing over a 1024-node scene. Planned expansion includes startup time, RAM, CPU/GPU usage, frame time, input latency, component creation, large lists and animation performance.

## Repository layout

```text
Swirui/
├── .github/workflows/      # Python, Rust and native GPU CI
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
