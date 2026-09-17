# SwirUI Roadmap

> Next-generation Python UI framework: native, GPU-first, reactive, beautiful and extensible.

## Project progress

**Overall completion: 36%**

`[███████░░░░░░░░░░░░░] 36%`

Progress is based on implemented and verified roadmap work. Ideas, mockups and unfinished prototypes do not increase the percentage.

---

## 0.1 Alpha — Foundation

**Status:** Complete ✅

- [x] Repository initialized
- [x] Package metadata and development tooling
- [x] Application lifecycle
- [x] Window lifecycle/model
- [x] Component tree
- [x] Event system
- [x] Reactive `State`
- [x] Configuration system
- [x] Logging system
- [x] Renderer abstraction
- [x] Platform abstraction
- [x] Automated tests
- [x] CI on Python 3.11–3.14
- [x] Architecture documentation

## 0.2 Alpha — Native Window + First Renderer

**Status:** Complete ✅

### Native runtime

- [x] Direct Windows native backend using Win32 + `ctypes`
- [x] Native Win32 HWND creation without Tkinter / Qt / SDL
- [x] x64-safe Win32 handle bindings
- [x] Native event-loop integration
- [x] Window-level input normalization
- [x] Close / resize / focus events
- [x] Mouse move / button events
- [x] Keyboard down / up events
- [x] Text-input events
- [x] Automatic platform backend selection
- [x] Automatic renderer selection on Windows: wgpu first, preview fallback
- [x] Windows-native smoke test on GitHub Actions
- [x] Exact decorated Win32 client-area sizing across create and programmatic resize
- [x] DPI-aware native minimum-track sizing
- [x] Logical client geometry preserved across Win32 DPI transitions
- [x] Scene-level z-aware hit testing
- [x] Pointer events enriched with SceneGraph target + ancestry path
- [x] Pointer enter / leave transitions
- [x] SceneNode-to-Component mapping by stable key
- [x] Routed capture / target / bubbling component pointer input
- [x] Event propagation cancellation
- [x] Linux native backend
- [x] macOS native backend

### Rendering runtime

- [x] Render tree
- [x] Scene graph
- [x] Geometry and color primitives
- [x] Frame scheduler
- [x] Invalidation-driven rendering
- [x] Backend-neutral `RenderSurface` lifecycle
- [x] Runtime surface recreation on resize
- [x] `AppConfig.target_fps` connected to frame scheduling
- [x] Runtime target-FPS retargeting and deadline-aware frame pacing
- [x] Real GPU surface / swapchain on Windows via Rust + wgpu
- [x] GPU adapter/device/queue creation
- [x] Verified clear → submit → present to a real SwirUI HWND
- [x] ABI3 PyO3 native wheel build for Python 3.11+
- [x] SceneGraph rectangle submission to the GPU renderer
- [x] Instanced filled-rectangle GPU pipeline
- [x] Single draw call for a batch of rectangle instances
- [x] Persistent wgpu renderer context per window
- [x] Surface/device/queue/pipeline reused across frames
- [x] Persistent GPU context survives resize/reconfiguration
- [x] Anti-aliased GPU rounded rectangles using `CornerRadius`
- [x] Per-corner radii carried through Python → Rust → WGSL
- [x] SDF/fwidth rounded-edge antialiasing
- [x] General shape / path rendering
- [x] Text rendering
- [x] Image rendering
- [x] Clipping and compositing
- [x] Robust DPI / HiDPI handling
- [x] Multi-monitor support
- [x] Display-aware 60 / 120 / 144+ Hz presentation
- [x] VSync / present-mode selection

### 0.2 gate

0.2 is complete when SwirUI can open a native window and render a visible GPU-backed scene containing shapes and text while handling resize and input correctly, with the milestone's renderer/runtime hardening complete enough to support the first real widgets.

The verified Windows integration gate exercises one real native session containing clipped rounded shapes, Unicode text, an image and a concave path while also checking exact client-area resize, persistent GPU-context reuse and routed native pointer/focus input.

Cross-platform native-window coverage now includes real Linux/X11 lifecycle/input verification under Xvfb and a direct macOS Cocoa/AppKit backend with real NSWindow lifecycle, normalized input and Retina logical-geometry verification. Linux/macOS GPU/wgpu presentation and Wayland remain separate future work and are not implied by the 0.2 native-window milestone.

## 0.3 Alpha — Visual Engine

