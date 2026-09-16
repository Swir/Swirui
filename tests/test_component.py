import pytest

from swirui.core import Component


def test_component_tree_and_walk() -> None:
    root = Component("root", key="root")
    left = Component("left", key="left")
    right = Component("right", key="right")
    leaf = Component("leaf", key="leaf")

    root.add(left, right)
    left.add(leaf)

    assert [component.key for component in root.walk()] == ["root", "left", "leaf", "right"]
    assert root.find("leaf") is leaf
    assert leaf.parent is left


def test_reparenting_is_automatic() -> None:
    first = Component("first")
    second = Component("second")
    child = Component("child")

    first.add(child)
    second.add(child)

    assert child.parent is second
    assert child not in first.children
    assert child in second.children


def test_component_cycle_is_rejected() -> None:
    root = Component("root")
    child = Component("child")
    root.add(child)

    with pytest.raises(ValueError, match="cycle"):
        child.add(root)
