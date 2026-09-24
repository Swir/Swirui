"""Terminal demo with application-owned command handling."""

from __future__ import annotations

from swirui import Terminal
from swirui.rendering.geometry import Rect


def main() -> None:
    terminal = Terminal(
        bounds=Rect(24.0, 24.0, 760.0, 360.0),
        prompt="swir> ",
        accessible_name="SwirUI demo terminal",
    )
    terminal.writeln("\x1b[36mSwirUI retained terminal\x1b[0m")
    terminal.writeln("Commands are application-owned; the widget never starts a shell.")

    def handle_command(command: str) -> None:
        normalized = command.strip().lower()
        if normalized == "help":
            terminal.writeln("help, status, clear")
        elif normalized == "status":
            terminal.writeln("\x1b[32mrenderer ready\x1b[0m")
        elif normalized == "clear":
            terminal.clear_buffer()
        elif normalized:
            terminal.writeln(f"unknown command: {command}")

    # A real app would subscribe to ``submitted``. The calls below keep this
    # example deterministic and renderer-independent for documentation/CI use.
    for command in ("help", "status"):
        terminal.input_text = command
        terminal.submit()
        handle_command(command)

    scene = terminal.build_scene_node()
    print(f"Terminal lines={len(terminal.lines)}, retained_nodes={sum(1 for _ in scene.walk())}")
    print(terminal.accessible_value_text)


if __name__ == "__main__":
    main()
