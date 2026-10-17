# Windows desktop beta: 0.1.0b1

The beta is a usable, deliberately bounded desktop release, separate from the
full roadmap. Canonical roadmap completion remains 68%. See the
[release page](https://github.com/Swir/Swirui/releases/tag/v0.1.0b1) for publication
status, installation files and the actual qualification run.

On supported Windows/Python, install with
`python -m pip install --only-binary=:all: swirui==0.1.0b1`, then run
`python -m swirui doctor` and `python -m swirui demo`.

## Supported scope

- Windows x64, 64-bit CPython 3.11–3.14, and a working wgpu-compatible graphics
  adapter/driver. The ABI3 wheel contains both Python API and native core.
- Retained core and professional widgets, layouts, reactive state, animation,
  keyboard/mouse editing, text clipboard, and Windows GPU materials/effects.
- Runtime/inherited themes, nine presets, custom JSON theme packages, Windows
  appearance synchronization, and decorative perspective surfaces.
- An installed-package demo (`python -m swirui demo`) and read-only installation
  diagnostics (`python -m swirui doctor`, optionally `--json`). No checkout or
  compiler is required to run the Windows wheel.

## Boundaries

Linux/X11 and macOS/Cocoa window backends have native smoke coverage, but their
GPU presentation and Wayland are not part of this desktop beta. The portable
wheel is intended for Python models/tooling and tests on those systems.

Perspective layers are decoration; a general 3D viewport, models, interactive
3D widgets, full visual Studio, WebView and PdfViewer are outside beta scope.
Markdown implementation exists, while its roadmap closeout remains tracked by
PR #189. OS screen-reader integration, IME, touch/pen and full internationalization
are unfinished; beta adoption must account for those limitations. Some advanced
media widgets still use explicit styling rather than complete theme inheritance.
API changes may occur during beta. No universal FPS or hardware guarantee is made.

## Qualification

The release workflow must pass Ruff, mypy and pytest on Python 3.11–3.14,
Windows Rust tests, and the full installed native-wheel suite. A separate empty
environment installs only that wheel, then runs diagnostics and a real native
gallery smoke test from outside the source checkout. Portable/native wheels and
sdist must contain identical Python sources and pass metadata checks.

PR checks qualify a candidate without publishing it. Publication requires a new
matching release tag and the existing PyPI Trusted Publisher. Published files
are never overwritten. Actual CI run links and publication status belong in the
release notes; this checklist alone is not evidence of a successful run.

For a bug report, include the version, `python -m swirui doctor --json`, a minimal
program, reproduction steps and the graphics error if applicable. Diagnostics
load the extension but do not claim a rendered frame; `demo --smoke-test` checks
the latter explicitly.
