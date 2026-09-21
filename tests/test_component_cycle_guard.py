from __future__ import annotations

import pytest

from swirui.core import Component


class _PointHelperComponent(Component):
    @staticmethod
    def _contains(bounds: object, x: float, y: float) -> bool:
        del bounds, x, y
        return False


def test_cycle_guard_is_independent_from_subclass_contains_helpers() -> None:
    root = Component("root")
    child = _PointHelperComponent("child")

    root.add(child)

    assert child.parent is root
    with pytest.raises(ValueError, match="cycle"):
        child.add(root)
