from __future__ import annotations

import pytest

from swirui import Autocomplete as PublicAutocomplete
from swirui import AutocompleteProvider as PublicAutocompleteProvider
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind
from swirui.rendering.geometry import Rect
from swirui.rendering.scene import SceneNodeKind
from swirui.widgets import Autocomplete as WidgetsAutocomplete
from swirui.widgets import AutocompleteProvider as WidgetsAutocompleteProvider
from swirui.widgets.autocomplete import Autocomplete, AutocompleteProvider

_WINDOW = NativeWindowHandle(1)


def test_autocomplete_public_api_exports_retained_component() -> None:
    assert PublicAutocomplete is Autocomplete
    assert WidgetsAutocomplete is Autocomplete
    assert PublicAutocompleteProvider is AutocompleteProvider
    assert WidgetsAutocompleteProvider is AutocompleteProvider


def _event(
    kind: PlatformEventKind,
    *,
    key_code: int | None = None,
    text: str | None = None,
    ctrl: bool = False,
) -> PlatformEvent:
    return PlatformEvent(
        kind=kind,
        window=_WINDOW,
        key_code=key_code,
        text=text,
        ctrl=ctrl,
    )


def test_autocomplete_filters_prefix_and_renders_bounded_popup() -> None:
    control = Autocomplete(
        "",
        bounds=Rect(10.0, 20.0, 320.0, 44.0),
        items=("Alpha", "Alpine", "Beta"),
        max_suggestions=2,
    )
    control.emit("focus_gained")
    typed = control.emit(
        "text_input",
        event=_event(PlatformEventKind.TEXT_INPUT, text="a"),
    )
    scene = control.build_scene_node()
    suggestion_nodes = [
        node
        for node in scene.walk()
        if node.kind is SceneNodeKind.TEXT and ":suggestion:" in node.key
    ]

    assert typed.default_prevented
    assert control.value == "a"
    assert control.suggestions == ("Alpha", "Alpine")
    assert control.suggestions_open
    assert not scene.clip_to_bounds
    assert [node.text for node in suggestion_nodes] == ["Alpha", "Alpine"]
    assert "2 suggestions" in (control.accessible_value_text or "")


def test_autocomplete_keyboard_selection_accepts_suggestion() -> None:
    control = Autocomplete(
        "sw",
        bounds=Rect(0.0, 0.0, 360.0, 44.0),
        items=("SwirUI", "SwirEngine", "Something"),
    )
    accepted: list[str] = []
    control.on(
        "suggestion_accepted",
        lambda event: accepted.append(str(event.data["suggestion"])),
    )
    control.emit("focus_gained")

    down = control.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x28),
    )
    enter = control.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x0D),
    )

    assert down.default_prevented
    assert enter.default_prevented
    assert control.value == "SwirUI"
    assert accepted == ["SwirUI"]
    assert not control.suggestions_open
    assert control.selected_suggestion is None


def test_autocomplete_ctrl_space_forces_open_and_escape_closes() -> None:
    control = Autocomplete(
        "",
        bounds=Rect(0.0, 0.0, 300.0, 44.0),
        items=("one", "two", "three"),
        minimum_prefix_length=3,
        max_suggestions=2,
    )
    control.emit("focus_gained")
    assert not control.suggestions_open

    forced = control.emit(
        "key_down",
        event=_event(
            PlatformEventKind.KEY_DOWN,
            key_code=0x20,
            ctrl=True,
        ),
    )
    assert forced.default_prevented
    assert control.suggestions == ("one", "two")
    assert control.selected_suggestion == "one"

    escaped = control.emit(
        "key_down",
        event=_event(PlatformEventKind.KEY_DOWN, key_code=0x1B),
    )
    assert escaped.default_prevented
    assert not control.suggestions_open


def test_autocomplete_provider_is_bounded_deduplicated_and_receives_caret() -> None:
    calls: list[tuple[str, int]] = []

    def provider(value: str, caret: int):
        calls.append((value, caret))
        yield "apple"
        yield "APPLE"
        yield "application"
        yield "apricot"
        yield from (f"app-{index}" for index in range(2_000))

    control = Autocomplete(
        "ap",
        bounds=Rect(0.0, 0.0, 320.0, 44.0),
        provider=provider,
        max_suggestions=3,
    )
    control.emit("focus_gained")

    assert calls[-1] == ("ap", 2)
    assert control.suggestions == ("apple", "application", "apricot")
    assert len(control.suggestions) == 3


def test_autocomplete_case_sensitive_matching_and_focus_loss() -> None:
    control = Autocomplete(
        "Sw",
        bounds=Rect(0.0, 0.0, 320.0, 44.0),
        items=("SwirUI", "swirl", "Switch"),
        case_sensitive=True,
    )
    control.emit("focus_gained")

    assert control.suggestions == ("SwirUI", "Switch")
    control.emit("focus_lost")
    assert not control.suggestions_open


def test_autocomplete_case_insensitive_matching_excludes_current_identity() -> None:
    control = Autocomplete(
        "swirui",
        bounds=Rect(0.0, 0.0, 320.0, 44.0),
        items=("SwirUI", "SwirEngine", "SWIRUI"),
        case_sensitive=False,
    )
    control.emit("focus_gained")

    assert control.suggestions == ()


def test_autocomplete_rejects_invalid_configuration() -> None:
    bounds = Rect(0.0, 0.0, 320.0, 44.0)

    with pytest.raises(ValueError, match="minimum_prefix_length"):
        Autocomplete(bounds=bounds, minimum_prefix_length=-1)

    with pytest.raises(ValueError, match="max_suggestions"):
        Autocomplete(bounds=bounds, max_suggestions=0)

    with pytest.raises(ValueError, match="max_suggestions"):
        Autocomplete(bounds=bounds, max_suggestions=33)

    with pytest.raises(TypeError, match="provider"):
        Autocomplete(bounds=bounds, provider=object())  # type: ignore[arg-type]
