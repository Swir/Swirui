"""Image/SVG/GIF media pipeline demo backed by the Rust native decoder."""

from __future__ import annotations

import base64

from swirui import App, AppConfig, Panel, Window, mount
from swirui.media import decode_image
from swirui.rendering import Rect, WgpuRenderer
from swirui.widgets import Image, ImageFit

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
)
GIF_1X1 = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
SVG_CARD = b"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="96">
<rect width="160" height="96" rx="18" fill="#0d1627"/>
<circle cx="48" cy="48" r="24" fill="#00a8ff"/>
<rect x="84" y="32" width="52" height="12" rx="6" fill="#eaf7ff"/>
<rect x="84" y="54" width="38" height="8" rx="4" fill="#58c7ff"/>
</svg>"""


def main() -> None:
    renderer = WgpuRenderer()
    png = decode_image(PNG_1X1, format_hint="png")
    svg = decode_image(SVG_CARD, width=320, height=192)
    gif = decode_image(GIF_1X1)

    png.register_frame(renderer, "media:png")
    svg.register_frame(renderer, "media:svg")
    gif_ids = gif.register_all(renderer, "media:gif")

    app = App("SwirUI Media Image", config=AppConfig(target_fps=120), renderer=renderer)
    window = app.add_window(Window(title="SwirUI Image / SVG / GIF", width=900, height=420))
    root = Panel(bounds=Rect(0.0, 0.0, 900.0, 420.0), key="media-image-demo")
    root.add(
        Image(
            "media:png",
            pixel_width=png.width,
            pixel_height=png.height,
            bounds=Rect(60.0, 80.0, 220.0, 240.0),
            fit=ImageFit.CONTAIN,
            accessible_name="Decoded PNG preview",
        ),
        Image(
            "media:svg",
            pixel_width=svg.width,
            pixel_height=svg.height,
            bounds=Rect(340.0, 80.0, 220.0, 240.0),
            fit=ImageFit.CONTAIN,
            accessible_name="Native rasterized SVG preview",
        ),
        Image(
            gif_ids[0],
            pixel_width=gif.width,
            pixel_height=gif.height,
            bounds=Rect(620.0, 80.0, 220.0, 240.0),
            fit=ImageFit.CONTAIN,
            accessible_name="Decoded GIF preview",
        ),
    )
    mount(window, root)
    raise SystemExit(app.run())


if __name__ == "__main__":
    main()
