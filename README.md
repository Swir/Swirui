<!-- SWIR-README-STANDARD:v1 -->

<div align="center">

<img src="assets/swirui-icon.svg" width="136" alt="SwirUI icon">

# ⚡ SwirUI

### Native, reactive and GPU-first desktop UI framework for Python

**Python public API • Rust + wgpu native core • High-refresh desktop rendering**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-02050A?style=for-the-badge&logo=python&logoColor=62E5FF)
![Rust](https://img.shields.io/badge/Rust-Native%20Core-02050A?style=for-the-badge&logo=rust&logoColor=62E5FF)
![wgpu](https://img.shields.io/badge/wgpu-30.0.1-02050A?style=for-the-badge&logo=webgpu&logoColor=62E5FF)
![Windows](https://img.shields.io/badge/Windows-Win32%20GPU-02050A?style=for-the-badge&logo=windows11&logoColor=62E5FF)

[![CI](https://img.shields.io/github/actions/workflow/status/Swir/Swirui/ci.yml?branch=main&style=flat-square&label=CI&color=0088FF)](https://github.com/Swir/Swirui/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-pre--alpha-0088FF?style=flat-square)
![Progress](https://img.shields.io/badge/project%20progress-40%25-0088FF?style=flat-square)

</div>

<img width="100%" src="https://raw.githubusercontent.com/Swir/Swir/main/assets/power-divider-v4.svg" alt="SWIR electric divider" />

## Project Status

**40% — 0.3 Alpha Visual Engine is active.**

`[████████░░░░░░░░░░░░] 40%`

- `0.1 Alpha — Foundation` ✅
- `0.2 Alpha — Native Window + First Renderer` ✅
- `0.3 Alpha — Visual Engine` 🚧

Progress increases only for implemented and verified roadmap work. Documentation-only changes, skeletons and unfinished experiments do not increase the percentage.

SwirUI is **pre-alpha**. Public APIs may still change while the renderer, widget system and higher-level runtime are developed. There is no public GitHub Release yet.

## Overview

SwirUI is being built as a complete Python desktop application framework rather than a visual skin over Tkinter, Qt or another widget toolkit. Python remains the public developer API, while Rust, wgpu and PyO3 own performance-critical native rendering work.

The current Windows renderer uses a persistent per-window wgpu context and a retained SceneGraph. Linux/X11 and macOS/Cocoa already have real native window and input backends. GPU presentation on Linux/macOS and Wayland support remain future work and are not claimed as complete.

## Highlights

| Feature | Current verified capability |
|---|---|
| Native windows | Direct Win32, X11 and Cocoa/AppKit backends without Tkinter/Qt/SDL |
| GPU renderer | Persistent Rust/wgpu renderer context on Windows with retained scene submission |
| Shapes | Anti-aliased rounded rectangles plus convex/concave `Path2D` geometry |
| Text | Persistent shaped Unicode text through glyphon/cosmic-text |
| Images | Content-addressed RGBA GPU cache with aliases, telemetry and safe lifetime management |
| Composition | Hierarchical clipping, cumulative opacity and painter-order retained composition |
| HiDPI | Logical-DIP public geometry with physical-pixel native/GPU conversion |
| Displays | Multi-monitor mapping, refresh discovery and 60/120/144+ Hz display-aware pacing |
| Visual Engine | Gradients, shadows, glow, bloom, depth, parallax, reflections and adaptive lighting |
| Materials | Native backdrop blur, FrostedGlass and Acrylic with deterministic grain |
| Post-processing | Persistent scene blur and affine RGBA color filters |
| Performance | Adaptive visual-quality profiles plus retained effect and GPU resource caches |
| Accessibility | Semantic roles/tree, keyboard focus routing and keyboard-only traversal foundation |
| Custom shaders | Bounded Python WGSL effect contract and native validation are in progress; runtime shader application is not complete yet |

## Quick Start

### Python development environment

```powershell
git clone https://github.com/Swir/Swirui.git
cd Swirui
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the native-window demo:

```powershell
python examples/native_window_demo.py
```

### Windows GPU development

The verified wgpu presentation path currently targets Windows. Build the PyO3 extension into the active environment:

```powershell
python -m pip install maturin==1.15.0
cd native
maturin develop --release
cd ..
python examples/gpu_rectangles_demo.py
```

## Requirements & Compatibility

| Area | Status |
|---|---|
| Python | 3.11, 3.12, 3.13 and 3.14 are tested in CI |
| Windows | Native Win32 backend + verified Rust/wgpu presentation path |
| Linux | Native X11 window/input backend verified under Xvfb |
| macOS | Native Cocoa/AppKit window/input backend with Retina logical geometry |
| Wayland | Planned |
| Linux/macOS GPU presentation | Planned; not yet claimed |
| Native GPU build | Stable Rust toolchain + Maturin + PyO3 ABI3 |

## Usage

Foundation API:

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

When the native GPU extension is installed on Windows, SwirUI can select the wgpu renderer automatically. Explicit renderer injection remains available for tests and custom backends.

### GPU and runtime examples

```text
examples/gpu_rectangles_demo.py
examples/gpu_text_demo.py
examples/gpu_image_demo.py
examples/gpu_paths_demo.py
examples/gpu_gradients_demo.py
examples/gpu_mesh_gradients_demo.py
examples/gpu_depth_demo.py
examples/gpu_reflections_demo.py
examples/gpu_dynamic_effects_demo.py
examples/gpu_bloom_demo.py
examples/gpu_noise_demo.py
examples/gpu_adaptive_lighting_demo.py
examples/gpu_scene_blur_demo.py
examples/gpu_backdrop_blur_demo.py
examples/gpu_glass_materials_demo.py
examples/gpu_color_filters_demo.py
examples/gpu_native_effect_frame_cache_demo.py
examples/adaptive_quality_demo.py
examples/high_refresh_demo.py
```

These examples exercise the same retained contracts used by applications. Public geometry remains in logical DIPs while native surfaces and GPU submission operate in physical pixels.

## Technology & Architecture

```text
Python Application API
        │
        ├── App / Window / Component / State
        ├── Routed input + accessibility semantics
        └── Runtime configuration + adaptive visual quality
        │
SwirUI Runtime
        │
        ├── Win32 / X11 / Cocoa native backends
        ├── logical DIP ↔ physical pixel boundary
        ├── retained RenderTree / SceneGraph
        └── display-aware frame scheduler
        │
Renderer Layer
        │
        ├── persistent Windows wgpu context
        ├── rectangles / paths / shaped text / images
        ├── blur / backdrop / glass / acrylic
        ├── gradients / depth / lighting / bloom / color filters
        └── retained GPU/effect caches
        │
Native Core
        │
        └── Rust 2024 + wgpu 30 + PyO3 ABI3
```

The active custom-shader work keeps the Python API intentionally narrow: application code supplies a pure WGSL color-effect function, while SwirUI owns GPU bindings, entry points and validation. Native runtime pipeline creation and persistent pipeline caching are still required before the roadmap item can be marked complete.

## Testing & Quality

Every significant runtime change is expected to preserve the existing quality gates:

- Ruff and strict Mypy
- pytest on Python 3.11–3.14
- retained-runtime performance budgets with JSON reports
- `cargo check` and `cargo test`
- Maturin / PyO3 native build
- real Linux/X11 and macOS/Cocoa native-window smoke tests
- real Win32 + wgpu smoke tests
- integrated 0.2 native renderer/runtime gate
- HiDPI, multi-monitor, presentation-policy, text, image, path, effects and cache coverage

SwirUI does not claim performance superiority over other frameworks without reproducible measurements.

## Roadmap

The authoritative plan is **[ROADMAP.md](ROADMAP.md)**.

The remaining 0.3 milestone item is **Custom shader effects**. The current branch-level work establishes a bounded Python effect contract and native Naga WGSL validation, but the roadmap item remains open until persistent native pipeline creation/caching and real renderer application are implemented and verified.

## Releases

There is currently **no public GitHub Release** for SwirUI. Development is source-first while the alpha gates are still being completed.

- Development history: **[CHANGELOG.md](CHANGELOG.md)**
- Full roadmap: **[ROADMAP.md](ROADMAP.md)**
- CI status: **[GitHub Actions](https://github.com/Swir/Swirui/actions)**

## Repository Structure

```text
Swirui/
├── .github/workflows/      # Python, Rust and native-platform CI
├── assets/                 # SwirUI icon and visual assets
├── benchmarks/             # reproducible performance budgets
├── docs/                   # architecture documentation
├── examples/               # native/runtime/GPU examples
├── native/                 # Rust + wgpu + PyO3 core
├── src/swirui/             # public Python framework and renderer bridge
├── tests/                  # automated unit/integration/native smoke tests
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
└── pyproject.toml
```

## 🔎 Search Keywords

`python desktop gui` • `python gpu ui` • `native python ui framework` • `wgpu python renderer` • `rust pyo3 gui` • `win32 python gui` • `reactive desktop ui` • `high refresh rate ui` • `hidpi desktop ui` • `gpu text rendering` • `frosted glass ui` • `acrylic desktop ui` • `custom wgsl effects` • `multi monitor python ui`

<img width="100%" src="https://raw.githubusercontent.com/Swir/Swir/main/assets/power-divider-v4.svg" alt="SWIR electric divider" />

<div align="center">

### `BUILD • TEST • RENDER • EVOLVE`

⭐ **If SwirUI is useful or interesting, consider leaving a star.**

[**← SWIR profile**](https://github.com/Swir) · [**All projects →**](https://github.com/Swir?tab=repositories)

</div>
