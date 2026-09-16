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
![Progress](https://img.shields.io/badge/project%20progress-10%25-00BFFF)

</div>

---

## Project progress

**10% — 0.2 Alpha: Native Window + First Renderer in progress**

`[██░░░░░░░░░░░░░░░░░░] 10%`

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
- invalidation-driven `FrameScheduler`
- backend-neutral `RenderSurface` lifecycle
- render scheduling connected to `AppConfig.target_fps`
- deterministic headless backend for tests and CI
- **direct native Win32 backend via Python `ctypes`**
- real Win32 window creation without Tkinter, Qt or SDL
- native Windows event pump
- normalized close, resize, focus, mouse, keyboard and text-input events
- x64-safe Win32 handle bindings
- visible SceneGraph bring-up renderer for Windows
- **Rust 2024 native core with wgpu 30 + PyO3**
- **real wgpu surface creation from SwirUI's Win32 HWND**
- **GPU adapter/device/queue creation and swapchain configuration**
- **verified GPU clear → submit → present on Windows CI**
- **persistent wgpu context per native window**
- **persistent surface/device/queue/pipeline reuse across frames and resize**
- **instanced anti-aliased rounded-rectangle GPU pipeline**
- **per-corner `CornerRadius` rendered by a WGSL SDF shader**
- **SceneGraph → Python WgpuRenderer → Rust/wgpu primitive submission**
- **native shaped text rendering with glyphon + cosmic-text**
- **persistent font system, glyph atlas, viewport and Swash cache**
- **SceneNodeKind.TEXT → Python WgpuRenderer → Rust/glyphon/wgpu submission**
- Unicode shaping and text rendering verified on a real Win32 HWND
- text and rounded rectangles rendered through the same persistent GPU scene context
- automatic renderer selection: wgpu first on Windows, temporary GDI preview fallback when the native core is unavailable
- z-aware SceneGraph hit testing with painter-order handling
- SceneNode-to-Component mapping by stable key
- routed pointer input through **capture → target → bubble** phases
- pointer target/path enrichment plus `pointer_enter` / `pointer_leave` transitions
- propagation cancellation with `Event.stop_propagation()`
- ABI3 native wheel build for Python 3.11+
- Windows native + persistent rounded-GPU + shaped-text smoke tests on Python 3.14
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
```

The rectangle demo submits a prepared SwirUI `SceneGraph` into the Rust/wgpu backend. Filled rectangles are batched into one instanced draw call and per-corner radii are evaluated in the fragment shader with anti-aliased SDF edges. The text demo exercises the full `SceneGraph → Python → Rust → glyphon → wgpu` path with Unicode shaping, multiple font sizes and a persistent glyph atlas. The native renderer keeps its GPU context alive across frames and reconfigures the existing surface and text viewport on resize instead of recreating the GPU device and pipelines.

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

counter.subscribe(lambda value: print(f"Counter: {value}"))
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
        ├── Reactive State
        └── Runtime configuration
        │
SwirUI Runtime
        │
        ├── Native Platform Backend
        │     └── Win32 backend ✅
        ├── Render Tree ✅
        ├── Scene Graph ✅
        ├── z-aware Scene hit testing ✅
        ├── SceneNode → Component mapping ✅
        ├── Render Surface lifecycle ✅
        ├── Frame Scheduler ✅
        └── capture / target / bubble input routing ✅
        │
Renderer Layer
        │
        ├── GPU surface / swapchain ✅
        ├── persistent per-window GPU context ✅
        ├── SceneGraph rectangle submission ✅
        ├── instanced filled rectangles ✅
        ├── anti-aliased per-corner rounded rectangles ✅
        ├── shaped text + persistent glyph atlas ✅
        ├── images ← NEXT
        ├── clipping / compositing
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

The native Windows foundation, persistent wgpu renderer, rounded GPU primitives, shaped GPU text and routed component pointer input are verified. The next renderer/runtime work is:

1. image rendering
2. clipping and compositing
3. robust DPI / HiDPI and multi-monitor handling
4. display-aware high-refresh presentation
5. present-mode selection and frame pacing
6. reusable dynamic GPU buffers/resource caching
7. keyboard focus routing and accessibility groundwork

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
cargo check
cargo test
Windows native smoke test
Windows wgpu clear/present smoke test
Windows persistent rounded-rectangle GPU draw smoke test
Windows shaped-text SceneGraph → Python → Rust/wgpu smoke test
```

SwirUI will not claim to outperform another framework without reproducible measurements. Planned benchmarks include startup time, RAM, CPU/GPU usage, frame time, input latency, component creation, large lists and animation performance.

## Repository layout

```text
Swirui/
├── .github/workflows/      # Python, Rust and native GPU CI
├── assets/                 # SwirUI visual assets and icon
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
