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
- Hierarchical `SceneNode.clip_to_bounds` clipping with retained cumulative clip propagation through nested scene groups.
- Clip-aware GPU paths for all current primitive kinds: per-instance rectangle shader clipping, glyphon `TextBounds` clipping and image-quad cropping with UV remapping.
- Cumulative ancestor opacity propagation for rectangles, shaped text and images, with fully transparent subtree pruning before GPU resource preparation.
- Clip-aware SceneGraph hit testing so descendants outside a clipping ancestor cannot receive pointer hits.
- Rectangle intersection geometry used by retained-scene clipping and renderer culling.
- Windows mixed-scene GPU smoke coverage for clipped rounded rectangles, shaped text and images across repeated frames and resize.
- Win32 display enumeration, per-window scale reporting and normalized `WM_DPICHANGED` events as groundwork for full DPI/HiDPI and multi-monitor support.
- Focusable component contract with per-window logical keyboard focus.
- Capture → target → bubble routing for focused `key_down`, `key_up` and `text_input` events with propagation cancellation.
- Deterministic forward/reverse focus traversal across enabled, visible, focusable components.
- Pointer-down focus handoff from a hit-tested SceneNode to the matching focusable Component.
- Focus lifecycle events (`focus_gained`, `focus_lost`, `component_focus_changed`) and automatic focus clearing when the root is replaced or the window closes.
- Automated focus-routing coverage for Unicode text input, propagation cancellation, traversal, pointer focus handoff and invalid focus targets.
- Runtime `App.set_target_fps()` retargeting for all current and future window frame schedulers.
- Cross-window `App.seconds_until_next_frame()` deadline reporting and frame events that expose the active target FPS and frame interval.
- Automated high-refresh pacing coverage for runtime 60 → 120/144 Hz retargeting and sub-poll-interval frame deadlines.

### Changed
- The wgpu renderer now reports submitted rectangle, text and image counts independently.
- Registered image resources are uploaded automatically into newly created native window contexts and can be replaced or removed at runtime.
- Text scene nodes use white as the renderer default when no explicit fill color is supplied, matching the temporary GDI preview behavior.
- Installed native cores that lack shaped-text or image-resource support now fail explicitly instead of silently dropping scene nodes.
- Rounded-rectangle instances now carry clip bounds through Python → Rust → WGSL while the legacy 12-float direct native rectangle interface remains accepted for compatibility.
- Image vertices are cropped before draw submission so clipping preserves the correct source UV region instead of stretching the visible portion.
- Win32 smoke tests use process-unique native window classes to avoid stale process-wide WNDPROC callbacks when multiple backend instances are exercised in one pytest process.
- Native event-loop idle sleeps now shorten to the nearest pending frame deadline instead of quantizing 120/144+ Hz targets to a fixed 4 ms polling cadence.

## [0.1.0a1] - 2026-09-16

### Added
- SwirUI repository foundation.
- Initial README and development roadmap.

---

**SwirUI — by [Swir](https://github.com/Swir)**