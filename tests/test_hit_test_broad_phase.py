from swirui.rendering import Color, Point, Rect, SceneNode, SceneNodeKind


def _rectangle(key: str, bounds: Rect, *, z_index: int = 0) -> SceneNode:
    return SceneNode(
        key=key,
        kind=SceneNodeKind.RECTANGLE,
        bounds=bounds,
        fill=Color.from_hex("#4499CC"),
        z_index=z_index,
    )


def test_hit_path_keeps_topmost_z_order_after_leaf_culling() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 500, 500))
    root.add(
        _rectangle("far-away", Rect(300, 300, 40, 40), z_index=100),
        _rectangle("bottom", Rect(10, 10, 100, 100), z_index=1),
        _rectangle("top", Rect(10, 10, 100, 100), z_index=5),
    )

    path = root.hit_path(Point(40, 40))

    assert tuple(node.key for node in path) == ("root", "top")


def test_unclipped_parent_can_hit_descendant_outside_parent_bounds() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 500, 500))
    group = SceneNode("group", SceneNodeKind.GROUP, Rect(10, 10, 20, 20))
    outside_child = _rectangle("outside-child", Rect(120, 120, 40, 40))
    group.add(outside_child)
    root.add(group)

    path = root.hit_path(Point(130, 130))

    assert tuple(node.key for node in path) == ("root", "group", "outside-child")


def test_clipped_parent_prunes_descendant_outside_parent_bounds() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 500, 500))
    group = SceneNode(
        "group",
        SceneNodeKind.GROUP,
        Rect(10, 10, 20, 20),
        clip_to_bounds=True,
    )
    group.add(_rectangle("outside-child", Rect(120, 120, 40, 40)))
    root.add(group)

    assert root.hit_test(Point(130, 130)) is None


def test_zero_opacity_subtree_is_ignored_before_hit_routing() -> None:
    root = SceneNode("root", SceneNodeKind.GROUP, Rect(0, 0, 500, 500))
    invisible = SceneNode(
        "invisible",
        SceneNodeKind.GROUP,
        Rect(0, 0, 500, 500),
        opacity=0.0,
    )
    invisible.add(_rectangle("hidden-child", Rect(20, 20, 100, 100), z_index=99))
    root.add(invisible, _rectangle("visible", Rect(20, 20, 100, 100), z_index=1))

    hit = root.hit_test(Point(30, 30))

    assert hit is not None
    assert hit.key == "visible"
