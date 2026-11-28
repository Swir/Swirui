"""Capture the actual Windows/wgpu client frame, without an OS cursor or chrome.

From a source checkout with a built native module:
    python tools/capture_studio.py --output studio-dark.png
    python tools/capture_studio.py --theme light --output studio-light.png

The PNG contains unmodified renderer RGBA pixels, not a desktop screenshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from swirui import AnimationController, App, Window, mount
from swirui.rendering import WgpuRenderer
from swirui.studio_comparison import bind_comparison
from swirui.studio_suite import StudioSuite


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    if width <= 0 or height <= 0 or len(rgba) != width * height * 4:
        raise ValueError("Invalid renderer readback dimensions or byte length")

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))

    stride = width * 4
    rows = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, level=9)) + chunk(b"IEND", b"")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument("--pane", choices=("dashboard", "preview", "settings", "comparison"),
                        default="dashboard")
    parser.add_argument("--accent", help="Opaque hex accent, e.g. #7FE0BF")
    parser.add_argument("--corner-radius", type=int, help="Authored control radius (0–24)")
    parser.add_argument("--layer-tilt", type=int, nargs=2, metavar=("X", "Y"),
                        help="Inspector angles in degrees (−35 to 35)")
    parser.add_argument("--depth-layers", type=int, choices=range(9),
                        help="Number of decorative layers behind the card")
    parser.add_argument("--focus-motion", action="store_true",
                        help="Show focus on the Enable motion switch in the preview")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--comparison-size", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"),
                        help="Resize the comparison window before capturing its frame")
    parser.add_argument("--comparison-text", nargs=2, metavar=("NAME", "HEADLINE"),
                        help="Set the project name and Inspector headline for the comparison")
    args = parser.parse_args()
    if args.width < 1024 or args.height < 720:
        parser.error("Studio requires at least 1024 × 720 logical pixels")
    if args.focus_motion and args.pane != "preview":
        parser.error("--focus-motion requires --pane preview")
    if args.layer_tilt and any(abs(angle) > 35 for angle in args.layer_tilt):
        parser.error("--layer-tilt angles must be between -35 and 35 degrees")
    if args.comparison_size and (args.pane != "comparison" or args.comparison_size[0] < 320
                                 or args.comparison_size[1] < 390):
        parser.error("--comparison-size requires --pane comparison and at least 320 × 390")
    if args.comparison_text and args.pane != "comparison":
        parser.error("--comparison-text requires --pane comparison")
    renderer = WgpuRenderer()
    app = App("SwirUI Studio capture", renderer=renderer)
    window = app.add_window(Window(width=args.width, height=args.height,
                                   min_width=1024, min_height=720))
    studio = StudioSuite()
    studio.resize_to(args.width, args.height)
    if args.comparison_text:
        name, headline = args.comparison_text
        studio.preview.project.value = name
        studio.inspector.set_value("title", headline)
        try:
            studio.preview.theme_package()
        except ValueError as error:
            parser.error(str(error))
    window.on("resized", lambda _: studio.resize_to(window.width, window.height))
    if args.theme == "light":
        studio.toggle_theme()
    if args.accent is not None and not studio.settings.set_accent(args.accent):
        parser.error("--accent must be an opaque hex color")
    if args.layer_tilt:
        studio.inspector.set_value("tilt_x", args.layer_tilt[0])
        studio.inspector.set_value("tilt_y", args.layer_tilt[1])
    if args.depth_layers is not None:
        studio.inspector.set_value("depth", args.depth_layers)
    if args.corner_radius is not None:
        corners = studio.preview.corners
        if not corners.minimum <= args.corner_radius <= corners.maximum:
            parser.error("--corner-radius must be between 0 and 24")
        corners.value = args.corner_radius
    studio.activate("preview" if args.pane == "comparison" else args.pane)
    mount(window, studio)
    bind_comparison(app, window, studio.preview)
    animations = AnimationController(app, window)
    interactions = studio.bind_interactions(animations)
    try:
        app.start()
        app.process_events()
        # Settle any input-induced material feedback before the recorded frame.
        for interaction in interactions:
            interaction.dispose()
        target = window
        if args.focus_motion:
            window.focus_component(studio.preview.motion)
        if args.pane == "comparison":
            studio.preview.create.emit("click")
            target, = [candidate for candidate in app.windows if candidate is not window]
            if args.comparison_size:
                target.resize(*args.comparison_size)
            app.process_events()
        app.invalidate(target)
        last = app._frame_schedulers[target].stats.last_frame_time
        assert last is not None
        app.render_pending(last + 1)
        context = renderer._contexts[target.native_handle.value]
        width, height, rgba = context.read_scene_rgba()
        write_png(args.output, width, height, bytes(rgba))
        print(json.dumps({
            "path": str(args.output.resolve()), "width": width, "height": height,
            "theme": args.theme, "pane": args.pane,
            "source": "wgpu read_scene_rgba; OS cursor and window chrome excluded",
            "adapter": renderer.adapter_name, "backend": renderer.graphics_backend,
            "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        }))
    finally:
        for interaction in interactions:
            interaction.dispose()
        animations.dispose()
        app.stop()


if __name__ == "__main__":
    main()
