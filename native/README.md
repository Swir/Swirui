# SwirUI Native Core

This directory contains the native performance layer for SwirUI.

The public developer API stays in Python. The native core is responsible for work that benefits
from predictable performance and direct GPU/platform access.

## Current stack

- Rust 2024 edition
- `wgpu` 30.x for cross-platform GPU access
- PyO3 0.29.x for the Python bridge
- CPython ABI3 baseline: Python 3.11+

## Current milestone

The native crate currently exposes its version and the graphics backends compiled into `wgpu`.
The next native steps are:

1. Create and own a real GPU instance/device/queue.
2. Accept a native window handle from the Python runtime.
3. Create a `wgpu::Surface` and configure the swapchain.
4. Upload scene primitives into GPU buffers.
5. Render the first rectangle and rounded rectangle.
6. Add text atlas/rendering support.
7. Replace the temporary Win32 GDI preview renderer.

The GDI preview backend exists only to validate visible scene submission while the wgpu path is
being connected. It is not part of the long-term rendering architecture.
