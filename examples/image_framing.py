"""Pan a live square crop of the Studio comparison with the mouse or arrow keys."""

from pathlib import Path

from swirui import NEON_BLUE, App, Label, Panel, Slider, Window, mount
from swirui.media import decode_image
from swirui.rendering import Point, Rect, WgpuRenderer
from swirui.widgets import Image, ImageFit


def create_app(renderer: WgpuRenderer) -> App:
    path = Path(__file__).resolve().parents[1] / "docs/screenshots/studio-comparison.png"
    asset = decode_image(path.read_bytes())
    resource = "studio-comparison"
    asset.register_frame(renderer, resource)
    app = App("Image framing", renderer=renderer)
    window = app.add_window(Window(title="Image framing", width=920, height=418,
                                   min_width=560, min_height=270))
    theme = NEON_BLUE.with_accent("#FF7ADE")
    initial = Rect(0, 0, 1, 1)
    root = Panel(bounds=initial, theme=theme)
    source_label = Label("Source image", bounds=initial, font_size=22)
    crop_label = Label("Square crop", bounds=initial, font_size=22)
    position_label = Label("Horizontal position", bounds=initial)
    slider = Slider(bounds=initial, value=100, accessible_name="Horizontal position")
    source = Image(resource, bounds=initial, pixel_width=asset.width, pixel_height=asset.height,
                   accessible_name="Studio in dark and light appearances")
    crop = Image(resource, bounds=initial, pixel_width=asset.width, pixel_height=asset.height,
                 fit=ImageFit.COVER, image_position=Point(1, 0.5),
                 accessible_name="Square crop of the Studio comparison")
    root.add(source_label, source, crop_label, crop, position_label, slider)

    def layout() -> None:
        width, height = window.width, window.height
        size = min(height - 144, (width - 72) * 0.38)
        right = width - 24 - size
        root.bounds = Rect(0, 0, width, height)
        source_label.bounds = Rect(24, 18, right - 48, 32)
        crop_label.bounds = Rect(right, 18, size, 32)
        source.bounds = Rect(24, 60, right - 48, size)
        crop.bounds = Rect(right, 60, size, size)
        position_label.bounds = Rect(right, 70 + size, size, 24)
        slider.bounds = Rect(right, 96 + size, size, 32)

    def pan() -> None:
        crop.image_position = Point(slider.value / 100, 0.5)

    slider.on("changed", lambda _: pan())
    window.on("resized", lambda _: layout())
    layout()
    mount(window, root)
    return app


if __name__ == "__main__":
    raise SystemExit(create_app(WgpuRenderer()).run())
