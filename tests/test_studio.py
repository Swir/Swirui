from swirui import Window, mount
from swirui import __main__ as cli
from swirui.rendering import Rect
from swirui.studio import ShowcaseEditor


def pane(editor: ShowcaseEditor, key: str):
    return next(item for item in editor.workspace.panes if item.key == key)


def test_showcase_unifies_design_code_inspector_and_console():
    editor = ShowcaseEditor()
    window = Window(width=1440, height=900)
    runtime = mount(window, editor)
    try:
        editor.prepare_layout(Rect(0, 0, 1440, 900))
        assert editor.center_tabs.selected_key == "design"
        assert editor.left_tabs.selected_key == "hierarchy"
        assert editor.bottom_tabs.selected_key == "console"
        assert pane(editor, "explorer").dock == "left"
        assert pane(editor, "inspector").dock == "right"
        assert pane(editor, "console").dock == "bottom"
        assert editor.hierarchy.selected_node is not None
        assert editor.hierarchy.selected_node.key == "hero"
        assert editor.preview.selected_key == "hero"

        editor.hierarchy.select_index(5)
        assert editor.hierarchy.selected_node is not None
        assert editor.hierarchy.selected_node.key == "metric"
        assert editor.preview.selected_key == "metric"
        assert editor.inspector.items[0].value == "Metric"

        editor.inspector.set_value("title", "Ship a better native app.")
        assert editor.preview.headline.text == "Ship a better native app."
        editor.run_button.emit("click")
        assert editor.preview_running and editor.preview.running
        assert editor.run_button.text == "Pause preview"

        editor.mode.emit("click")
        assert editor.light and editor.mode.text == "Dark appearance"
        assert editor.preview.headline.text == "Ship a better native app."
    finally:
        runtime.unmount()


def test_showcase_responsive_docking_and_reset_preserve_state():
    editor = ShowcaseEditor()
    editor.editor.value = "# retained draft"
    editor.prepare_layout(Rect(0, 0, 1000, 720))
    assert editor.compact
    assert pane(editor, "inspector").dock == "center"

    editor.prepare_layout(Rect(0, 0, 1440, 900))
    assert not editor.compact
    assert pane(editor, "inspector").dock == "right"
    assert editor.editor.value == "# retained draft"

    editor.center_tabs.select_key("code")
    editor.left_tabs.select_key("assets")
    editor.bottom_tabs.select_key("output")
    editor.reset_layout()
    assert editor.center_tabs.selected_key == "design"
    assert editor.left_tabs.selected_key == "hierarchy"
    assert editor.bottom_tabs.selected_key == "console"
    assert editor.editor.value == "# retained draft"


def test_cli_studio_subcommand_routes_to_showcase(monkeypatch):
    import swirui.studio as studio

    monkeypatch.setattr(cli, "installation_report", lambda: {"ready": True})
    monkeypatch.setattr(studio, "run", lambda *, smoke_test=False: 7 if smoke_test else 6)
    assert cli.main(["studio"]) == 6
    assert cli.main(["studio", "--smoke-test"]) == 7
