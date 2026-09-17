# SwirUI Native Core

This directory contains SwirUI's performance-critical native rendering core.

Python remains the public developer API. Rust owns the work that benefits from predictable performance, persistent GPU resources and direct graphics access; PyO3 is the bridge between both layers.

## Current stack

- Rust 2024 edition
- `wgpu` 30.x for GPU access and presentation
- PyO3 0.29.x with an ABI3 Python 3.11+ baseline
- glyphon + cosmic-text for shaped GPU text
- Win32 raw-window-handle surface integration for the currently verified native GPU path

## Current architecture

The Windows GPU renderer now keeps one persistent wgpu context per native window instead of recreating graphics state every frame. Each context owns and reuses:

- `wgpu::Instance`, `Surface`, `Device` and `Queue`
- swapchain configuration and presentation policy
- rounded-rectangle, filled-path, image and shaped-text pipelines
- reusable primitive buffers and glyph/image resources
- a persistent sampleable offscreen scene target
- one reusable final fullscreen texture blitter

Scene geometry is authored through the public Python API in logical DIPs. The Python renderer converts it to physical pixels using the current per-monitor scale before submission through PyO3. The native renderer then draws rectangles, tessellated paths/gradients, cached RGBA images and shaped text into the offscreen scene texture and performs the final offscreen-to-swapchain presentation pass.

The offscreen target survives ordinary frames and is recreated only when the physical surface size actually changes. This creates the render boundary required for the 0.3 Visual Engine's upcoming blur, glass/acrylic, bloom and custom post-processing passes without claiming those effects as complete yet.

## Verification

CI keeps the native path behind real gates rather than architecture-only checks:

- `cargo check --all-targets`
- `cargo test --lib`
- Maturin release-wheel build on Windows with Python 3.14
- real Win32 window + wgpu presentation smoke tests
- mixed rectangle/path/text/image scenes across repeated frames and resize
- shaped text, image cache, clipping, gradients, retained shadows, mixed-DPI and presentation-policy smoke tests
- persistent offscreen-target lifecycle checks, including no redundant reallocation on repeated same-size resize

The Python package is tested on Python 3.11, 3.12, 3.13 and 3.14. Linux/X11 and macOS/Cocoa already have native window/input backends, while their wgpu presentation paths remain future work and are not claimed as complete.

## Current native focus

The active 0.3 work is the post-processing layer built on top of the persistent offscreen scene target. The next high-impact renderer steps are separable GPU blur, region-aware background blur, glass/acrylic composition and bloom while preserving the existing persistent-resource, HiDPI and high-refresh guarantees.
