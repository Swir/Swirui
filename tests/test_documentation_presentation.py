from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "ROADMAP.md"

# Catch old block-character meters and common bracketed ASCII meters without
# confusing Markdown headings, checklist boxes, tables or directory trees.
_LEGACY_METER = re.compile(
    r"(?:[█▓▒░■□]{4,}|\[(?:[#=█▓▒░■□]+-+|-+[#=█▓▒░■□]+|[#=█▓▒░■□]{6,})\])"
)


def test_readme_uses_v2_standard_and_one_project_progress_card() -> None:
    readme = README.read_text(encoding="utf-8")

    assert readme.startswith("<!-- SWIR-README-STANDARD:v2 -->")
    assert readme.count('src="assets/readme/progress-card.svg"') == 1
    assert 'src="assets/readme/progress-mini.svg"' not in readme
    assert "## 🔎 Search Keywords" in readme
    assert _LEGACY_METER.search(readme) is None


def test_roadmap_uses_one_mini_without_legacy_meter_or_duplicate_card() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert roadmap.count('src="assets/readme/progress-mini.svg"') == 1
    assert 'src="assets/readme/progress-card.svg"' not in roadmap
    assert _LEGACY_METER.search(roadmap) is None


def test_verified_runtime_status_is_recorded_without_changing_weighted_percentage() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    assert "**Overall completion: 68%**" in roadmap
    assert "**Status:** Complete ✅ — 12 / 12 groups verified" in roadmap
    assert "**Status:** Underway 🚧 — 2 / 12 groups verified" in roadmap
    assert "- [x] Frame-rate-independent timing" in roadmap
    assert "- [x] Animation cancellation / chaining" in roadmap
