"""Professional CodeEditor demo with retained Python syntax highlighting."""

from __future__ import annotations

from swirui import CodeEditor
from swirui.rendering.geometry import Rect


def main() -> None:
    source = """from swirui import App, Window


def build_app() -> App:
    app = App(name="SwirUI Editor")
    app.add_window(Window(title="Editor", width=960, height=640))
    return app
"""
    editor = CodeEditor(
        source,
        bounds=Rect(24.0, 24.0, 880.0, 520.0),
        accessible_name="SwirUI source editor",
        language="python",
    )
    editor.scroll_to_line(1)
    scene = editor.build_scene_node()
    syntax_nodes = sum(1 for node in scene.walk() if ":syntax:" in node.key)

    print(
        "CodeEditor "
        f"lines={editor.line_count}, visible={editor.visible_line_range}, "
        f"syntax_nodes={syntax_nodes}, "
        f"retained_nodes={sum(1 for _ in scene.walk())}"
    )
    print(editor.accessible_value_text)


if __name__ == "__main__":
    main()
