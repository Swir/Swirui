import math

import pytest

from swirui import Window
from swirui.rendering import (
    Color,
    MeshGradient,
    Rect,
    Scene,
    SceneNode,
    SceneNodeKind,
    WgpuRenderer,
)


def _four_corner_mesh() -> MeshGradient:
    return MeshGradient.four_corner(
        Color(1.0, 0.0, 0.0),
        Color(0.0, 1.0, 0.0),
        Color(0.0, 0.0, 1.0),
        Color(1.0, 1.0, 1.0),
    )


def test_mesh_gradient_validation_and_bilinear_sampling() -> None:
    mesh = _four_corner_mesh()

    assert mesh.row_count == 2
    assert mesh.column_count == 2
    assert mesh.color_at(0.0, 0.0) == Color(1.0, 0.0, 0.0)
    assert mesh.color_at(1.0, 0.0) == Color(0.0, 1.0, 0.0)
    assert mesh.color_at(0.0, 1.0) == Color(0.0, 0.0, 1.0)
    assert mesh.color_at(1.0, 1.0) == Color(1.0, 1.0, 1.0)

    center = mesh.color_at(0.5, 0.5)
    assert center.r == pytest.approx(0.5)
    assert center.g == pytest.approx(0.5)
    assert center.b == pytest.approx(0.5)
    assert center.a == pytest.approx(1.0)
    assert mesh.color_at(-1.0, -2.0) == mesh.color_at(0.0, 0.0)
    assert mesh.color_at(2.0, 4.0) == mesh.color_at(1.0, 1.0)

    with pytest.raises(ValueError, match="two color rows"):
        MeshGradient(((Color(1.0, 0.0, 0.0), Color(0.0, 1.0, 0.0)),))
    with pytest.raises(ValueError, match="two color columns"):
        MeshGradient(((Color(1.0, 0.0, 0.0),), (Color(0.0, 1.0, 0.0),)))
    with pytest.raises(ValueError, match="same length"):
        MeshGradient(
            (
                (Color(1.0, 0.0, 0.0), Color(0.0, 1.0, 0.0)),
                (Color(0.0, 0.0, 1.0), Color(1.0, 1.0, 1.0), Color(0.0, 0.0, 0.0)),
            )
        )
    with pytest.raises(ValueError, match="finite"):
        mesh.color_at(math.inf, 0.5)


def test_mesh_gradient_builds_control_aligned_retained_quads() -> None:
    mesh = MeshGradient(
        (
            (
                Color.from_hex("#00D9FF"),
                Color.from_hex("#3157E8"),
                Color.from_hex("#8B5CF6"),
            ),
            (
                Color.from_hex("#0F172A"),
                Color.from_hex("#4F46E5"),
                Color.from_hex("#EC4899"),
            ),
            (
                Color.from_hex("#111827"),
                Color.from_hex("#0EA5E9"),
                Color.from_hex("#7C3AED"),
            ),
        )
    )
    bounds = Rect(30.0, 20.0, 480.0, 300.0)
    node = mesh.to_scene_node("mesh-panel", bounds, subdivisions=4, opacity=0.75, z_index=3)

    assert node.kind is SceneNodeKind.GROUP
    assert node.bounds == bounds
    assert node.clip_to_bounds
    assert node.opacity == pytest.approx(0.75)
    assert node.z_index == 3
    assert len(node.children) == 64
    assert all(child.kind is SceneNodeKind.PATH for child in node.children)
    assert all(child.key == "mesh-panel" for child in node.children)
    assert all(child.path is not None for child in node.children)
    assert sum(child.path.triangle_count for child in node.children if child.path) == 128

    for child in node.children:
        assert child.path is not None
        for point in child.path.points:
            assert 0.0 <= point.x <= bounds.width
            assert 0.0 <= point.y <= bounds.height
            assert math.isfinite(point.x)
            assert math.isfinite(point.y)

    with pytest.raises(ValueError, match="subdivisions"):
        mesh.to_scene_node("too-coarse", bounds, subdivisions=0)
    with pytest.raises(ValueError, match="subdivisions"):
        mesh.to_scene_node("too-dense", bounds, subdivisions=33)


def test_mesh_gradient_scene_preserves_stable_hit_key() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 420.0, 260.0),
    )
    root.add(_four_corner_mesh().to_scene_node("mesh-card", Rect(50.0, 40.0, 320.0, 170.0)))
    scene = Scene(420.0, 260.0, root)

    target = scene.hit_test_xy(180.0, 120.0)
    assert target is not None
    assert target.key == "mesh-card"
    assert target.kind is SceneNodeKind.PATH


def test_mesh_gradient_flows_into_existing_wgpu_path_preparation() -> None:
    root = SceneNode(
        key="root",
        kind=SceneNodeKind.GROUP,
        bounds=Rect(0.0, 0.0, 520.0, 340.0),
    )
    root.add(
        _four_corner_mesh().to_scene_node(
            "gpu-mesh",
            Rect(40.0, 50.0, 440.0, 240.0),
            subdivisions=5,
        )
    )

    window = Window(width=520, height=340)
    window.set_scene(Scene(520.0, 340.0, root))
    vertices = WgpuRenderer()._path_vertices(window)

    assert len(vertices) == 25 * 2 * 3
    assert all(len(vertex) == 10 for vertex in vertices)
    assert all(math.isfinite(value) for vertex in vertices for value in vertex)
