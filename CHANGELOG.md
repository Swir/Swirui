# Changelog

All notable changes to SwirUI will be documented in this file.

The project uses semantic versioning where practical during pre-alpha development. Breaking API changes may occur before 1.0.

## [Unreleased]

### Added
- Initial project architecture and package metadata.
- Public project roadmap with real progress tracking.
- Python 3.11–3.14 development target.
- Foundation for application, window, component, event and reactive state systems.
- Initial automated test and CI direction.
- Persistent native shaped-text subsystem using glyphon/cosmic-text inside the Rust/wgpu renderer.
- SceneGraph text submission through the Python `WgpuRenderer` bridge into the persistent native GPU context.
- Windows GPU text smoke coverage including Unicode shaping, repeated frames and resize.
- `examples/gpu_text_demo.py` showing rounded rectangles and shaped text in one native GPU scene.
- Persistent RGBA8 image resources backed by cached native wgpu textures, texture views and bind groups.
- SceneGraph `IMAGE` submission through the Python resource registry into the native Rust/wgpu image pipeline.
- Native image sampling with reusable linear sampler, alpha blending and per-node opacity.
- Windows GPU image smoke coverage including resource upload, repeated mixed rectangle/text/image frames, resize and resource removal.
- `examples/gpu_image_demo.py` with a dependency-free procedural image uploaded once and reused by the persistent GPU context.
- Content-addressed GPU image caching that deduplicates byte-identical RGBA payloads across logical resource ids while preserving reference-safe lifetime, alias rebinding and transactional multi-context rollback.
- GPU image-cache telemetry for logical resources, unique native resources, aliases, retained bytes, cache hits and actual native uploads.
- Backend-neutral `Path2D` filled-polygon geometry with deterministic convex/concave ear-clipping tessellation and geometry-accurate hit testing.
- `SceneNodeKind.PATH` submission through Python into a persistent clipped/alpha-blended Rust/wgpu triangle pipeline with reusable GPU buffers.
- `examples/gpu_paths_demo.py` plus real Windows Path2D smoke coverage across persistent frames and resize.
- Hierarchical `SceneNode.clip_to_bounds` clipping with retained cumulative clip propagation through nested scene groups.
- Clip-aware GPU paths for all current primitive kinds: rectangle shader clipping, filled-path clipping, glyphon `TextBounds` clipping and image-quad cropping with UV remapping.
- Cumulative ancestor opacity propagation for rectangles, paths, shaped text and images, with fully transparent subtree pruning before GPU resource preparation.
- Clip-aware SceneGraph hit testing so descendants outside a clipping ancestor cannot receive pointer hits.
- Rectangle intersection geometry used by retained-scene clipping and renderer culling.
- Windows mixed-scene GPU smoke coverage for clipped rounded rectangles, shaped text and images across repeated frames and resize.
- Win32 display enumeration, per-window scale reporting and normalized `WM_DPICHANGED` events as groundwork for full DPI/HiDPI and multi-monitor support.
- Active-display refresh-rate discovery through Win32/GDI with per-window monitor mapping.
- Normalized Win32 display-transition events from window movement, display configuration changes and DPI transitions.
- Per-window display metadata containing virtual-desktop geometry, work area, UI scale, primary-display state and active refresh rate.
- Monitor-aware frame pacing that caps each native window to `min(AppConfig.target_fps, active_display_refresh_rate)` and retargets automatically when the window changes displays.
- Frame telemetry exposing configured target FPS, effective per-window target FPS and active display refresh rate.
- Deterministic 60 Hz → 144 Hz monitor-transition pacing coverage plus real Win32 refresh-rate/display mapping smoke tests.
- `examples/high_refresh_demo.py` now demonstrates live display-aware pacing and reports monitor scale, refresh rate and effective target FPS while moving between monitors.
- Focusable component contract with per-window logical keyboard focus.
- Capture → target → bubble routing for focused `key_down`, `key_up` and `text_input` events with propagation cancellation.
- Deterministic forward/reverse focus traversal across enabled, visible, focusable components.
- Automatic Tab / Shift+Tab keyboard focus traversal with hidden/disabled ancestor pruning and stale-focus healing.
- `Event.prevent_default()` for cancelling framework default actions without stopping capture/target/bubble propagation.
- Backend-neutral Shift/Ctrl/Alt/Meta keyboard modifier metadata carried by `PlatformEvent`.
- Real Win32 keyboard and system-key normalization smoke coverage.
- Pointer-down focus handoff from a hit-tested SceneNode to the matching focusable Component.
- Focus lifecycle events (`focus_gained`, `focus_lost`, `component_focus_changed`) and automatic focus clearing when the root is replaced or the window closes.
- Automated focus-routing coverage for Unicode text input, propagation cancellation, traversal, pointer focus handoff and invalid focus targets.
- Backend-neutral `AccessibilityRole` semantics covering common controls and content roles.
- Immutable accessibility-tree snapshots with accessible names/descriptions plus enabled, focusable and focused state.
- Hidden-subtree pruning and semantic-tree lookup tests as the contract for future native accessibility adapters.
- Runtime `App.set_target_fps()` retargeting for all current and future window frame schedulers.
- Cross-window `App.seconds_until_next_frame()` deadline reporting and frame events that expose the active target FPS and frame interval.
- Automated high-refresh pacing coverage for runtime 60 → 120/144 Hz retargeting and sub-poll-interval frame deadlines.
- End-to-end logical-DIP window geometry with explicit logical ↔ physical conversion helpers and physical-pixel renderer surfaces.
- Per-monitor DPI scaling for GPU rectangles, paths, per-corner radii, shaped text, images and clip rectangles before Python → Rust/wgpu submission.
- Native physical pointer and resize input normalization back into logical DIPs before SceneGraph hit testing and routed component input.
- Deterministic 150% → 200% scale-transition coverage plus a real Win32/wgpu mixed-DPI smoke test that verifies rectangles, Unicode text, images, input coordinates and persistent surface reconfiguration.
- Dependency-free retained-runtime benchmark helpers with median, p95, worst-case, throughput and explicit latency-budget evaluation.
- CI performance guardrails for 1024-node retained SceneGraph traversal, pointer hit-testing and deterministic reflection tessellation workloads.
- Machine-readable JSON performance reports uploaded from CI for regression inspection.
- Direct Linux/X11 native-window backend using Python `ctypes` and the system libX11 client library, with normalized resize, focus, pointer, keyboard, text-input and window-close events.
- Real X11 native-window smoke coverage on Python 3.14 under Xvfb, including create, map, title, resize, event polling, hide and destroy lifecycle checks.
- Direct macOS Cocoa/AppKit native-window backend using Python `ctypes` and the Objective-C runtime, without requiring PyObjC.
- CoreGraphics display discovery plus per-window Cocoa screen mapping, backing scale and refresh-rate reporting.
- Normalized Cocoa pointer, keyboard, text-input, focus, resize and close events with framework-compatible Tab and modifier-key metadata.
- Retina-safe physical-pixel ↔ Cocoa-point conversion at the native boundary, including live backing-scale and display-transition events.
- Real macOS Cocoa native-window smoke coverage on Python 3.14, including App-level verification that logical SwirUI geometry remains stable on scaled displays.
- Immutable multi-stop `LinearGradient` and `RadialGradient` primitives that compile into clipped retained `Path2D` geometry and reuse the verified native Rust/wgpu shape pipeline.
- Immutable rectangular `MeshGradient` color lattices with clamped bilinear sampling and deterministic retained quad tessellation.
- GPU gradient demos for linear, radial and mesh gradients, plus real Win32/wgpu smoke coverage for each gradient family.
- Retained `DropShadow` effects using normalized Gaussian-like rounded-rectangle layers that reuse the existing persistent native wgpu rectangle batch, HiDPI scaling and alpha compositing.
- `examples/gpu_shadows_demo.py` plus a dedicated real Win32/wgpu shadow smoke gate.
- Retained `Glow` and elevation-aware `DynamicShadow` effects with configurable light direction/altitude and deterministic Gaussian-like layer generation.
- Visual-quality-aware retained effect budgets for `Performance`, `Balanced`, `Quality`, `Ultra`, `Cinematic` and `Auto` profiles without changing effect geometry, colors or extents.
- `examples/gpu_dynamic_effects_demo.py` for live quality-aware glow and dynamic-shadow animation on a persistent GPU context.
- Retained source-driven `Bloom` that splits one quality-aware layer budget into normalized wide-spill and tight-core light bands while reusing the persistent HiDPI-aware wgpu rectangle batch.
- `examples/gpu_bloom_demo.py` plus real Win32/wgpu bloom smoke coverage across persistent frames alongside dynamic shadows and glow.
- Persistent sampleable offscreen scene targets in the native Win32/wgpu renderer, with one reusable fullscreen blitter for final swapchain presentation.
- Native offscreen-target lifecycle telemetry and real Win32/wgpu smoke coverage proving reuse across frames, recreation on physical resize and no redundant same-size reallocation.
- Persistent two-pass separable Gaussian GPU blur with retained ping/output render targets and pipeline state that survive ordinary frames and are recreated only on real physical resize.
- DPI-aware `WgpuRenderer(scene_blur_radius=...)` and `set_scene_blur_radius()` APIs that keep the public blur radius in logical DIPs while executing post-processing in physical GPU pixels.
- `examples/gpu_scene_blur_demo.py` plus real Win32/wgpu smoke coverage for blur enable/disable, repeated-frame reuse and resize lifecycle.
- Retained painter-order `BackdropBlur` regions that split the SceneGraph into ordered segments, blur only already-painted background content and preserve later foreground content sharply above the material boundary.
- Persistent native wgpu backdrop blur/compositor resources with rounded region masks, logical-DIP → physical-pixel conversion and reuse across repeated frames.
- Public retained `FrostedGlass` and `Acrylic` material primitives composed from the verified backdrop path plus HiDPI-aware tint, border and luminosity layers.
- Deterministic acrylic micro-grain with visual-quality-aware retained density, bounded cost and no per-frame random generation or image uploads.
- `examples/gpu_backdrop_blur_demo.py` and `examples/gpu_glass_materials_demo.py`, plus real Win32/wgpu smoke coverage proving backdrop/material rendering across the same persistent GPU context.
- Public retained `Noise` / grain effect with deterministic seeded geometry, quality-aware sample budgets and shared grain sampling used by acrylic materials.
- Public retained `AdaptiveLighting` effect with elevation-, direction- and altitude-aware shadow/highlight lobes, deterministic quality scaling and non-interactive retained composition.
- `examples/gpu_noise_demo.py` and `examples/gpu_adaptive_lighting_demo.py`, plus real Win32/wgpu smoke coverage proving noise and changing directional lighting render across the same persistent native GPU context.
- Public retained `PerspectivePlane` projection with bounded logical-DIP X/Y rotation, camera distance, depth translation and normalized transform origin.
- Public pointer-driven `Parallax` mapping that clamps viewport input and compiles directly into the existing clipped, HiDPI-aware retained `Path2D` GPU pipeline.
- `examples/gpu_depth_demo.py` plus real Win32/wgpu smoke coverage proving changing perspective/parallax geometry renders across the same persistent native GPU context.
- Public quality-aware retained `Reflection` effect with normalized specular bands compiled into clipped, non-interactive linear-gradient/path geometry.
- `examples/gpu_reflections_demo.py` plus deterministic reflection tessellation performance coverage and real Win32/wgpu persistent-context smoke coverage.
- Immutable, composable `ColorFilter` transforms for affine RGBA post-processing, including brightness, contrast, saturation, grayscale, sepia, invert, opacity and hue rotation.
- Persistent native Rust/wgpu color-filter post-processing with reusable output texture, pipeline, bind group and uniform state after scene/backdrop blur composition.
- `examples/gpu_color_filters_demo.py` plus real Win32/wgpu color-filter smoke coverage across repeated frames and persistent context reuse.
- Public `AdaptiveQualityController` resolving `VisualQuality.AUTO` into concrete Performance/Balanced/Quality/Ultra/Cinematic profiles from smoothed cadence and measured renderer cost.
- Hysteresis, fast sustained-pressure demotion, conservative sustained-headroom promotion and cooldown protection for stable automatic quality without idle-window false positives.
- Runtime `App.set_visual_quality()`, `effective_visual_quality`, quality diagnostics and `visual_quality_changed` events without native-window recreation.
- Frame telemetry for renderer duration, frame-budget utilization and configured/effective visual quality, plus `examples/adaptive_quality_demo.py` and focused pressure/headroom/idle regression tests.
- Native retained effect-frame caching for unchanged backdrop/material scenes, keyed by stable prepared-scene generation tokens and renderer background while reusing each window's persistent offscreen wgpu target.
- Native effect-cache hit/miss telemetry, explicit invalidation/reset hooks, deterministic Python token/invalidation coverage, `examples/gpu_native_effect_frame_cache_demo.py` and a real Win32/wgpu cache-hit smoke gate.
- Retained Text/Label and Button/IconButton controls compiled from Python components into SceneGraph geometry and shaped GPU text with routed pointer/keyboard focus interaction.
- Retained Input, PasswordInput and TextArea controls with native text-input routing, password masking, focus/caret behavior and accessibility semantics.
- Retained Checkbox, RadioButton and Switch controls with pointer/keyboard interaction, checked semantics and real Win32/wgpu smoke coverage.
- Retained Slider and RangeSlider controls with pointer dragging, keyboard adjustment, bounded stepping, focus visuals and numeric accessibility value/range semantics.
- Retained ProgressBar and path-based ProgressRing controls with determinate value/range semantics and deterministic GPU geometry.
- `examples/core_widgets_demo.py`, `examples/core_toggles_demo.py` and `examples/range_progress_demo.py`, plus expanded real Win32 widget interaction coverage inside the persistent wgpu context.
- Retained `ScrollView` with content-local child coordinates, clamped logical-DIP offsets, automatic content measurement, keyboard scrolling and accessibility value semantics.
- `examples/core_scroll_view_demo.py` plus real Win32/wgpu coverage for clipped translated content, routed child interaction and persistent renderer-context reuse.
- Retained `Expander` and `Accordion` controls with managed disclosure content, pointer/keyboard interaction, expanded/collapsed accessibility state, exclusive or multi-open coordination and optional require-one behavior.
- `examples/expander_accordion_demo.py` plus real Win32/wgpu smoke coverage that switches accordion sections through native input while preserving the persistent renderer context.