- [x] Glass / frosted glass
- [x] Acrylic-like materials
- [x] Background blur
- [x] Glow and bloom
- [x] Dynamic shadows
- [x] Linear / radial / mesh gradients
- [ ] Reflections
- [x] Depth and perspective
- [x] Adaptive lighting
- [x] Parallax
- [ ] Color filters
- [x] Noise / grain
- [ ] Custom shader effects
- [ ] Effect caching
- [ ] Adaptive quality profiles: Performance / Balanced / Quality / Ultra / Cinematic

## 0.4 Alpha — Core Widgets

- [ ] Text / Label
- [ ] Button / IconButton
- [ ] Input / PasswordInput / TextArea
- [ ] Checkbox / RadioButton / Switch
- [ ] Slider / RangeSlider
- [ ] ProgressBar / ProgressRing
- [ ] Badge / Chip
- [ ] Tooltip
- [ ] Card / GlassCard
- [ ] Panel / Frame
- [ ] ScrollView
- [ ] Expander / Accordion
- [ ] SplitView
- [ ] Modal / Dialog
- [ ] Toast / Notification surface

## 0.5 Alpha — Layout Engine

- [ ] Row / Column
- [ ] Stack / Grid / Wrap
- [ ] Dock / Flow / Overlay
- [ ] Constraint layout
- [ ] Intrinsic sizing
- [ ] Min / max constraints
- [ ] Responsive breakpoints
- [ ] Adaptive navigation
- [ ] Dynamic typography
- [ ] Compact / desktop / ultrawide variants
- [ ] DPI-aware spacing
- [ ] Layout invalidation optimization

## 0.6 Alpha — Reactive Runtime

- [x] Basic thread-safe `State`
- [ ] Computed state
- [ ] Reactive properties
- [ ] Data binding
- [ ] Two-way binding
- [ ] Observable collections
- [ ] Dependency tracking
- [ ] Async state
- [ ] Persistent state
- [ ] Component lifecycle hooks
- [ ] Minimal-update scheduling
- [ ] Batched state transactions

## 0.7 Alpha — Animation Engine

- [ ] Fade / slide / scale / rotate
- [ ] Blur / glow transitions
- [ ] Morph / flip / reveal
- [ ] Spring / elastic / bounce
- [ ] Physics animations
- [ ] Page transitions
- [ ] Shared-element transitions
- [ ] Hover / press / focus animations
- [ ] Magnetic interactions
- [ ] Particle effects
- [ ] Frame-rate-independent timing
- [ ] Animation cancellation / chaining

## 0.8 Beta — Professional Widgets

- [ ] DataGrid / Table
- [ ] TreeView / ListView
- [ ] Virtualized collections
- [ ] Tabs
- [ ] Docking system
- [ ] Sidebar / NavigationRail
- [ ] Toolbar / Ribbon / MenuBar
- [ ] ContextMenu / CommandPalette
- [ ] PropertyGrid / Inspector
- [ ] Timeline
- [ ] Calendar / DatePicker / TimePicker
- [ ] ColorPicker
- [ ] FilePicker / FolderPicker

## Data Visualization

- [ ] Line / area / bar charts
- [ ] Pie / donut charts
- [ ] Scatter / heatmap / radar
- [ ] Gauge / candlestick / timeline charts
- [ ] Live and streaming data
- [ ] GPU chart rendering
- [ ] Interactive zoom and selection
- [ ] Large-dataset optimization

## Media Engine

- [ ] Image / SVG / GIF
- [ ] Lottie
- [ ] VideoPlayer
- [ ] AudioPlayer
- [ ] CameraView
- [ ] Microphone input
- [ ] Waveform
- [ ] Spectrum visualizer

## Advanced Application Components

- [ ] Terminal
- [ ] Code editor
- [ ] Syntax highlighting
- [ ] Autocomplete
- [ ] Minimap
- [ ] Markdown viewer
- [ ] PDF viewer
- [ ] WebView
- [ ] JSON / log / hex viewers
- [ ] File explorer
- [ ] Settings framework

## 2D / 3D

- [ ] Canvas2D
- [ ] Infinite canvas
- [ ] GPU drawing API
- [ ] 3D viewport
- [ ] Cameras / scenes / meshes
- [ ] Materials / lighting
- [ ] Model viewer
- [ ] Interactive 3D widgets

## Theme Engine

