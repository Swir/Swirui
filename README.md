<div align="center">

# ⚡ SwirUI

### A next-generation Python UI framework built for beautiful, reactive and GPU-first desktop applications.

**Beautiful by default. Powerful when needed. Fast everywhere.**

[![CI](https://github.com/Swir/Swirui/actions/workflows/ci.yml/badge.svg)](https://github.com/Swir/Swirui/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776AB?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/status-pre--alpha-7C3AED)
![Progress](https://img.shields.io/badge/project%20progress-3%25-00BFFF)

</div>

---

## Project progress

**3% — 0.1 Alpha Foundation complete ✅**

`[█░░░░░░░░░░░░░░░░░░░] 3%`

**Current milestone:** `0.2 Alpha — Native Window + First Renderer`

The percentage reflects completed and tested roadmap work. It is not increased for ideas, mockups or unfinished prototypes.

## What is SwirUI?

SwirUI is being designed as a complete application framework for Python rather than a skin over an existing widget toolkit. The long-term architecture combines a simple Python API with a high-performance native/GPU rendering core, reactive state, responsive layouts, advanced animation, desktop integration, visual tooling and AI-assisted development.

The project is currently **pre-alpha**. The public API may change while the renderer, native backends and widget systems are developed.

## Core goals

- **Future-grade visuals** — glass, blur, glow, gradients, shaders, depth, lighting and fluid animation.
- **GPU-first rendering** — a renderer designed for modern displays and high refresh rates.
- **Simple Python API** — powerful UI without excessive boilerplate.
- **Reactive state** — data changes should update the interface naturally.
- **Responsive layouts** — one application should scale from compact windows to 4K and ultrawide displays.
- **Professional widgets** — from buttons and forms to DataGrid, docking, code editor, charts, media and 3D viewports.
- **Developer tooling** — hot reload, inspector, profiler, testing and packaging.
- **SwirUI Studio** — a future visual UI designer with live preview and code generation.
- **AI-ready architecture** — AI-generated layouts remain ordinary editable SwirUI components.
- **Cross-platform direction** — Windows, Linux and macOS are the primary desktop targets.

## Foundation API

```python
from swirui import App, Component, State, Window

counter = State(0)

app = App(name="SwirUI Demo")
window = Window(title="Future starts here", width=1100, height=720)

root = Component("dashboard")
window.set_root(root)
app.add_window(window)

counter.subscribe(lambda value: print(f"Counter: {value}"))
counter.set(1)

app.run()
```

> The current runtime is intentionally minimal. The completed 0.1 foundation establishes lifecycle, component, event, state, renderer and platform contracts. Native windows and the first real rendering pipeline are the focus of 0.2 Alpha.

## Architecture direction

```text
Python API
   │
   ├── Application / Window lifecycle
   ├── Reactive State
   ├── Component Tree
   ├── Events
   ├── Layout / Widgets
   │
SwirUI Runtime
   │
   ├── Renderer abstraction
   ├── Platform abstraction
   └── Native bridge
   │
Rust Native Core (planned)
   │
   ├── GPU renderer
   ├── text / images / effects
   ├── layout acceleration
   └── platform integration
   │
GPU / Operating System
```

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

## Repository layout

```text
Swirui/
├── .github/workflows/      # CI
├── docs/                   # architecture and design notes
├── examples/               # runnable examples
├── src/swirui/             # framework source
├── tests/                  # automated tests
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
└── pyproject.toml
```

## Development setup

```bash
git clone https://github.com/Swir/Swirui.git
cd Swirui
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
python -m pip install -e ".[dev]"
pytest
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Completed milestone — 0.1 Alpha: Foundation

The foundation now includes:

- application lifecycle
- window model
- component tree with cycle protection and reparenting
- event system
- thread-safe reactive state
- logging and runtime configuration
- renderer abstraction and headless renderer
- platform abstraction and headless platform backend
- automated tests
- strict Ruff and Mypy quality gates
- CI verified on Python 3.11, 3.12, 3.13 and 3.14
- architecture documentation

## Current milestone — 0.2 Alpha: Native Window + First Renderer

The next milestone moves SwirUI from the framework foundation toward visible UI output. It targets the native desktop window backend, event-loop integration, input dispatch, render tree, scene graph, frame scheduler, GPU surface, basic shapes/text/images, compositing, DPI handling and high-refresh-rate scheduling.

See **[ROADMAP.md](ROADMAP.md)** for the complete plan.

## Performance philosophy

SwirUI will not claim to be faster than another framework without measurements. Benchmarks will publish hardware, OS, framework versions and reproducible source code. Planned metrics include startup time, memory, CPU/GPU usage, frame time, input latency, large-list performance and animation performance.

## Project status

SwirUI is experimental and not ready for production applications yet. The 0.1 architecture foundation is complete and development is moving into the first native/rendering milestone.

---

<div align="center">

### ⚡ SwirUI

**Designed and developed by [Swir](https://github.com/Swir)**

</div>