### Changed
- The wgpu renderer now reports submitted rectangle, path, text and image counts independently.
- Registered image resources are uploaded automatically into newly created native window contexts and can be replaced or removed at runtime.
- Byte-identical image resources registered under different logical ids now share one native GPU texture allocation.
- Text scene nodes use white as the renderer default when no explicit fill color is supplied, matching the temporary GDI preview behavior.
- Installed native cores that lack shaped-text or image-resource support now fail explicitly instead of silently dropping scene nodes.
- Rounded-rectangle instances now carry clip bounds through Python → Rust → WGSL while the legacy 12-float direct native rectangle interface remains accepted for compatibility.
- Image vertices are cropped before draw submission so clipping preserves the correct source UV region instead of stretching the visible portion.
- Win32 smoke tests use process-unique native window classes to avoid stale process-wide WNDPROC callbacks when multiple backend instances are exercised in one pytest process.
- Win32 now normalizes both ordinary `WM_KEYDOWN` / `WM_KEYUP` and system `WM_SYSKEYDOWN` / `WM_SYSKEYUP` messages through the same framework keyboard-event path.
- Native event-loop idle sleeps now shorten to the nearest pending frame deadline instead of quantizing 120/144+ Hz targets to a fixed 4 ms polling cadence.
- `AppConfig.target_fps` is now an application ceiling for native windows rather than an unconditional per-window target; headless rendering keeps the configured value unchanged.
- `DisplayInfo` keeps its existing positional field ordering while adding refresh-rate metadata at the end of the public dataclass contract.
- Public `Window` and SceneGraph geometry now stays in logical DIPs while Win32 and renderer backends operate on physical client pixels.
- Adjacent Win32 resize/DPI transitions are normalized so resize pixels are interpreted with the incoming monitor scale rather than the previous scale.
- The temporary GDI preview renderer now follows the same logical-DIP → physical-pixel scaling contract as the native wgpu renderer.
- CI now has a dedicated retained-runtime performance job in addition to the Python quality/test matrix, Rust checks and Windows native smoke gate.
- Linux platform selection now chooses the direct X11 backend when `DISPLAY` is available while retaining the deterministic headless backend for Linux servers and CI sessions without a display.
- macOS platform selection now chooses the direct Cocoa backend, and CI has a dedicated real-Cocoa Python 3.14 native-window gate alongside Linux X11 and Windows/wgpu gates.
- Gradient stop interpolation and visual argument validation are shared across linear/radial gradient implementations, while mesh gradients preserve stable SceneGraph hit keys across generated cells.
- Decorative SceneGraph nodes can opt out of direct pointer hit testing without disabling independently interactive descendants, so visual overflow such as shadows cannot steal input from nearby controls.
- Native Win32/wgpu scene rendering now targets the persistent offscreen texture first and presents through a final fullscreen blit, establishing a real post-processing boundary for the 0.3 Visual Engine.
- Final Win32/wgpu presentation can now select the retained separable-blur output without reallocating the blur pipeline or render targets on every frame.
- Backdrop boundaries now reuse the persistent offscreen scene target and blur pipeline in painter order, and material decoration uses reserved negative z-indices so default-z child content remains sharp, visible and interactive above frosted/acrylic layers.
- Native color filters run after scene/backdrop blur so one composable affine transform applies consistently to the final rendered scene without rebuilding retained geometry.
- `VisualQuality.AUTO` now changes quality only when both cadence and measured renderer cost indicate sustained pressure/headroom; fixed profiles remain fixed and direct config changes synchronize at frame boundaries.
- Unchanged backdrop/material scenes now skip primitive preparation/submission and backdrop blur/composition after the first successful frame; final scene blur and color filters remain live postprocess stages on every presentation.

## [0.1.0a1] - 2026-09-16

### Added
- SwirUI repository foundation.
- Initial README and development roadmap.

---

**SwirUI — by [Swir](https://github.com/Swir)**