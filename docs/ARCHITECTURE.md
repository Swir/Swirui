# SwirUI Architecture

SwirUI is intentionally split into layers so the public Python API is not coupled to a particular renderer, operating system or native implementation.

## Design rules

1. **Python stays the public developer API.** Native code is an implementation detail.
2. **Rendering and platform integration are separate.** A Windows backend must not define widget behavior, and widgets must not know which GPU API draws them.
3. **State and events are framework primitives.** Widgets, animation and tooling should reuse the same contracts.
4. **Headless operation is supported.** Core behavior must be testable without a display server or GPU.
5. **Performance claims require measurement.** Optimization follows profiling and reproducible benchmarks.
6. **Accessibility and internationalization are architectural concerns, not post-1.0 patches.**

## Layer model

```text
Application code
      │
Public Python API
      │
Component / State / Event runtime
      │
Layout + Widget + Animation systems
      │
Render tree / Scene graph
      │
Renderer abstraction ───── Platform abstraction
      │                           │
GPU/native renderer          OS integration
      └──────────────┬────────────┘
                 Native core
```

## Current 0.1 foundation

### `App`
Owns the application lifecycle and top-level windows. The first implementation deliberately does not block in a native event loop. The API contract is established before a platform backend owns that loop.

### `Window`
Represents framework-level window state: title, dimensions, visibility, lifecycle and the root component. Native handles do not belong in this class.

### `Component`
Forms the retained component tree. It supports deterministic traversal, parent ownership, reparenting and cycle prevention.

### `EventEmitter`
Provides a small framework-wide event contract with explicit unsubscribe support and propagation stopping.

### `State[T]`
Provides a thread-safe observable value. This is only the first reactive primitive; computed values, dependency tracking, batched updates and render scheduling are later milestones.

### `Renderer`
A protocol representing frame rendering. `NullRenderer` keeps tests independent from future GPU dependencies.

### `PlatformBackend`
A protocol representing native operating-system integration. `NullPlatformBackend` provides a headless implementation for tests and tooling.

## Planned native core

Rust is the preferred direction for performance-critical implementation because it can provide memory safety and native performance while exposing a controlled Python bridge. The exact graphics stack will be selected after prototype benchmarks rather than locked in prematurely.

Likely native responsibilities include:

- GPU device/surface management
- scene graph processing
- text and image pipelines
- effect/shader pipelines
- layout acceleration
- animation scheduling
- native window and input integration
- resource caching

## Render pipeline direction

```text
Reactive state update
        ↓
Component invalidation
        ↓
Layout pass (only where needed)
        ↓
Render-tree update
        ↓
Scene preparation / batching
        ↓
GPU command generation
        ↓
Present frame
```

The architecture should avoid rebuilding the entire interface for a small state change.

## Quality profiles

The renderer will eventually expose adaptive quality profiles:

- Performance
- Balanced
- Quality
- Ultra
- Cinematic

Profiles may alter blur kernels, shadow quality, sampling, particle density and other expensive visual effects without requiring application code changes.

## Cross-platform policy

Windows, Linux and macOS are primary desktop targets. Platform-specific capabilities are exposed through capability detection rather than assuming every OS supports identical behavior.

## API stability

Before 1.0, APIs may change as renderer and widget prototypes reveal better contracts. Breaking changes must be recorded in `CHANGELOG.md`. Public APIs should become progressively more stable approaching beta.

---

**SwirUI — by [Swir](https://github.com/Swir)**
