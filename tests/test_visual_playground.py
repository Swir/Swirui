"""Exercise real control events in the native playground without opening a window."""

import runpy
from pathlib import Path

from swirui import Checkbox, Input, Slider, Switch, Window, mount

Studio = runpy.run_path(str(Path(__file__).parents[1] / "examples" / "swirui_studio.py"))["Studio"]


def test_palette_change_preserves_edits_and_toggle_events() -> None:
    studio = Studio()
    title = studio.controls["title"]
    radius = studio.controls["radius"]
    depth = studio.controls["depth"]
    motion = studio.controls["motion"]
    glass = studio.controls["glass"]
    assert isinstance(title, Input)
    assert isinstance(radius, Slider) and isinstance(depth, Slider)
    assert isinstance(motion, Switch) and isinstance(glass, Checkbox)
    title.value = "My own interface"
    radius.value = 40
    depth.value = 12
    motion.toggle()
    glass.toggle()
    assert (studio.motion, studio.glass) == (False, False)
    studio.controls["Ocean"].emit("click")
    assert studio.palette_name == "Ocean"
    assert studio.controls["title"].value == "My own interface"
    assert studio.controls["radius"].value == 40
    assert studio.controls["depth"].value == 12
    assert not studio.controls["motion"].checked
    assert not studio.controls["glass"].checked
    studio.controls["reset"].emit("click")
    assert studio.palette_name == "Violet"
    assert studio.title == "Make space for possibility."
    assert (studio.radius, studio.depth, studio.motion, studio.glass) == (24, 24, True, True)


def test_preview_actions_work_without_a_running_animation_controller() -> None:
    studio = Studio()
    for name in ("primary", "secondary", "ghost"):
        studio.controls[name].emit("click")
    assert studio.preview_count == 3
    assert studio.phase == 0


def test_live_palette_and_mode_keep_the_same_controls_and_focused_selection() -> None:
    studio = Studio()
    window = Window(width=1440, height=860)
    mount(window, studio)
    title = studio.controls["title"]
    title.value = "Keep this selection"
    window.focus_component(title)
    title.select_all()
    original_controls = dict(studio.controls)
    studio.change_palette("Ocean")
    studio.toggle_mode()
    assert studio.light_mode
    assert studio.controls == original_controls
    assert all(control.effective_theme == studio.theme for control in studio.controls.values())
    assert window.focused_component is title
    assert title.selected_text == "Keep this selection"
    assert studio.controls["mode"].text == "Dark theme"
    studio.reset()
    assert not studio.light_mode
    assert studio.controls == original_controls
