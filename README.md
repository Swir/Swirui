<!-- SWIR-README-STANDARD:v2 -->

<div align="center">

<img src="https://raw.githubusercontent.com/Swir/Swirui/v0.1.0b1/assets/readme/hero.svg" width="100%" alt="SwirUI — native reactive GPU-first Python desktop UI framework">

# ⚡ SwirUI

### Native, reactive and GPU-first desktop UI framework for Python

**Python public API • Rust + wgpu native core • High-refresh desktop rendering**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-02050A?style=for-the-badge&logo=python&logoColor=62E5FF)
![Rust](https://img.shields.io/badge/Rust-Native%20Core-02050A?style=for-the-badge&logo=rust&logoColor=62E5FF)
![wgpu](https://img.shields.io/badge/wgpu-30.0.1-02050A?style=for-the-badge&logo=webgpu&logoColor=62E5FF)
![Windows](https://img.shields.io/badge/Windows-Win32%20GPU-02050A?style=for-the-badge&logo=windows11&logoColor=62E5FF)

[![CI](https://img.shields.io/github/actions/workflow/status/Swir/Swirui/ci.yml?branch=main&style=flat-square&label=CI&color=0088FF)](https://github.com/Swir/Swirui/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-Windows%20desktop%20beta-0088FF?style=flat-square)
[![PyPI](https://img.shields.io/pypi/v/swirui?include_prereleases&style=flat-square)](https://pypi.org/project/swirui/)
![Progress](https://img.shields.io/badge/project%20progress-68%25-0088FF?style=flat-square)

</div>

<img width="100%" src="https://raw.githubusercontent.com/Swir/Swir/main/assets/power-divider-v4.svg" alt="SWIR electric divider" />

## Project Status

<!-- SWIR-PYPI-PROGRESS:START -->
```text
SwirUI      [####################----------] 68.0%
Scope       12 / 12 layout groups verified
```
<!-- SWIR-PYPI-PROGRESS:END -->

> PyPI-safe text progress is the portable status view. The SVG below is an optional GitHub visual.

<img width="100%" src="https://raw.githubusercontent.com/Swir/Swirui/v0.1.0b1/assets/readme/progress-card.svg" alt="SwirUI project progress: 68.0% — 0.5 Alpha Layout Engine complete; 12 of 12 layout groups verified">

**68% authoritative weighted project progress — 0.8 Beta Professional Widgets is complete at 13 / 13 groups; Media Engine is complete at 8 / 8 groups verified.**

- `0.1 Alpha — Foundation` ✅
- `0.2 Alpha — Native Window + First Renderer` ✅
- `0.3 Alpha — Visual Engine` ✅
- `0.4 Alpha — Core Widgets` ✅
- `0.5 Alpha — Layout Engine` ✅
- `0.6 Alpha — Reactive Runtime` ✅
- `0.7 Alpha — Animation Engine` ✅ `12 / 12`
- `0.8 Beta — Professional Widgets` ✅ `13 / 13`
- `Media Engine` ✅ `8 / 8`

The published 68% value preserves the verified weighting documented in `ROADMAP.md` through completed 0.5. Completed later milestone functionality is tracked by its canonical checklist until an explicit project-weighting extension is documented; later work is never double-counted or used to invent project progress.

**0.1.0b1 is the Windows desktop beta**, for building your own Python programs
with SwirUI controls, materials and custom themes. See the
[release page](https://github.com/Swir/Swirui/releases/tag/v0.1.0b1) for publication
status and qualification evidence.
Beta scope and release readiness are separate from full roadmap completion;
public APIs may still change before 1.0.

## Overview

SwirUI is being built as a complete Python desktop application framework rather than a visual skin over Tkinter, Qt or another widget toolkit. Python stays the public developer API while Rust, wgpu and PyO3 own performance-critical native rendering work.

The Windows renderer uses a persistent per-window wgpu context and retained SceneGraph. Linux/X11 and macOS/Cocoa already provide real native window and input backends. GPU presentation on Linux/macOS and Wayland support remain future work and are not claimed as complete.

The completed 0.5 layout layer provides content-aware intrinsic measurement, min/max constraints, responsive compact/desktop/ultrawide policies, adaptive navigation, dynamic typography, DPI-stable logical spacing and revision-aware layout caching. The completed 0.6 runtime adds computed state, async/persistent state, dynamic dependency tracking, batched transactions, reactive properties, bindings, observable collections, retained component lifecycle hooks and transaction-scoped minimal-update scheduling. The completed 0.7 animation layer adds elapsed-time tweens, analytical spring motion, inertial decay, serial/parallel composition, cancellation/chaining, hover/press/focus animation, blur/glow transitions, magnetic and particle effects, retained page/shared-element transitions, fade/slide/scale/rotate transforms, retained reveal/flip/morph transitions and window-scoped frame driving.

## Highlights

| Area | Current verified capability |
|---|---|
| Native windows | Direct Win32, X11 and Cocoa/AppKit backends without Tkinter, Qt or SDL |
| GPU renderer | Persistent Rust/wgpu renderer context on Windows with retained scene submission |
| Shapes | Anti-aliased rounded rectangles plus convex/concave `Path2D` geometry |
| Text | Persistent shaped Unicode text through glyphon/cosmic-text, including arbitrary-affine retained presentation through cached native rasters |
| Images | Content-addressed RGBA GPU cache with aliases, telemetry and safe lifetime management |
| Composition | Hierarchical clipping, cumulative opacity, exact affine convex clipping and painter-order retained composition |
| HiDPI | Logical-DIP public geometry with physical-pixel native/GPU conversion |
| Displays | Multi-monitor mapping, refresh discovery and 60/120/144+ Hz display-aware pacing |
| Visual Engine | Gradients, shadows, glow, bloom, depth, parallax, reflections and adaptive lighting |
| Materials | Native backdrop blur, `FrostedGlass` and `Acrylic` with deterministic grain |
| Post-processing | Persistent scene blur, affine RGBA color filters and validated custom WGSL effects |
| Custom shaders | Bounded Python `CustomShaderEffect` API, native Naga validation, persistent GPU pass and bounded pipeline reuse |
| Core widgets | Retained Text/Label, Button/IconButton, text inputs, toggles, Slider/RangeSlider, progress, surfaces, ScrollView, Accordion, SplitView, Modal/Dialog and Toast/Notification |
| Layout engine | Row/Column, Stack/Grid/Wrap, DockPanel/Flow/Overlay, ConstraintLayout, intrinsic sizing, min/max constraints and optimized retained reflow |
| Responsive UI | Logical-DIP breakpoints, compact/desktop/ultrawide variants, adaptive navigation and `DynamicTypography` |
| Reactive runtime | `State`, `ComputedState`, `AsyncState`, `PersistentState`, dependency tracking, transactions, bindings, observable collections and retained lifecycle hooks |
| Animation runtime | Elapsed-time `Tween`, analytical spring/decay, serial/parallel composition, interaction/effect/particle helpers, page/shared-element transitions, fade/slide/scale/rotate and retained reveal/flip/morph transitions |
| Performance | Adaptive visual-quality profiles plus retained effect/GPU caches and layout-preparation revision caching |
| Accessibility | Semantic roles/tree, keyboard focus routing, keyboard-only traversal, checked state, numeric value/range and dialog/alert semantics |

## Quick Start

### Windows desktop beta — 0.1.0b1

This beta targets **Windows x64 with 64-bit CPython 3.11–3.14**. Its native wheel
includes the Rust/wgpu core, so users do not need Rust or a repository checkout.
Install the pinned beta from PyPI in a fresh environment:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --only-binary=:all: swirui==0.1.0b1
.venv\Scripts\python -m swirui doctor
.venv\Scripts\python -m swirui demo
```

The packaged gallery lets you switch dark/light appearance, glass/acrylic/solid
materials and perspective layers while preserving your edits. It resizes down
to an 800 × 600 logical client area. `python -m swirui demo --smoke-test` opens,
renders and closes the gallery, reporting the actual adapter/backend.

The explicit version selects this prerelease. On supported Windows/Python,
pip selects the native ABI3 wheel automatically. A compatible graphics driver
is still required; `doctor` checks installation and `demo --smoke-test` checks rendering.
The portable wheel supports Python models and tooling; it does not provide
equivalent GPU desktop rendering on Linux/macOS. See the
[beta scope and limitations](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/beta.md) before adopting this prerelease.

### Your first program

Save this as `my_app.py` and run `.venv\Scripts\python my_app.py`.
Your application owns its behavior; the controls inherit SwirUI's visual theme.

```python
from swirui import NEON_BLUE, App, Button, Input, Label, Panel, Window, mount
from swirui.rendering import Rect, WgpuRenderer

app = App("My first SwirUI app", renderer=WgpuRenderer())
window = Window(title="Made with SwirUI", width=640, height=400,
                min_width=640, min_height=400)
root = Panel(bounds=Rect(0, 0, 640, 400), theme=NEON_BLUE)
name = Input(bounds=Rect(32, 88, 320, 44), placeholder="Your name")
message = Label("Your idea. Your Python. Your style.", bounds=Rect(32, 32, 560, 32))
button = Button("Say hello", bounds=Rect(32, 156, 180, 44))
button.on("click", lambda _: setattr(message, "text", f"Hello, {name.value or 'world'}!"))
root.add(message, name, button)
window.on("resized", lambda _: setattr(root, "bounds", Rect(0, 0, window.width, window.height)))
mount(window, root)
app.add_window(window)
try:
    app.run()
finally:
    app.stop()
```

Choose another built-in preset, replace palette/font tokens, or distribute your
own JSON theme package. For glass, acrylic and decorative depth, see
[custom material themes](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/custom-material-themes.md).
These perspective layers are visual decoration, not a general-purpose 3D viewport.

### Customize the visual system

Core controls accept an explicit, immutable `Theme`. Share one theme across a
window or use independent themes for different windows. Semantic swatches keep
surfaces, text, focus rings and button states consistent; explicit widget color,
font and radius arguments still take precedence.

```python
from dataclasses import replace
from swirui import Button, ButtonVariant, Input, Palette, Theme
from swirui.rendering import Rect

theme = Theme(palette=replace(Palette(), accent="#82DEED"))
save = Button("Save changes", bounds=Rect(24, 80, 180, 44),
              theme=theme, variant=ButtonVariant.PRIMARY)
name = Input(bounds=Rect(24, 24, 280, 44), placeholder="Project name", theme=theme)
```

Supported controls include buttons, text inputs, labels, checkboxes, radio
buttons, switches, sliders, panels/cards, progress indicators, badges/chips,
tooltips, expanders, split panes, dialogs and notifications. Components inherit the nearest
ancestor theme unless they set their own `theme`. Assigning `None` restores
inheritance; `effective_theme` reports the resolved value. Explicit color, font
and radius overrides continue to win. Unthemed trees retain their legacy defaults.

```python
from swirui import FUTURE_DARK, FUTURE_LIGHT, Button, Panel
from swirui.rendering import Rect

root = Panel(bounds=Rect(0, 0, 600, 400), theme=FUTURE_DARK)
root.add(Button("Save", bounds=Rect(24, 24, 160, 44)))
root.theme = FUTURE_LIGHT
```

Runtime changes update the same controls in a single retained transaction;
text, selection, focus, values and editor undo history remain intact. Children
added or moved later resolve their new scope automatically. Custom components
can override `on_theme_changed(previous, current)`; widget subclasses should
call `super().on_theme_changed(...)` to retain built-in style bindings.
Custom appearances can be shared as versioned JSON `ThemePackage` files with
multiple variants, complete palettes and tokens. Load with `ThemePackage.load(path)`
and assign `root.theme = package.default` or `package.themes["day"]`. The
[theme-package guide](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/theme-packages.md) covers authoring, validation and
atomic saves. Try Aurora with
`python examples/workbench_gallery.py --theme-package examples/themes/aurora.swirui-theme.json`.
`ThemeController(window)` follows the Windows application color preference and
supports explicit system/light/dark choices, custom theme pairs and an explicit
fallback on unsupported backends. It preserves local scopes and editing state;
see [system appearance](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/system-appearance.md) and run
`python examples/appearance_gallery.py` for a native preview.
Connect an `AnimationController` to opt into appearance transitions. Nine built-in
presets include Neon Blue, Neon Green, Matrix, Cyberpunk, OLED, Minimal and
Professional alongside Future Dark/Light. Try `python examples/theme_gallery.py`;
see [presets and motion](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/theme-presets.md) for reduced motion and interpolation
behavior. Linux/macOS synchronization remains unimplemented. Direct theme assignment
continues to apply immediately.

### Build your own appearance

Your application can define its own palette, typography, materials and depth.
`SurfaceStyle` adds glass/acrylic, shadow, accent glow and decorative perspective
layers; `ThemeSurface` inherits them while its child controls remain editable.

```python
from dataclasses import replace
from swirui import NEON_BLUE, SurfaceStyle, ThemePackage, ThemeSurface
from swirui.rendering import Rect

my_theme = replace(
    NEON_BLUE,
    palette=replace(NEON_BLUE.palette, accent="#85F5E3"),
    surface_style=SurfaceStyle(
        kind="glass", blur_radius=28, elevation=14,
        glow_radius=20, depth_layers=3, tilt_y=-12,
    ),
)
surface = ThemeSurface(bounds=Rect(40, 40, 420, 260), theme=my_theme)
ThemePackage("My appearance", {"main": my_theme}, "main").save("my-theme.json")
```

Try `python examples/custom_theme_gallery.py` or load
[Ocean Studio](examples/themes/ocean-studio.swirui-theme.json).
The [custom-material guide](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/custom-material-themes.md) covers local overrides,
portable sharing and rendering limits. Perspective layers provide a dimensional
UI treatment; a full 3D model viewport remains on the roadmap.

### Release preparation

The [release workflow](.github/workflows/publish-pypi.yml) qualifies candidate
packages and publishes only for a matching GitHub Release after its checks pass.
It validates versions, tests the installed Windows native wheel, checks identical
Python sources across distributions and uses PyPI Trusted Publishing.
See [release instructions](https://github.com/Swir/Swirui/blob/v0.1.0b1/docs/releasing.md). These local candidate changes are
not yet published; they do not constitute a stable release or new remote CI evidence.

Notification colors use `accent`, `success`, `warning` and `error` palette roles.
An unauthored `GlassCard` material follows the inherited surface, border and
radius tokens; supplying or assigning a `FrostedGlass` material preserves that
explicit material across theme changes. Transparent scroll containers propagate
their scope without adding an opaque background. Advanced professional and media
widgets are not all theme-aware yet. `NavigationRail`/`Sidebar`, `Tabs`,
`ListView`/`TreeView` and the public layered `DataGrid` now follow runtime palettes,
fonts and radius tokens, with bounded keyboard-focus outlines. Theme changes
preserve active pages, hidden-page content, expansion, multi-selection, filters,
sorting, scrolling and cell-edit buffers. Explicit style overrides retain priority.
Tab headers handle arrows/Home/End only while the header owns keyboard focus;
page controls and nested tabs keep their own navigation keys.
`Toolbar`, `MenuBar`, `Ribbon`, `ContextMenu` and `CommandPalette` also inherit
runtime colors, fonts and radii, with focus outlines. Keyboard navigation reveals
overflow commands within bounded scene viewports; palette `max_visible_rows`
limits the result viewport, not searchable/navigable results. Only visible rows
(including partially clipped boundary rows) are compiled. Query text retains spaces
during typing, while matching uses case-insensitive words. Command navigation
respects child focus and prevented defaults. Popups reserve a separate shortcut
column, and short command strips place shortcuts beside labels.
Context menus and palettes support fractional wheel/trackpad motion, scrollbar
track clicks and captured thumb dragging. `scroll_by(delta)` and `scroll_offset`
use logical pixels. Scrolling preserves the active command; keyboard navigation
reveals it again. Unconsumed wheel motion can bubble to enclosing scroll surfaces.
The palette reuses the `Input` editing model: Left/Right, Shift selection,
Backspace/Delete, Ctrl+A/C/X/V, `caret_index`, `selected_text` and `select()` work
on the query. Home/End retain result navigation; Ctrl+Home/End moves to query
boundaries and Shift+Home/End extends selection. Clipboard failures emit
`clipboard_error` without losing selected text. Pasted line breaks/tabs become
word separators. Theme changes preserve query, caret, selection and scroll position.

After building and installing the native wheel from this checkout, run
`python examples/swirui_studio.py` for the native visual playground. Switch
between Future Dark and Future Light, change accent, card title, corner radius
and glass depth, or replay the finite animation.
`python examples/core_gallery.py` opens an interactive core-control gallery:
adjust progress, select a chip, collapse text input, resize a split pane, explore
status colors, focus a tooltip and open a dialog while switching modes. Both
examples are demonstrations, not the planned visual application editor.
Once keyboard focus enters a `Modal`/`Dialog`, Tab and Shift+Tab wrap through
available content instead of reaching controls behind it. The application still
chooses initial focus when opening and restores focus when dismissing; the gallery
demonstrates both steps. Controls that consume Tab themselves retain that behavior.
Pointer coordinates inside modal content follow its dialog-local coordinate space,
including nested dialogs and pointer capture; the original logical window event
remains available as `event.data["window_event"]` on routed pointer events.
`python examples/workspace_gallery.py` demonstrates the professional controls with
a filterable/editable sample portfolio, 2,000 virtualized assets, a retained file
tree and synchronized sidebar/tab navigation. Ctrl+K opens a modal command palette
with page navigation, theme switching and asset bookmarks; Enter invokes and
Escape closes, restoring focus to the command launcher. Sample data stays local in memory.
This interactive showcase is not the future visual application editor.

`python examples/text_editing_gallery.py` opens Compose, an editable notes/code
showcase with an idea-completion popup and live light/dark appearance switching.
`CodeEditor` inherits its gutter, current-line, minimap and syntax colors; partial
`syntax_colors` overrides remain fixed while other token colors follow the theme.
Selected code uses the input foreground so syntax colors do not reduce selection
contrast. `Theme(monospace_family="Consolas")` changes editor typography independently
of the normal `font_family`; an explicit editor font still takes precedence.
`Autocomplete` inherits popup surfaces, selection colors, font and radius without
re-running its provider or changing its query, selected suggestion or input selection.

`python examples/picker_gallery.py` opens Details, a synchronized calendar/date/time
and color-picker showcase. All four controls inherit palettes, fonts, radius and
keyboard-focus styling. Explicit `font_family` values remain fixed across theme changes.
ColorPicker values, HSV channels and HEX are encoded sRGB; preview and track shapes
convert to the renderer's linear RGB, preserving alpha. Checkerboards show transparency,
and dragging a channel continues outside the control until release or loss of capture.

`python examples/workbench_gallery.py` combines a docked code editor, notes, inspector
and local command console. PropertyGrid/Inspector and DockWorkspace inherit normal
fonts and palettes; Terminal uses `monospace_family`. Theme switches retain unfinished
property edits, pane contents, command drafts and history. Terminal scrollback stores
ANSI foreground identities so old output can adapt to light/dark surfaces. Its 16
supported foreground codes can be overridden with `ansi_colors={31: Color(...)}`;
these colors use encoded sRGB, like text. DockWorkspace itself accepts Left/Right
and Home/End to activate panes when it has keyboard focus. The example interprets
only `help`, `status` and `clear` in Python and never executes shell commands.

The current native core preserves painter order between interleaved primitive
types in ordinary scenes, including glass boundaries. Older native wheels and
affine-transform scenes use the established renderer path. The diagnostic
native context's `read_scene_rgba()` returns the offscreen RGBA scene before final
whole-frame post-processing; it is not a desktop screenshot API.

### Text editing geometry (this checkout)

With the current native wgpu core, `Input`, `PasswordInput` and command queries
use the renderer's font discovery and cosmic-text shaping for caret positions,
selection spans and pointer placement. Long lines scroll in pixels inside a
content clip; the complete string is preserved so scrolling does not reshape
kerning or ligatures. Geometry is measured at the current physical font size
and converted back to logical coordinates. Password geometry receives only
mask characters. A control retains only its latest layout; color-only theme
changes and moving the caret do not trigger another shaping pass.

`TextArea` and `CodeEditor` also use shaped per-line carets, selection and clicks.
Each logical line stays intact inside the content clip; long lines scroll
horizontally to the caret instead of wrapping independently of editing geometry.
Up/Down and code-editor PageUp/PageDown preserve the desired visual column
across short lines. The multiline cache is bounded to 128 entries and 65,536
source characters, while document line indexing is reused until the value changes.
There is no soft-wrap editing mode yet.

The current native core accepts `SceneNode.text_spans` as ordered, disjoint
`(start, end, Color)` ranges using Python character indexes. Code highlighting
colors complete shaped lines instead of drawing additional copies of tokens;
GPU text, cached affine rasterization and effect copies preserve these colors.
At most 4096 spans per scene node and 512 visible editor spans per frame are used.
Older cores retain legacy editor overlays and reject explicitly supplied rich
text nodes. Run `python examples/text_editing_gallery.py` for editable notes and code.

Headless, portable and older native cores retain deterministic estimated widths.
This is not complete IME,
grapheme-aware keyboard navigation or bidirectional cursor-affinity support.
The native single-line geometry API bounds each request to 1 MiB of UTF-8,
a 1024-byte font-family name and a physical font size of at most 16384 pixels.

### Text clipboard (this checkout)

On Windows, `Input`, `PasswordInput`, `TextArea`, `Autocomplete` and `CodeEditor`
handle Ctrl+C, Ctrl+X and Ctrl+V through the owning window. Copy and cut are
disabled for password fields. Read-only controls permit copy, and a failed cut
leaves the text and selection intact. Paste respects maximum length, preserves
multiline indentation and participates in the code editor's undo history.

Applications can call `window.get_clipboard_text()` and
`window.set_clipboard_text(text)` directly. A missing native provider or a busy
clipboard raises `ClipboardError`; control shortcuts report a `clipboard_error`
event with `operation` and `error` instead of interrupting the UI loop.

For headless tests, supply `Window(clipboard=MemoryClipboard())` with
`MemoryClipboard` imported from `swirui`. This explicitly uses isolated memory,
not the system clipboard. Native Linux/macOS providers, non-text formats and
terminal selection exchange remain unimplemented. The opt-in Windows clipboard
test uses `SWIRUI_TEST_CLIPBOARD=1` and replaces clipboard contents with known
test text; it does not inspect previous clipboard contents.

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

Try the retained widgets, layout engine, reactive runtime and animation foundation:

```powershell
python examples/core_widgets_demo.py
python examples/layout_row_column_demo.py
python examples/layout_advanced_demo.py
python examples/responsive_layout_demo.py
python examples/adaptive_navigation_demo.py
python examples/dynamic_typography_demo.py
python examples/reactive_runtime_demo.py
python examples/async_persistent_state_demo.py
python examples/component_lifecycle_demo.py
python examples/animation_timing_demo.py
python examples/physics_animation_demo.py
python examples/page_transition_demo.py
python examples/shared_element_transition_demo.py
python examples/transform_animation_demo.py
python examples/advanced_transform_animation_demo.py
python examples/rotate_transition_demo.py
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

Try the custom-shader runtime after building the native extension:

```powershell
python examples/gpu_custom_shader_demo.py
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

### Foundation API

```python
from swirui import App, AppConfig, Component, State, Window

counter = State(0)
app = App(name="SwirUI Demo", config=AppConfig(target_fps=120))
window = Window(title="Future starts here", width=1100, height=720)
root = Component("dashboard")
window.set_root(root)
app.add_window(window)
counter.subscribe(lambda value: print("Counter:", value))
counter.set(1)
app.run()
```

### Reactive runtime

```python
from swirui import State, computed, state_transaction

price = State(12.0)
quantity = State(2)
discount = State(0.0)
subtotal = computed(lambda: price.value * quantity.value)
total = computed(lambda: subtotal.value * (1.0 - discount.value))

total.subscribe(lambda value: print(f"Total: {value:.2f}"), immediate=True)
with state_transaction():
    price.set(15.0)
    quantity.set(3)
    discount.set(0.10)
```

Computed dependencies are discovered from reads performed by the computation. Nested transactions coalesce notifications and dependency-ordered computed recomputation at the outer boundary. `bind()` and `bind_bidirectional()` return disposable binding handles, observable collections publish immutable/defensive snapshots, `AsyncState` models asynchronous loading/error/value transitions and `PersistentState` provides schema-versioned atomic JSON persistence.

### Animation timing and physics

```python
from swirui import AnimationParallel, SpringAnimation, State, Tween, ease_in_out_cubic

position = State(0.0)
opacity = State(0.0)
intro = AnimationParallel(
    SpringAnimation(0.0, 320.0, position.set, stiffness=180.0, damping=22.0),
    Tween(0.0, 1.0, 0.35, opacity.set, easing=ease_in_out_cubic),
).start()

intro.advance(1.0 / 120.0)
```

Animation primitives consume elapsed seconds rather than frame counts. Spring and inertial-decay sampling use closed-form equations, so samples at the same elapsed time remain deterministic across different frame partitions. Completion, cancellation, serial chaining and parallel composition preserve unused frame time where applicable. Page, shared-element and retained transform transitions use the same frame clock while applying visual-only retained-scene movement/scaling/rotation, so authored layout geometry remains stable.

### Retained layout example

```python
from swirui import Button, CrossAxisAlignment, Insets, Row, Window, mount
from swirui.rendering import Rect

window = Window(title="Layout", width=720, height=360)
row = Row(
    bounds=Rect(0, 0, 1, 1),
    fill_viewport=True,
    padding=Insets.symmetric(horizontal=32, vertical=120),
    spacing=16,
    cross_alignment=CrossAxisAlignment.STRETCH,
)
row.add(
    Button("Primary", bounds=Rect(0, 0, 160, 48)).set_layout_grow(1),
    Button("Secondary", bounds=Rect(0, 0, 160, 48)).set_layout_grow(2),
)
mount(window, row)
```

Layout geometry remains in logical DIPs. The retained layout pass runs before child SceneGraph compilation, so arranged bounds are used by rendering and hit testing without recreating the native GPU context.

### Bounded custom WGSL effect

```python
from swirui.rendering import CustomShaderEffect, WgpuRenderer

source = """
fn swirui_effect(
    color: vec4<f32>,
    uv: vec2<f32>,
    params: vec4<f32>,
) -> vec4<f32> {
    let gain = 1.0 + params.x;
    return vec4<f32>(color.rgb * gain, color.a);
}
"""

effect = CustomShaderEffect(source, parameters=(0.15, 0.0, 0.0, 0.0))
renderer = WgpuRenderer(custom_shader=effect)
```

## GPU and Runtime Examples

```text
examples/reactive_runtime_demo.py
examples/async_persistent_state_demo.py
examples/component_lifecycle_demo.py
examples/animation_timing_demo.py
examples/physics_animation_demo.py
examples/page_transition_demo.py
examples/shared_element_transition_demo.py
examples/transform_animation_demo.py
examples/advanced_transform_animation_demo.py
examples/rotate_transition_demo.py
examples/core_widgets_demo.py
examples/core_toggles_demo.py
examples/range_progress_demo.py
examples/core_surfaces_demo.py
examples/core_scroll_view_demo.py
examples/expander_accordion_demo.py
examples/core_split_view_demo.py
examples/core_overlays_demo.py
examples/layout_row_column_demo.py
examples/layout_panels_demo.py
examples/layout_advanced_demo.py
examples/responsive_layout_demo.py
examples/adaptive_navigation_demo.py
examples/dynamic_typography_demo.py
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
examples/gpu_custom_shader_demo.py
examples/gpu_native_effect_frame_cache_demo.py
examples/adaptive_quality_demo.py
examples/high_refresh_demo.py
```

## Technology & Architecture

```text
Python Application API
        │
        ├── App / Window / Component / State / ComputedState
        ├── retained widgets + complete 0.5 layout API
        ├── responsive layout / adaptive navigation / dynamic typography
        ├── async/persistent state + bindings / observable collections
        ├── retained lifecycle + minimal-update scheduling
        ├── elapsed-time animation + retained page/shared-element/transform/rotate transitions
        ├── routed input + accessibility semantics
        └── runtime configuration + adaptive visual quality
        │
SwirUI Runtime
        │
        ├── reactive dependency tracking + batched transactions
        ├── intrinsic measure → arrange + min/max constraints
        ├── animation sequencing / parallel composition / frame controller
        ├── compact / desktop / ultrawide logical-DIP policies
        ├── revision-aware retained layout invalidation cache
        ├── Win32 / X11 / Cocoa native backends
        ├── logical DIP ↔ physical pixel boundary
        ├── retained RenderTree / SceneGraph
        └── display-aware frame scheduler
        │
Renderer Layer
        │
        ├── persistent Windows wgpu context
        ├── rectangles / paths / shaped text / images
        ├── exact affine geometry/image clipping + cached affine shaped-text rasters
        ├── blur / backdrop / glass / acrylic
        ├── gradients / depth / lighting / bloom / color filters
        ├── validated custom WGSL post-processing
        └── retained GPU/effect/pipeline caches
        │
Native Core
        │
        └── Rust 2024 + wgpu 30 + PyO3 ABI3
```

## Testing & Quality

Every significant runtime change is expected to preserve the existing quality gates:

- Ruff and strict Mypy
- pytest on Python 3.11–3.14
- deterministic weighted progress-SVG verification against `ROADMAP.md`
- retained-runtime performance budgets with JSON reports
- `cargo check` and `cargo test`
- Maturin / PyO3 native build
- real Linux/X11 and macOS/Cocoa native-window smoke tests
- real Win32 + wgpu smoke tests
- integrated 0.2 native renderer/runtime gate
- HiDPI, multi-monitor, presentation-policy, text, image, path, effects and cache coverage
- retained widget interaction, accessibility and real Win32 input/rendering coverage
- intrinsic measurement, responsive reflow, adaptive navigation, dynamic typography and DPI-aware spacing coverage
- reactive-runtime tests for dependencies, batching, computed chains, bindings, observable collections, async/persistent state, lifecycle and minimal-update scheduling
- animation tests for frame-partition-independent timing, analytical spring/decay, cancellation, serial/parallel composition, page/shared-element transitions and retained reveal/flip/morph/rotate transforms
- real Win32 + wgpu retained transition coverage with persistent per-window context reuse, including arbitrary-affine shaped text
- real custom-WGSL validation and persistent-runtime smoke coverage

SwirUI does not claim performance superiority over other frameworks without reproducible measurements.

## Roadmap

The authoritative plan and its single roadmap progress graphic are in **[ROADMAP.md](https://github.com/Swir/Swirui/blob/v0.1.0b1/ROADMAP.md)**.

**0.8 Beta — Professional Widgets is complete at 13 / 13 groups, and Media Engine is complete at 8 / 8 groups verified.** The Media Engine credit includes the merged Image/SVG/GIF, Lottie, VideoPlayer, AudioPlayer, CameraView, Microphone input, Waveform and Spectrum visualizer qualification chains. The project-wide weighted percentage intentionally remains 68% until the documented weighting model is explicitly extended. The named 0.8 roadmap milestone and the separately scoped `0.1.0b1` Windows desktop beta do not imply completion of the full roadmap. Markdown closeout remains tracked separately in PR #189.

## Releases

**SwirUI v0.1.0b1** is the Windows desktop beta. Each release is built and tested by GitHub Actions before PyPI Trusted Publishing. The payload contains a Windows x64 ABI3 native wheel, a portable Python wheel and a source archive. The release notes record actual qualification and publication results.

- PyPI: **[swirui 0.1.0b1](https://pypi.org/project/swirui/0.1.0b1/)**
- GitHub prerelease: **[v0.1.0b1](https://github.com/Swir/Swirui/releases/tag/v0.1.0b1)**
- Development history: **[CHANGELOG.md](https://github.com/Swir/Swirui/blob/v0.1.0b1/CHANGELOG.md)**
- Full roadmap: **[ROADMAP.md](https://github.com/Swir/Swirui/blob/v0.1.0b1/ROADMAP.md)**
- CI status: **[GitHub Actions](https://github.com/Swir/Swirui/actions)**

## Repository Structure

```text
Swirui/
├── .github/workflows/      # Python, Rust and native-platform CI
├── assets/                 # SwirUI icon, README artwork and generated progress SVGs
├── benchmarks/             # reproducible performance budgets
├── docs/                   # architecture documentation
├── examples/               # native/runtime/GPU examples
├── native/                 # Rust + wgpu + PyO3 core
├── src/swirui/             # public Python framework and renderer bridge
├── tests/                  # automated unit/integration/native smoke tests
├── tools/                  # deterministic repository maintenance generators/checks
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
└── pyproject.toml
```

## 🔎 Search Keywords

`python desktop gui` • `python gpu ui` • `native python ui framework` • `python reactive ui` • `python async state` • `python persistent state` • `python animation framework` • `python spring animation` • `python physics animation` • `python retained widgets` • `python layout engine` • `python responsive layout` • `wgpu python renderer` • `rust pyo3 gui` • `win32 python gui` • `high refresh rate ui` • `hidpi desktop ui` • `gpu text rendering` • `custom wgsl effects` • `multi monitor python ui`

<img width="100%" src="https://raw.githubusercontent.com/Swir/Swir/main/assets/power-divider-v4.svg" alt="SWIR electric divider" />

<div align="center">

<img src="https://raw.githubusercontent.com/Swir/Swirui/v0.1.0b1/assets/swirui-icon.svg" width="76" alt="SwirUI icon">

### `BUILD • TEST • RENDER • EVOLVE`

⭐ **If SwirUI is useful or interesting, consider leaving a star.**

[**← SWIR profile**](https://github.com/Swir) · [**All projects →**](https://github.com/Swir?tab=repositories)

</div>