- [ ] Future Dark / Future Light
- [ ] Neon Blue / Neon Green
- [ ] Matrix / Cyberpunk
- [ ] Glass / Adaptive Glass
- [ ] OLED / Minimal / Professional
- [ ] Runtime theme switching
- [ ] System-theme synchronization
- [ ] Theme inheritance
- [ ] Custom theme packages
- [ ] Animated theme transitions
- [ ] Design tokens

## Desktop Integration

- [ ] Clipboard
- [ ] Drag & drop
- [ ] System tray
- [ ] Native notifications
- [ ] Global hotkeys
- [ ] File associations
- [ ] URL handlers
- [ ] Native dialogs
- [ ] Taskbar integration
- [ ] Multi-instance management

## Input & Accessibility

- [x] Window-level keyboard / mouse normalization on Windows
- [x] Scene-level pointer hit testing and hover transitions
- [x] Capture / target / bubble pointer routing
- [x] Event propagation cancellation
- [x] Keyboard focus routing
- [ ] Touch / gestures
- [ ] Pen / pressure
- [ ] Gamepad navigation
- [ ] Screen readers
- [x] Keyboard-only navigation
- [x] Focus management
- [ ] High contrast
- [ ] Reduced motion
- [ ] Font scaling
- [x] Semantic roles
- [ ] Accessibility inspector

## Internationalization

- [ ] System-language detection
- [ ] English fallback
- [ ] Runtime language switching
- [ ] RTL layouts
- [ ] Locale-aware dates / numbers / currencies
- [ ] Translation packages
- [ ] IME support

## Async & Performance

- [ ] `asyncio` integration
- [ ] Background tasks
- [ ] Worker threads
- [x] Thread-safe state updates
- [ ] Multiprocessing helpers
- [ ] Cancellation
- [ ] Progress reporting
- [x] Performance budgets
- [x] Frame-time telemetry

## Plugin System & Marketplace

- [ ] Plugin API
- [ ] Plugin discovery
- [ ] Widget plugins
- [ ] Theme plugins
- [ ] Renderer plugins
- [ ] Dependency resolution
- [ ] Security model
- [ ] SwirUI Marketplace

## SwirUI Studio

- [ ] Drag-and-drop editor
- [ ] Component tree
- [ ] Property inspector
- [ ] Theme editor
- [ ] Animation timeline
- [ ] Responsive preview
- [ ] Live preview
- [ ] Code preview
- [ ] Asset manager
- [ ] Python code generation
- [ ] Import existing SwirUI projects
- [ ] Round-trip editing
- [ ] Hot reload

## AI Builder

- [ ] Prompt-to-layout
- [ ] Prompt-to-component
- [ ] Prompt-to-theme
- [ ] Prompt-to-animation
- [ ] Responsive variant generation
- [ ] Accessibility suggestions
- [ ] Refactoring assistance
- [ ] Debugging assistance

AI output must remain ordinary, editable SwirUI code.

## Developer Tools

- [ ] SwirUI Inspector
- [ ] Component tree debugger
- [ ] Layout debugger
- [ ] State inspector
- [ ] Event inspector
- [ ] Animation inspector
- [ ] GPU profiler
- [ ] FPS / frame-time monitor
- [ ] Memory profiler
- [ ] Hot reload server

## Testing

- [x] Unit-test foundation
- [x] Headless native-window test backend
- [x] Linux real-X11 native-window smoke test
- [x] macOS real-Cocoa native-window + Retina logical-geometry smoke test
- [x] Windows real-native-window smoke test
- [x] Windows integrated 0.2 mixed-scene + exact-client + routed-input gate
- [x] Windows active-display / refresh-rate mapping smoke test
- [x] Windows `WM_DISPLAYCHANGE` / `WM_DPICHANGED` normalization smoke tests
- [x] Windows keyboard / system-key normalization smoke test
- [x] Windows real-wgpu surface/present smoke test
- [x] Windows real-wgpu instanced rectangle draw smoke test
- [x] Windows persistent GPU context multi-frame + resize smoke test
- [x] Windows per-corner rounded-rectangle shader smoke test
- [x] Windows shaped-text SceneGraph → Python → Rust/wgpu smoke test
- [x] Windows image-resource SceneGraph → Python → Rust/wgpu smoke test
- [x] Windows filled Path2D SceneGraph → Python → Rust/wgpu smoke test
- [x] Windows retained linear / radial / mesh gradient GPU smoke tests
- [x] Windows retained depth / perspective / parallax GPU smoke test
- [x] Windows retained adaptive-lighting / glow / bloom / noise GPU smoke test
- [x] Windows retained backdrop/background-blur + glass/acrylic GPU smoke test
- [x] Windows mixed-DPI logical-DIP → physical-GPU smoke test
- [x] Windows presentation-policy reconfiguration smoke test
- [x] Display-aware high-refresh runtime pacing tests
- [x] Rust native-core check and unit tests
- [x] ABI3 native extension build on Windows
- [x] Python 3.11–3.14 test matrix
- [x] Ruff quality gate
- [x] Mypy quality gate
- [x] SceneGraph hit-test and pointer-targeting tests
- [x] Routed component input propagation tests
- [ ] Widget interaction tests
- [ ] Screenshot tests
- [ ] Visual regression tests
- [x] Accessibility tests
- [x] Performance regression tests
- [ ] Automated UI testing

