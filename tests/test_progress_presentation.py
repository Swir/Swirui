import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASCII_PROGRESS = re.compile(r"\[[#-]{20}\]\s*\d+(?:\.\d+)?%")


def test_active_progress_docs_use_ascii_only() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert readme.count("<!-- SWIR-ASCII-PROGRESS:START -->") == 1
    assert readme.count("<!-- SWIR-ASCII-PROGRESS:END -->") == 1
    assert roadmap.count("<!-- SWIR-ROADMAP-ASCII-PROGRESS:START -->") == 1
    assert roadmap.count("<!-- SWIR-ROADMAP-ASCII-PROGRESS:END -->") == 1
    assert ASCII_PROGRESS.search(readme)
    assert ASCII_PROGRESS.search(roadmap)
    assert "assets/readme/progress-card.svg" not in readme
    assert "assets/readme/progress-mini.svg" not in readme
    assert "assets/readme/progress-card.svg" not in roadmap
    assert "assets/readme/progress-mini.svg" not in roadmap


def test_completed_animation_status_stays_synchronized_with_verified_roadmap() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "0.7 Alpha Animation Engine are complete; 0.7 has 12 / 12 groups verified" in readme
    assert "**Status:** Complete ✅ — 12 / 12 groups verified" in roadmap
    assert "- [x] Page transitions" in roadmap
    assert "- [x] Shared-element transitions" in roadmap
    assert "- [x] Morph / flip / reveal" in roadmap
    assert "- [x] Fade / slide / scale / rotate" in roadmap
