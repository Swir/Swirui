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

### Changed
- The wgpu renderer now reports submitted rectangle and text counts independently.
- Text scene nodes use white as the renderer default when no explicit fill color is supplied, matching the temporary GDI preview behavior.
- Installed native cores that lack shaped-text support now fail explicitly instead of silently dropping text nodes.

## [0.1.0a1] - 2026-09-16

### Added
- SwirUI repository foundation.
- Initial README and development roadmap.

---

**SwirUI — by [Swir](https://github.com/Swir)**