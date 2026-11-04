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
    parser.add_argument("--pane", choices=("dashboard", "preview"), default="dashboard")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    args = parser.parse_args()
    if args.width < 1024 or args.height < 720:
        parser.error("Studio requires at least 1024 × 720 logical pixels")
    renderer = WgpuRenderer()
    app = App("SwirUI Studio capture", renderer=renderer)
    window = app.add_window(Window(width=args.width, height=args.height,
                                   min_width=1024, min_height=720))
    studio = StudioSuite()
    studio.resize_to(args.width, args.height)
    window.on("resized", lambda _: studio.resize_to(window.width, window.height))
    if args.theme == "light":
        studio.toggle_theme()
    studio.activate(args.pane)
    mount(window, studio)
    animations = AnimationController(app, window)
    interactions = studio.bind_interactions(animations)
    try:
        app.start()
        app.process_events()
        # Settle any input-induced material feedback before the recorded frame.
        for interaction in interactions:
            interaction.dispose()
        app.invalidate(window)
        last = app._frame_schedulers[window].stats.last_frame_time
        assert last is not None
        app.render_pending(last + 1)
        context = renderer._contexts[window.native_handle.value]
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
