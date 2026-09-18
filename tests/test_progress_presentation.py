import re
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LEGACY_PROGRESS_METER = re.compile(r"\[[█▓▒░#=\-\s]+\]\s*\d+(?:\.\d+)?%")


def test_active_progress_docs_use_svg_without_legacy_character_meter() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "assets/readme/progress-card.svg" in readme
    assert "assets/readme/progress-mini.svg" in roadmap
    assert LEGACY_PROGRESS_METER.search(readme) is None
    assert LEGACY_PROGRESS_METER.search(roadmap) is None


def test_generated_progress_svgs_are_valid_and_match_completed_layout_scope() -> None:
    card_path = ROOT / "assets" / "readme" / "progress-card.svg"
    mini_path = ROOT / "assets" / "readme" / "progress-mini.svg"

    card = ET.parse(card_path).getroot()
    mini = ET.parse(mini_path).getroot()
    assert card.attrib["viewBox"] == "0 0 1200 180"
    assert mini.attrib["viewBox"] == "0 0 900 72"

    card_text = card_path.read_text(encoding="utf-8")
    mini_text = mini_path.read_text(encoding="utf-8")
    for text in (card_text, mini_text):
        assert "68.0%" in text
        assert "COMPLETE" in text
        assert "12 / 12 layout groups verified" in text

    assert 'data-role="progress-fill" x="50" y="116" width="748"' in card_text
    assert 'data-role="progress-fill" x="170" y="42" width="476"' in mini_text
