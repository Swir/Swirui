"""Timeline demo for retained professional SwirUI applications."""

from swirui import App, Timeline, TimelineItem, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App("SwirUI Timeline")
    window = app.add_window(Window(title="SwirUI Professional Timeline", width=820, height=520))
    timeline = Timeline(
        (
            TimelineItem("idea", "Idea", "09:00", "Define the user workflow."),
            TimelineItem("build", "Build", "10:30", "Implement the retained widget."),
            TimelineItem("verify", "Verify", "12:00", "Run Win32 + wgpu qualification."),
            TimelineItem("merge", "Merge", "14:00", "Integrate only after exact-head green."),
        ),
        bounds=Rect(90.0, 70.0, 620.0, 330.0),
        key="demo-timeline",
    )
    timeline.on(
        "selection_changed",
        lambda event: print("Selected:", event.data["item"].title),
    )
    timeline.on(
        "item_activated",
        lambda event: print("Activated:", event.data["item"].title),
    )
    mount(window, timeline)
    app.run()


if __name__ == "__main__":
    main()