## SwirUI CLI

Planned commands:

```bash
swirui new MyApp
swirui dev
swirui run
swirui test
swirui benchmark
swirui build
swirui package
```

## Packaging

- [ ] Windows EXE
- [ ] Windows MSI
- [ ] Portable Windows build
- [ ] Linux AppImage
- [ ] Linux DEB / RPM
- [ ] macOS APP / DMG
- [ ] Android feasibility
- [ ] iOS feasibility
- [ ] Web / WASM feasibility

## Native Core

Python remains the public developer API while performance-critical systems migrate progressively to Rust.

Current native foundation:

- [x] Rust 2024 native crate
- [x] PyO3 bridge
- [x] Maturin native build project
- [x] wgpu 30 renderer foundation
- [x] Windows HWND + DisplayHandle surface bridge
- [x] hardware adapter with software fallback selection
- [x] ABI3 Python 3.11+ native wheel
- [x] Python SceneGraph → native wgpu rectangle bridge
- [x] instanced GPU rectangle pipeline
- [x] persistent renderer context per window
- [x] context reuse across multiple frames and resize
- [x] native per-corner rounded-rectangle pipeline
- [x] native renderer split into dedicated Rust module
- [x] GPU resource cache
- [x] native text pipeline
- [x] native image pipeline
- [x] native filled-path pipeline
- [x] native painter-order backdrop blur/compositor pipeline

Primary future candidates:

- GPU rendering
- scene preparation
- text and image processing
- layout acceleration
- animation scheduler
- GPU resource management
- platform integration

## Benchmarks

SwirUI publishes reproducible benchmark guardrails instead of unsupported performance claims. The current CI suite measures retained 1024-node SceneGraph traversal and pointer hit testing with median, p95 and worst-case latency budgets and stores a machine-readable JSON report artifact for each run.

Metrics planned for continued expansion include:

- startup time
- RAM
- CPU / GPU usage
- frame time
- input latency
- component creation
- large-list / DataGrid performance
- animation performance

Where technically comparable, benchmark targets may include Qt/PyQt/PySide, Tkinter/CustomTkinter, Flet, Kivy, Flutter desktop and Electron-based desktop applications.

## SwirUI Showcase

The official showcase will be a real application rather than a Hello World screen.

- [ ] animated dashboard
- [ ] glass sidebar
- [ ] live charts
- [ ] DataGrid
- [ ] terminal
- [ ] code editor
- [ ] media player
- [ ] 3D viewport
- [ ] settings
- [ ] notifications
- [ ] theme switching
- [ ] responsive layouts
- [ ] live performance monitor

---

## Release strategy

| Release | Goal |
| --- | --- |
| 0.1 Alpha | Foundation ✅ |
| 0.2 Alpha | Native window + first visible renderer ✅ |
| 0.3 Alpha | Visual Engine |
| 0.4 Alpha | Core widgets |
| 0.5 Alpha | Layout Engine |
| 0.6 Alpha | Reactive runtime |
| 0.7 Alpha | Animation Engine |
| 0.8 Beta | Professional widgets |
| 0.9 Beta | Integration, media, charts and developer tooling |
| 1.0 | First production-ready release |

### 1.0 gate

SwirUI 1.0 requires a stable public API, tested GPU renderer, complete core widgets, responsive layout, reactive state, animation, accessibility baseline, internationalization, packaging, documentation, automated tests, benchmark suite and real-world applications.
