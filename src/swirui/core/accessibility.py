"""Backend-neutral accessibility semantics for SwirUI components.

This module defines the semantic information that native accessibility adapters
will consume later. It does not claim screen-reader integration by itself; it
provides a stable, testable component-to-semantic-tree contract first.
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
    IMAGE = "image"
    LINK = "link"
    LIST = "list"
    LIST_ITEM = "list_item"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    RADIO = "radio"
    SLIDER = "slider"
    SWITCH = "switch"
    TEXT = "text"
    TEXT_BOX = "text_box"


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
    """Build a visible semantic tree from a component hierarchy.

    Invisible components prune their full subtree because descendants cannot be
    reached visually or through the current focus contract. Component names are
    used as a deterministic fallback when no explicit accessible name is set.
    """

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
        children=children,
    )
