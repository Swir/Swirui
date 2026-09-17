"""Backend-neutral accessibility semantics for SwirUI components.

This module defines semantic information that native accessibility adapters can
consume without coupling the component tree to one operating-system API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component import Component


class AccessibilityRole(StrEnum):
    """Framework roles mapped to platform accessibility APIs by native adapters."""

    GENERIC = "generic"
    GROUP = "group"
    BUTTON = "button"
    CHECKBOX = "checkbox"
    CHIP = "chip"
    IMAGE = "image"
    LINK = "link"
    LIST = "list"
    LIST_ITEM = "list_item"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    PASSWORD_BOX = "password_box"
    PROGRESS_BAR = "progress_bar"
    RADIO = "radio"
    SLIDER = "slider"
    SWITCH = "switch"
    TEXT = "text"
    TEXT_BOX = "text_box"
    TOOLTIP = "tooltip"


@dataclass(frozen=True, slots=True)
class AccessibilityNode:
    """Immutable semantic snapshot of one visible component subtree."""

    key: str
    role: AccessibilityRole
    name: str
    description: str | None
    enabled: bool
    focusable: bool
    focused: bool
    checked: bool | None = None
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    value_text: str | None = None
    children: tuple[AccessibilityNode, ...] = ()

    def find(self, key: str) -> AccessibilityNode | None:
        """Find a semantic node by stable component key."""

        if self.key == key:
            return self
        for child in self.children:
            if match := child.find(key):
                return match
        return None


def build_accessibility_tree(
    root: Component | None,
    *,
    focused: Component | None = None,
) -> AccessibilityNode | None:
    """Build a visible semantic tree from a component hierarchy."""

    if root is None or not root.visible:
        return None

    children = tuple(
        node
        for child in root.children
        if (node := build_accessibility_tree(child, focused=focused)) is not None
    )
    return AccessibilityNode(
        key=root.key,
        role=root.accessibility_role,
        name=root.accessible_name or root.name,
        description=root.accessible_description,
        enabled=root.enabled,
        focusable=root.focusable,
        focused=root is focused,
        checked=root.accessible_checked,
        value=root.accessible_value,
        min_value=root.accessible_min_value,
        max_value=root.accessible_max_value,
        value_text=root.accessible_value_text,
        children=children,
    )
