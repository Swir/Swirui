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

**3% — Foundation in progress**

`[█░░░░░░░░░░░░░░░░░░░] 3%`

The percentage reflects completed and tested roadmap work. It is not increased for ideas, mockups or unfinished prototypes.

## What is SwirUI?

SwirUI is being designed as a complete application framework for Python rather than a skin over an existing widget toolkit. The long-term architecture combines a simple Python API with a high-performance native/GPU rendering core, reactive state, responsive layouts, advanced animation, desktop integration, visual tooling and AI-assisted development.

The project is currently **pre-alpha**. The public API will change while the foundation is built.

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

## First API direction

```python
from swirui import App, Window
from swirui.core import Component, State

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

> The current runtime is intentionally minimal. Native windows and GPU rendering arrive in later milestones; the foundation first establishes stable lifecycle, component, event and state contracts.

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

## Current milestone — 0.1 Alpha: Foundation

The first milestone establishes contracts that everything else will depend on:

- application lifecycle
- window model
- component tree
- event system
- reactive state
- logging and configuration foundations
- renderer abstraction
- platform abstraction
- test suite
- CI across supported Python versions

See **[ROADMAP.md](ROADMAP.md)** for the complete plan.

## Performance philosophy

SwirUI will not claim to be faster than another framework without measurements. Benchmarks will publish hardware, OS, framework versions and reproducible source code. Planned metrics include startup time, memory, CPU/GPU usage, frame time, input latency, large-list performance and animation performance.

## Project status

SwirUI is experimental and not ready for production applications yet. The repository is being developed in public from its architecture foundation upward.

---

<div align="center">

### ⚡ SwirUI

**Designed and developed by [Swir](https://github.com/Swir)**

</div>
