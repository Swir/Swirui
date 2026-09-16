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
- Persistent native RGBA8 image resource cache with wgpu texture upload, filtering sampler and alpha-blended textured-quad rendering.
- `ImageResource` plus `WgpuRenderer.register_image*()` / `unregister_image()` APIs for stable application-facing resource IDs.
- SceneGraph `IMAGE` submission through Python into the persistent Rust/wgpu renderer with resource replay for newly created window contexts.
- Windows GPU image smoke coverage including repeated frames, resize, resource removal and full SceneGraph integration alongside shaped text and rounded rectangles.
- `examples/gpu_images_demo.py` demonstrating dependency-free generated RGBA pixels reused by multiple native GPU image nodes.

### Changed
- The wgpu renderer now reports submitted rectangle, text and image counts independently.
- Text scene nodes use white as the renderer default when no explicit fill color is supplied, matching the temporary GDI preview behavior.
- Installed native cores that lack shaped-text or image support now fail explicitly instead of silently dropping those scene nodes.
- Image pixels are uploaded when a resource is registered and reused from the persistent native GPU cache across rendered frames.

## [0.1.0a1] - 2026-09-16

### Added
- SwirUI repository foundation.
- Initial README and development roadmap.

---

**SwirUI — by [Swir](https://github.com/Swir)**