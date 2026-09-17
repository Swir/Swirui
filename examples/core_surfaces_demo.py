"""Interactive retained badge, tooltip and surface demo for SwirUI 0.4."""

from swirui import App, Badge, Card, Chip, Component, GlassCard, Label, Tooltip, Window, mount
from swirui.core import Event
from swirui.rendering import Color, Rect


def main() -> int:
    app = App("SwirUI Content & Surfaces")
    window = app.add_window(Window(title="SwirUI — Content & Surfaces", width=820, height=500))
    root = Component("Content and surfaces demo")

    glass = GlassCard(
        key="glass-status",
        bounds=Rect(34.0, 34.0, 458.0, 244.0),
        accessible_name="GPU status card",
    )
    title = Label(
        "Retained glass surface",
        key="glass-title",
        bounds=Rect(64.0, 62.0, 330.0, 34.0),
        font_size=22.0,
        color=Color.from_hex("#62E5FF"),
    )
    badge = Badge(
        "0.4 ALPHA",
        key="milestone-badge",
        bounds=Rect(64.0, 118.0, 118.0, 30.0),
    )
    chip = Chip(
        "GPU effects",
        key="effects-chip",
        bounds=Rect(64.0, 172.0, 150.0, 40.0),
        accessible_name="GPU effects enabled",
    )
    status = Label(
        "Select the chip with pointer, Tab + Space, or Enter.",
        key="glass-status-text",
        bounds=Rect(64.0, 226.0, 390.0, 28.0),
        font_size=14.0,
        color=Color.from_hex("#D8F4FF"),
    )
    glass.add(title, badge, chip, status)

    tooltip = Tooltip(
        "Toggles the retained selection state",
        key="effects-tooltip",
        target=chip,
        bounds=Rect(224.0, 174.0, 250.0, 36.0),
    )

    card = Card(
        key="standard-card",
        bounds=Rect(530.0, 54.0, 250.0, 188.0),
        accessible_name="Standard card",
    )
    card.add(
        Label(
            "Card",
            key="card-title",
            bounds=Rect(558.0, 82.0, 150.0, 30.0),
            font_size=20.0,
            color=Color.from_hex("#F4FAFF"),
        ),
        Badge(
            "retained shadow",
            key="shadow-badge",
            bounds=Rect(558.0, 134.0, 142.0, 30.0),
        ),
        Label(
            "Same SceneGraph and persistent GPU path.",
            key="card-detail",
            bounds=Rect(558.0, 184.0, 190.0, 36.0),
            font_size=13.0,
            color=Color.from_hex("#B5D8E8"),
        ),
    )

    def update_status(event: Event) -> None:
        selected = bool(event.data["selected"])
        status.text = f"GPU effects selected: {'yes' if selected else 'no'}"

    chip.on("selection_changed", update_status)
    root.add(glass, tooltip, card)
    mount(window, root)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
