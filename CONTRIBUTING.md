# Contributing to SwirUI

Thanks for helping build SwirUI.

SwirUI is currently pre-alpha. Contributions should prioritize clear architecture, tests and maintainability over adding large amounts of unverified surface area.

## Development setup

```bash
git clone https://github.com/Swir/Swirui.git
cd Swirui
python -m venv .venv
```

Activate the virtual environment and install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the quality checks:

```bash
ruff check .
mypy src/swirui
pytest
```

## Contribution guidelines

- Keep the public API small and intentional.
- Add tests for behavior changes.
- Keep renderer-specific code out of core component/state modules.
- Do not introduce a platform dependency into the headless core unless there is a strong architectural reason.
- Prefer measurable performance improvements over speculative micro-optimizations.
- Document breaking public API changes in `CHANGELOG.md`.
- Keep README and ROADMAP progress accurate; do not increase the percentage for unfinished prototypes.
- Preserve Python 3.11–3.14 compatibility unless a documented project decision changes the support window.

## Commit style

Conventional-style prefixes are encouraged:

```text
feat: ...
fix: ...
test: ...
docs: ...
refactor: ...
perf: ...
ci: ...
build: ...
```

## Pull requests

A pull request should describe what changed, why the change belongs in SwirUI, how it was tested and any performance or compatibility impact.

## Architecture changes

Changes that affect the renderer boundary, platform abstraction, reactive runtime, component lifecycle or public API should include a short architecture rationale in the pull request.

---

**SwirUI — by [Swir](https://github.com/Swir)**
