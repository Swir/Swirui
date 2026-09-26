"""Retained autocomplete input with bounded suggestion rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import islice
from typing import Any

from swirui.core import Event
from swirui.platforms import PlatformEventKind
from swirui.rendering.geometry import Color, CornerRadius, Rect
from swirui.rendering.scene import SceneNode, SceneNodeKind

from .input import Input

AutocompleteProvider = Callable[[str, int], Iterable[str]]

_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_SPACE = 0x20
_VK_UP = 0x26
_VK_DOWN = 0x28
_VK_TAB = 0x09

_DEFAULT_POPUP_BACKGROUND = Color.from_hex("#07111C")
_DEFAULT_POPUP_BORDER = Color.from_hex("#153247")
_DEFAULT_POPUP_FOREGROUND = Color.from_hex("#F4FAFF")
_DEFAULT_POPUP_SELECTED = Color.from_hex("#0D2A3E")
_DEFAULT_POPUP_SELECTED_FOREGROUND = Color.from_hex("#62E5FF")
_MAX_PROVIDER_SCAN = 1024


class Autocomplete(Input):
    """Single-line input with bounded retained suggestions.

    Suggestions may come from a static iterable, a provider callback, or both.
    Matching is prefix based. The popup is keyboard-first and intentionally keeps
    candidate evaluation application-owned when a provider is supplied.
    """

    def __init__(
        self,
        value: str = "",
        *,
        bounds: Rect,
        items: Iterable[str] = (),
        provider: AutocompleteProvider | None = None,
        key: str | None = None,
        placeholder: str = "",
        read_only: bool = False,
        max_length: int | None = None,
        minimum_prefix_length: int = 1,
        max_suggestions: int = 8,
        case_sensitive: bool = False,
        open_on_focus: bool = False,
        popup_gap: float = 4.0,
        popup_background: Color | None = None,
        popup_border: Color | None = None,
        popup_foreground: Color | None = None,
        popup_selected: Color | None = None,
        popup_selected_foreground: Color | None = None,
        accessible_name: str | None = "Autocomplete",
        accessible_description: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._items = self._normalize_items(items)
        self._provider = self._validate_provider(provider)
        self._minimum_prefix_length = self._validate_minimum_prefix_length(
            minimum_prefix_length
        )
        self._max_suggestions = self._validate_max_suggestions(max_suggestions)
        self._case_sensitive = bool(case_sensitive)
        self._open_on_focus = bool(open_on_focus)
        self._popup_gap = self._validate_non_negative(popup_gap, "popup_gap")
        self._popup_background = popup_background or _DEFAULT_POPUP_BACKGROUND
        self._popup_border = popup_border or _DEFAULT_POPUP_BORDER
        self._popup_foreground = popup_foreground or _DEFAULT_POPUP_FOREGROUND
        self._popup_selected = popup_selected or _DEFAULT_POPUP_SELECTED
        self._popup_selected_foreground = (
            popup_selected_foreground or _DEFAULT_POPUP_SELECTED_FOREGROUND
        )
        self._suggestions: tuple[str, ...] = ()
        self._selected_suggestion_index = -1
        self._suggestions_open = False
        self._forced_open = False

        super().__init__(
            value,
            bounds=bounds,
            key=key,
            placeholder=placeholder,
            read_only=read_only,
            max_length=max_length,
            accessible_name=accessible_name,
            accessible_description=accessible_description,
            **kwargs,
        )
        self.on("changed", self._on_value_changed)
        self._sync_autocomplete_accessibility()

    @property
    def items(self) -> tuple[str, ...]:
        return self._items

    @items.setter
    def items(self, value: Iterable[str]) -> None:
        normalized = self._normalize_items(value)
        if normalized == self._items:
            return
        self._items = normalized
        self.refresh_suggestions()

    @property
    def provider(self) -> AutocompleteProvider | None:
        return self._provider

    @provider.setter
    def provider(self, value: AutocompleteProvider | None) -> None:
        normalized = self._validate_provider(value)
        if normalized is self._provider:
            return
        self._provider = normalized
        self.refresh_suggestions()

    @property
    def suggestions(self) -> tuple[str, ...]:
        return self._suggestions

    @property
    def selected_suggestion(self) -> str | None:
        index = self._selected_suggestion_index
        if 0 <= index < len(self._suggestions):
            return self._suggestions[index]
        return None

    @property
    def suggestions_open(self) -> bool:
        return self._suggestions_open

    def open_suggestions(self, *, force: bool = False) -> bool:
        """Refresh and open suggestions, optionally ignoring prefix length."""

        return self.refresh_suggestions(force=force)

    def close_suggestions(self) -> bool:
        """Close the popup and clear keyboard selection."""

        changed = (
            self._suggestions_open
            or self._selected_suggestion_index != -1
            or self._forced_open
        )
        self._suggestions_open = False
        self._selected_suggestion_index = -1
        self._forced_open = False
        if changed:
            self._sync_autocomplete_accessibility()
            self.invalidate(reason="autocomplete_close")
        return changed

    def refresh_suggestions(self, *, force: bool = False) -> bool:
        """Recompute the bounded suggestion set from current input state."""

        forced = bool(force)
        suggestions = self._collect_suggestions(force=forced)
        should_open = bool(suggestions)
        selected = self._selected_suggestion_index
        if selected >= len(suggestions):
            selected = len(suggestions) - 1
        if selected < -1:
            selected = -1

        changed = (
            suggestions != self._suggestions
            or should_open != self._suggestions_open
            or selected != self._selected_suggestion_index
            or forced != self._forced_open
        )
        self._suggestions = suggestions
        self._suggestions_open = should_open
        self._selected_suggestion_index = selected
        self._forced_open = forced
        if changed:
            self._sync_autocomplete_accessibility()
            self.invalidate(reason="autocomplete_refresh")
        return changed

    def build_scene_node(self) -> SceneNode:
        root = super().build_scene_node()
        if not self._suggestions_open or not self._suggestions:
            self._sync_autocomplete_accessibility()
            return root

        root.clip_to_bounds = False
        row_height = self._popup_row_height()
        popup = self._popup_bounds(row_height)
        root.add(
            SceneNode(
                key=f"{self.key}:suggestions",
                kind=SceneNodeKind.RECTANGLE,
                bounds=popup,
                z_index=10,
                fill=self._popup_border,
                corner_radius=CornerRadius.uniform(7.0),
                hit_testable=False,
            )
        )
        inner = Rect(
            popup.x + 1.0,
            popup.y + 1.0,
            max(0.0, popup.width - 2.0),
            max(0.0, popup.height - 2.0),
        )
        root.add(
            SceneNode(
                key=f"{self.key}:suggestions:surface",
                kind=SceneNodeKind.RECTANGLE,
                bounds=inner,
                z_index=11,
                fill=self._popup_background,
                corner_radius=CornerRadius.uniform(6.0),
                hit_testable=False,
            )
        )

        for index, suggestion in enumerate(self._suggestions):
            y = inner.y + (index * row_height)
            row_bounds = Rect(
                inner.x,
                y,
                inner.width,
                min(row_height, max(0.0, inner.bottom - y)),
            )
            if index == self._selected_suggestion_index:
                root.add(
                    SceneNode(
                        key=f"{self.key}:suggestion:{index}:selected",
                        kind=SceneNodeKind.RECTANGLE,
                        bounds=row_bounds,
                        z_index=12,
                        fill=self._popup_selected,
                        hit_testable=False,
                    )
                )
            root.add(
                SceneNode(
                    key=f"{self.key}:suggestion:{index}",
                    kind=SceneNodeKind.TEXT,
                    bounds=Rect(
                        row_bounds.x + self._padding,
                        row_bounds.y,
                        max(0.0, row_bounds.width - (2.0 * self._padding)),
                        row_bounds.height,
                    ),
                    z_index=13,
                    fill=(
                        self._popup_selected_foreground
                        if index == self._selected_suggestion_index
                        else self._popup_foreground
                    ),
                    text=suggestion,
                    font_size=self._font_size,
                    font_family=self._font_family,
                    hit_testable=False,
                )
            )

        self._sync_autocomplete_accessibility()
        return root

    def _on_key_down(self, event: Event) -> None:
        platform_event = self._platform_event(event, PlatformEventKind.KEY_DOWN)
        if (
            not self.enabled
            or platform_event is None
            or platform_event.key_code is None
        ):
            return

        key = platform_event.key_code
        command_modifier = (
            platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
        )
        if command_modifier and key == _VK_SPACE:
            self.open_suggestions(force=True)
            if self._suggestions and self._selected_suggestion_index < 0:
                self._selected_suggestion_index = 0
                self._sync_autocomplete_accessibility()
                self.invalidate(reason="autocomplete_select")
            event.prevent_default()
            return

        if (
            not platform_event.ctrl
            and not platform_event.alt
            and not platform_event.meta
        ):
            if key in (_VK_DOWN, _VK_UP):
                if not self._suggestions_open:
                    self.open_suggestions(force=True)
                if self._suggestions:
                    direction = 1 if key == _VK_DOWN else -1
                    self._move_suggestion_selection(direction)
                event.prevent_default()
                return

            if key in (_VK_RETURN, _VK_TAB) and self.selected_suggestion is not None:
                self._accept_selected_suggestion(input_event=event)
                event.prevent_default()
                return

            if key == _VK_ESCAPE and self._suggestions_open:
                self.close_suggestions()
                event.prevent_default()
                return

        super()._on_key_down(event)

    def _on_focus_gained(self, event: Event) -> None:
        super()._on_focus_gained(event)
        if self._open_on_focus:
            self.open_suggestions(force=True)
        else:
            self.refresh_suggestions()
        self._sync_autocomplete_accessibility()

    def _on_focus_lost(self, event: Event) -> None:
        super()._on_focus_lost(event)
        self.close_suggestions()
        self._sync_autocomplete_accessibility()

    def _on_value_changed(self, _event: Event) -> None:
        self.refresh_suggestions()
        self._sync_autocomplete_accessibility()

    def _move_suggestion_selection(self, direction: int) -> None:
        if not self._suggestions:
            return
        count = len(self._suggestions)
        index = self._selected_suggestion_index
        index = (
            0 if direction > 0 else count - 1
        ) if index < 0 else (index + direction) % count
        if index == self._selected_suggestion_index:
            return
        self._selected_suggestion_index = index
        self._sync_autocomplete_accessibility()
        self.invalidate(reason="autocomplete_select")

    def _accept_selected_suggestion(self, *, input_event: Event) -> bool:
        suggestion = self.selected_suggestion
        if suggestion is None or self._read_only:
            return False

        old_value = self._value
        self.select(0, len(self._value))
        super()._replace_selection(suggestion, input_event=input_event)
        self.close_suggestions()
        if self._value != old_value:
            self.emit(
                "suggestion_accepted",
                suggestion=suggestion,
                old_value=old_value,
                value=self._value,
                input_event=input_event,
            )
        self._sync_autocomplete_accessibility()
        return True

    def _collect_suggestions(self, *, force: bool) -> tuple[str, ...]:
        prefix = self._value
        if not force and len(prefix) < self._minimum_prefix_length:
            return ()

        normalized_prefix = prefix if self._case_sensitive else prefix.casefold()
        current_identity = (
            self._value if self._case_sensitive else self._value.casefold()
        )
        candidates: list[str] = list(self._items)
        if self._provider is not None:
            provided = self._provider(self._value, self._caret)
            candidates.extend(
                str(item) for item in islice(provided, _MAX_PROVIDER_SCAN)
            )

        suggestions: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = str(candidate)
            if not normalized:
                continue
            identity = normalized if self._case_sensitive else normalized.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            if identity == current_identity:
                continue
            comparable = normalized if self._case_sensitive else normalized.casefold()
            if normalized_prefix and not comparable.startswith(normalized_prefix):
                continue
            suggestions.append(normalized)
            if len(suggestions) >= self._max_suggestions:
                break
        return tuple(suggestions)

    def _popup_row_height(self) -> float:
        return max(self._line_height(), self._font_size + 8.0)

    def _popup_bounds(self, row_height: float) -> Rect:
        height = (row_height * len(self._suggestions)) + 2.0
        return Rect(
            self.bounds.x,
            self.bounds.bottom + self._popup_gap,
            self.bounds.width,
            height,
        )

    def _sync_autocomplete_accessibility(self) -> None:
        selected = self.selected_suggestion
        if not self._suggestions_open:
            status = "suggestions closed"
        elif selected is None:
            status = f"{len(self._suggestions)} suggestions"
        else:
            status = (
                f"{len(self._suggestions)} suggestions; selected "
                f"{self._selected_suggestion_index + 1}: {selected}"
            )
        self.accessible_value_text = f"{len(self._value)} characters; {status}"

    @staticmethod
    def _normalize_items(value: Iterable[str]) -> tuple[str, ...]:
        return tuple(str(item) for item in value)

    @staticmethod
    def _validate_provider(
        value: AutocompleteProvider | None,
    ) -> AutocompleteProvider | None:
        if value is not None and not callable(value):
            raise TypeError("provider must be callable or None.")
        return value

    @staticmethod
    def _validate_minimum_prefix_length(value: int) -> int:
        normalized = int(value)
        if normalized < 0:
            raise ValueError("minimum_prefix_length must be non-negative.")
        return normalized

    @staticmethod
    def _validate_max_suggestions(value: int) -> int:
        normalized = int(value)
        if normalized < 1 or normalized > 32:
            raise ValueError("max_suggestions must be between 1 and 32.")
        return normalized


__all__ = ["Autocomplete", "AutocompleteProvider"]
