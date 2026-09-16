"""Open the first real SwirUI native window on Windows."""

from swirui import App, Window

app = App("SwirUI Native Demo")
window = app.add_window(
    Window(
        title="SwirUI — Native Win32 Alpha",
        width=1100,
        height=720,
        min_width=640,
        min_height=420,
    )
)

window.on("resized", lambda event: print("resize:", event.data["size"]))
window.on(
    "pointer_move",
    lambda event: print(
        "pointer:",
        event.data["event"].x,
        event.data["event"].y,
    ),
)
window.on("key_down", lambda event: print("key:", event.data["event"].key_code))
window.on("text_input", lambda event: print("text:", event.data["event"].text))
window.on("closed", lambda _event: print("native window closed"))

raise SystemExit(app.run())
