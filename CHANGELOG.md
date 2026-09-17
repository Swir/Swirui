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
- CI performance guardrails for 1024-node retained SceneGraph traversal and pointer hit-testing workloads.
- Machine-readable JSON performance reports uploaded from CI for regression inspection.

### Changed
- The wgpu renderer now reports submitted rectangle, path, text and image counts independently.
- Registered image resources are uploaded automatically into newly created native window contexts and can be replaced or removed at runtime.
- Byte-identical image resources registered under different logical ids now share one native GPU texture allocation.
- Text scene nodes use white as the renderer default when no explicit fill color is supplied, matching the temporary GDI preview behavior.
- Installed native cores that lack shaped-text or image-resource support now fail explicitly instead of silently dropping scene nodes.
- Rounded-rectangle instances now carry clip bounds through Python → Rust → WGSL while the legacy 12-float direct native rectangle interface remains accepted for compatibility.
- Image vertices are cropped before draw submission so clipping preserves the correct source UV region instead of stretching the visible portion.
- Win32 smoke tests use process-unique native window classes to avoid stale process-wide WNDPROC callbacks when multiple backend instances are exercised in one pytest process.
- Native event-loop idle sleeps now shorten to the nearest pending frame deadline instead of quantizing 120/144+ Hz targets to a fixed 4 ms polling cadence.
- `AppConfig.target_fps` is now an application ceiling for native windows rather than an unconditional per-window target; headless rendering keeps the configured value unchanged.
- `DisplayInfo` keeps its existing positional field ordering while adding refresh-rate metadata at the end of the public dataclass contract.
- Public `Window` and SceneGraph geometry now stays in logical DIPs while Win32 and renderer backends operate on physical client pixels.
- Adjacent Win32 resize/DPI transitions are normalized so resize pixels are interpreted with the incoming monitor scale rather than the previous scale.
- The temporary GDI preview renderer now follows the same logical-DIP → physical-pixel scaling contract as the native wgpu renderer.
- CI now has a dedicated retained-runtime performance job in addition to the Python quality/test matrix, Rust checks and Windows native smoke gate.

## [0.1.0a1] - 2026-09-16

### Added
- SwirUI repository foundation.
- Initial README and development roadmap.

---

**SwirUI — by [Swir](https://github.com/Swir)**
