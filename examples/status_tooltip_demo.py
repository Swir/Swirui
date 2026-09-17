"""Interactive retained Badge, Chip and Tooltip demo."""

from swirui import App, Badge, Chip, Component, Label, Tooltip, Window, mount
from swirui.rendering import Color, Rect

app = App("SwirUI status and tooltip controls")
window = app.add_window(Window(title="SwirUI — Badge + Chip + Tooltip", width=680, height=360))
root = Component("status-tooltip-demo")

heading = Label(
    "SwirUI 0.4 — status + contextual controls",
    bounds=Rect(36.0, 28.0, 560.0, 36.0),
    font_size=23.0,
    color=Color.from_hex("#62E5FF"),
)
badge = Badge(
    "ALPHA",
    key="alpha-badge",
    bounds=Rect(36.0, 96.0, 92.0, 30.0),
    accessible_name="Alpha status",
)
chip = Chip(
    "GPU renderer",
    key="gpu-chip",
    bounds=Rect(36.0, 154.0, 152.0, 38.0),
    accessible_description="Activate to cycle the demo status",
)
tooltip = Tooltip(
    "Click or focus this chip",
    target=chip,
    key="gpu-chip-tooltip",
    bounds=Rect(36.0, 204.0, 220.0, 36.0),
)
status = Label(
    "Hover or focus the chip to reveal its retained tooltip.",
    key="status-text",
    bounds=Rect(36.0, 278.0, 560.0, 30.0),
    color=Color.from_hex("#8DA8B8"),
)
root.add(heading, badge, chip, tooltip, status)
mount(window, root)

clicks = 0


def cycle_status(*_args: object) -> None:
    global clicks
    clicks += 1
    badge.text = "ACTIVE" if clicks % 2 else "ALPHA"
    status.text = f"Chip activations: {clicks}"


chip.on("click", cycle_status)
app.run()
