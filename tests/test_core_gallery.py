"""Exercise gallery interactions through the public control event interfaces."""

import runpy
from pathlib import Path

from swirui import FUTURE_LIGHT, Window, mount

Gallery = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "core_gallery.py"))["Gallery"]


def test_gallery_mode_preserves_interactive_controls_and_dialog_focus():
    gallery = Gallery()
    window = Window(width=1200, height=820)
    gallery.window = window
    runtime = mount(window, gallery)
    try:
        gallery.slider.value = 82
        gallery.field.value = "My workspace"
        gallery.chip.emit("click")
        gallery.expander.collapse()
        gallery.split.split_ratio = 0.7
        gallery.notice.emit("click")
        controls = tuple(gallery.children)
        gallery.mode.emit("click")
        assert gallery.theme == FUTURE_LIGHT
        assert tuple(gallery.children) == controls
        assert gallery.progress.value == gallery.ring.value == 82
        assert gallery.percent.text == "82%"
        assert gallery.field.value == "My workspace" and not gallery.field.visible
        assert not gallery.chip.selected
        assert gallery.split.split_ratio == 0.7
        assert gallery.toast.kind == "info"
        gallery.open_dialog.emit("click")
        assert gallery.dialog.is_open and window.focused_component is gallery.close_dialog
        gallery.close_dialog.emit("click")
        assert not gallery.dialog.is_open and window.focused_component is gallery.open_dialog
    finally:
        runtime.unmount()
