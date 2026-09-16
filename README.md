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
![Progress](https://img.shields.io/badge/project%20progress-8%25-00BFFF)

</div>

---

## Project progress

**8% — 0.2 Alpha: Native Window + First Renderer in progress**

`[██░░░░░░░░░░░░░░░░░░] 8%`

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
- event system
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
- **instanced filled-rectangle GPU pipeline with a single draw call for the batch**
- **SceneGraph → Python WgpuRenderer → Rust/wgpu rectangle submission**
- automatic renderer selection: wgpu first on Windows, temporary GDI preview fallback when the native core is unavailable
- z-aware SceneGraph hit testing with painter-order handling
- pointer target/path enrichment plus `pointer_enter` / `pointer_leave` transitions
- ABI3 native wheel build for Python 3.11+
- Windows native + GPU rectangle smoke tests on Python 3.14
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

To run the current Rust/wgpu rectangle demo, install Maturin and the native core inside the same virtual environment:

```powershell
python -m pip install maturin==1.15.0
cd native
maturin develop --release
cd ..
python examples/gpu_rectangles_demo.py
```

The GPU demo submits a prepared SwirUI `SceneGraph` into the Rust/wgpu backend and renders its filled rectangles through an instanced GPU pipeline. The native renderer now keeps its GPU context alive across frames and reconfigures the existing surface on resize instead of recreating the GPU device and pipeline. Rounded corners, native text and images are intentionally still open renderer milestones.

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

When the native GPU extension is installed on Windows, `App()` now selects the wgpu renderer automatically. Explicit renderer injection remains available for tests and custom backends.

## Architecture

```text
Python Application API
        │
        ├── App / Window lifecycle
        ├── Components / Events
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
        ├── Render Surface lifecycle ✅
        ├── Frame Scheduler ✅
        └── Input normalization + pointer targeting ✅
        │
Renderer Layer
        │
        ├── GPU surface / swapchain ✅
        ├── persistent per-window GPU context ✅
        ├── SceneGraph rectangle submission ✅
        ├── instanced filled rectangles ✅
        ├── rounded rectangles ← NEXT
        ├── text / images
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

The native Windows foundation, real wgpu presentation, first SceneGraph GPU primitive path and persistent per-window GPU context are now verified. The next renderer/runtime work is:

1. anti-aliased GPU rounded rectangles using `CornerRadius`
2. native text and image rendering
3. clipping and compositing
4. routed/capture/bubbling input over scene/component paths
5. robust DPI / HiDPI and multi-monitor handling
6. display-aware high-refresh presentation
7. present-mode selection and frame pacing
8. GPU resource reuse/caching for dynamic scene data

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
Windows real instanced-rectangle GPU draw smoke test
Windows persistent GPU context multi-frame + resize smoke test
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
