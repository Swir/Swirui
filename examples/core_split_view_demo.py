"""Interactive retained SplitView demo for SwirUI 0.4."""

from swirui import App, Button, Component, Label, Panel, SplitView, Window, mount
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI SplitView")
    window = app.add_window(Window(title="SwirUI — SplitView", width=980, height=620))
    root = Component("SplitView demo")

    root.add(
        Label(
            "SplitView — drag the cyan divider or focus it and use Left / Right",
            key="instructions",
            bounds=Rect(48.0, 24.0, 800.0, 30.0),
            font_size=16.0,
            color=Color.from_hex("#D8F4FF"),
        )
    )

    first = Panel(
        key="explorer",
        bounds=Rect(0.0, 0.0, 500.0, 460.0),
        background=Color.from_hex("#07111C"),
        border_width=0.0,
    )
    first.add(
        Label(
            "PROJECT",
            key="project-label",
            bounds=Rect(20.0, 20.0, 180.0, 28.0),
            font_size=13.0,
            color=Color.from_hex("#62E5FF"),
        ),
        Button(
            "src / swirui",
            key="project-src",
            bounds=Rect(20.0, 64.0, 210.0, 44.0),
        ),
        Button(
            "tests",
            key="project-tests",
            bounds=Rect(20.0, 120.0, 210.0, 44.0),
        ),
    )

    second = Panel(
        key="editor",
        bounds=Rect(0.0, 0.0, 700.0, 460.0),
        background=Color.from_hex("#091723"),
        border_width=0.0,
    )
    second.add(
        Label(
            "main.py",
            key="editor-title",
            bounds=Rect(24.0, 20.0, 220.0, 30.0),
            font_size=17.0,
            color=Color.from_hex("#ECF9FF"),
        ),
        Label(
            "from swirui import App, SplitView",
            key="editor-line-1",
            bounds=Rect(24.0, 78.0, 420.0, 26.0),
            font_size=14.0,
            color=Color.from_hex("#8DA8B8"),
        ),
        Label(
            "# GPU-first retained desktop UI",
            key="editor-line-2",
            bounds=Rect(24.0, 112.0, 420.0, 26.0),
            font_size=14.0,
            color=Color.from_hex("#23C9FF"),
        ),
    )

    split = SplitView(
        key="workspace-split",
        bounds=Rect(48.0, 76.0, 860.0, 460.0),
        first=first,
        second=second,
        split_ratio=0.34,
        min_ratio=0.2,
        max_ratio=0.75,
        divider_size=8.0,
        accessible_name="Workspace split",
    )
    root.add(split)
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
