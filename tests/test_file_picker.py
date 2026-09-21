from __future__ import annotations

from pathlib import Path

import pytest

from swirui import FileFilter, FilePicker, FolderPicker
from swirui.core import AccessibilityRole
from swirui.rendering import Rect


def test_file_picker_filters_sorts_and_preserves_selection(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "beta.txt").write_text("beta", encoding="utf-8")
    (tmp_path / "alpha.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"png")
    (tmp_path / ".secret.txt").write_text("hidden", encoding="utf-8")

    picker = FilePicker(
        bounds=Rect(0.0, 0.0, 620.0, 360.0),
        directory=tmp_path,
        filters=(FileFilter("Text", ("*.txt",)),),
        key="files",
    )

    assert [entry.name for entry in picker.entries] == ["assets", "alpha.txt", "beta.txt"]
    picker.select_path(tmp_path / "beta.txt")
    assert picker.selected_path == (tmp_path / "beta.txt").absolute()

    (tmp_path / "gamma.txt").write_text("gamma", encoding="utf-8")
    picker.refresh()
    assert picker.selected_path == (tmp_path / "beta.txt").absolute()
    assert [entry.name for entry in picker.entries] == [
        "assets",
        "alpha.txt",
        "beta.txt",
        "gamma.txt",
    ]

    picker.set_show_hidden(True)
    assert ".secret.txt" in {entry.name for entry in picker.entries}


def test_file_picker_navigation_confirmation_and_filter_switch(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "readme.md").write_text("# demo", encoding="utf-8")
    (folder / "notes.txt").write_text("notes", encoding="utf-8")

    picker = FilePicker(
        bounds=Rect(0.0, 0.0, 600.0, 330.0),
        directory=tmp_path,
        filters=(
            FileFilter("Markdown", ("*.md",)),
            FileFilter("Text", ("*.txt",)),
        ),
        key="file-picker",
    )
    picker.select_path(folder)
    picker.activate_selected()
    assert picker.current_directory == folder.absolute()
    assert [entry.name for entry in picker.entries] == ["readme.md"]

    picker.set_active_filter(1)
    assert [entry.name for entry in picker.entries] == ["notes.txt"]
    picker.select_path(folder / "notes.txt")
    confirmed: list[Path] = []
    picker.on("selection_confirmed", lambda event: confirmed.append(event.data["path"]))
    picker.confirm_selection()
    assert confirmed == [(folder / "notes.txt").absolute()]

    picker.navigate_parent()
    assert picker.current_directory == tmp_path.absolute()


def test_folder_picker_only_lists_folders_and_confirms_current_directory(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (tmp_path / "file.txt").write_text("not a folder", encoding="utf-8")

    picker = FolderPicker(
        bounds=Rect(0.0, 0.0, 600.0, 320.0),
        directory=tmp_path,
        key="folders",
    )
    assert [entry.name for entry in picker.entries] == ["first", "second"]
    assert picker.selected_folder == first.absolute()

    picker.select_path(second)
    assert picker.selected_folder == second.absolute()
    confirmed: list[Path] = []
    picker.on("selection_confirmed", lambda event: confirmed.append(event.data["path"]))
    picker.confirm_selection()
    assert confirmed == [second.absolute()]

    empty = tmp_path / "empty"
    empty.mkdir()
    picker.navigate_to(empty)
    assert picker.entries == ()
    assert picker.selected_folder == empty.absolute()


def test_file_picker_scene_virtualization_and_accessibility(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"item-{index:02d}.txt").write_text(str(index), encoding="utf-8")

    picker = FilePicker(
        bounds=Rect(10.0, 20.0, 560.0, 260.0),
        directory=tmp_path,
        filters=(FileFilter("Text", ("*.txt",)),),
        row_height=28.0,
        key="browser",
    )
    scene = picker.build_scene_node()
    row_keys = [
        node.key
        for node in scene.walk()
        if ":row:" in node.key and node.key.count(":") == 2
    ]
    assert 0 < len(row_keys) < len(picker.entries)
    assert "browser:header" in {node.key for node in scene.walk()}
    assert "browser:action" in {node.key for node in scene.walk()}

    picker.select_index(30)
    assert picker.scroll_row > 0
    snapshot = picker.accessibility_snapshot(focused=picker)
    assert snapshot.role is AccessibilityRole.LIST
    assert snapshot.focused is True
    assert snapshot.row_count == 40
    assert snapshot.children
    assert any(child.selected for child in snapshot.children)


def test_file_picker_validates_filters_and_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="patterns"):
        FileFilter("Empty", ())
    with pytest.raises(IndexError, match="active_filter_index"):
        FilePicker(
            bounds=Rect(0.0, 0.0, 320.0, 200.0),
            directory=tmp_path,
            filters=(FileFilter("Text", ("*.txt",)),),
            active_filter_index=3,
        )
    with pytest.raises(FileNotFoundError):
        FilePicker(
            bounds=Rect(0.0, 0.0, 320.0, 200.0),
            directory=tmp_path / "missing",
        )
