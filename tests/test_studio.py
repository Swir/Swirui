from swirui import FUTURE_LIGHT
from swirui import __main__ as cli
from swirui import studio as studio_module
from swirui.rendering import Rect
from swirui.studio import Studio


def test_studio_integrates_preview_code_assets_hierarchy_inspector_and_console() -> None:
    studio = Studio()

    assert tuple(pane.key for pane in studio.workspace.panes) == (
        "hierarchy",
        "inspector",
        "console",
        "preview",
        "code",
        "assets",
    )
    assert studio.workspace.active_center_key == "preview"
    assert studio.preview.material == "glass"
    assert studio.preview.depth == 3
    assert not studio.light

    studio.inspector.set_value("title", "Neon command center")
    studio.inspector.set_value("material", "acrylic")
    studio.inspector.set_value("depth", 6)

    assert studio.preview.heading.text == "Neon command center"
    assert studio.preview.material == "acrylic"
    assert studio.preview.depth == 6
    assert studio.preview.theme.surface_style.kind == "acrylic"
    assert studio.preview.theme.surface_style.depth_layers == 6

    studio.activate("code")
    assert studio.workspace.active_center_key == "code"
    assert studio.active.text == "CODE"
    assert studio.code_button.variant.value == "primary"

    studio.activate("assets")
    assert studio.workspace.active_center_key == "assets"
    assert studio.assets.selected_index == 0
    assert studio.assets.selected_row is not None
    assert studio.assets.selected_row["id"] == 0

    studio.activate("preview")
    assert studio.workspace.active_center_key == "preview"
    assert studio.preview.heading.text == "Neon command center"


def test_studio_resizes_as_one_retained_workspace_and_preserves_preview_state() -> None:
    studio = Studio()
    studio.preview.project.value = "Persistent user project"
    studio.preview.project.select(0, 10)
    studio.inspector.set_value("material", "solid")

    for width, height in ((1024, 720), (1600, 1000), (1280, 800)):
        studio.resize_to(width, height)
        studio.workspace.prepare_layout(studio.workspace.bounds)
        studio.preview.prepare_layout(studio.preview.bounds)

        assert studio.bounds == Rect(0, 0, width, height)
        assert studio.workspace.bounds.right <= width
        assert studio.workspace.bounds.bottom <= height
        assert studio.preview.surface.bounds.right <= studio.preview.bounds.right
        assert studio.preview.footer.bounds.bottom <= studio.preview.bounds.bottom
        assert studio.preview.project.value == "Persistent user project"
        assert studio.preview.project.selected_text == "Persistent"
        assert studio.preview.material == "solid"


def test_studio_commands_switch_views_theme_and_reset_preview() -> None:
    studio = Studio()
    studio.preview.project.value = "Custom draft"
    studio.inspector.set_value("title", "Custom headline")
    studio.inspector.set_value("material", "acrylic")
    studio.inspector.set_value("depth", 7)

    studio.execute_command("code")
    assert studio.workspace.active_center_key == "code"

    studio.execute_command("theme")
    assert studio.light
    assert studio.preview.light
    assert studio.theme == FUTURE_LIGHT

    studio.execute_command("reset")
    assert studio.preview.heading.text == "Build beyond ordinary."
    assert studio.preview.material == "glass"
    assert studio.preview.depth == 3
    assert studio.preview.project.value == "Neon workspace"

    studio.execute_command("assets")
    assert studio.workspace.active_center_key == "assets"
    studio.execute_command("preview")
    assert studio.workspace.active_center_key == "preview"


def test_studio_preview_launch_message_requires_a_project_name() -> None:
    studio = Studio()

    studio.preview.project.value = "Orbit dashboard"
    studio.preview.create.emit("click")
    assert studio.preview.result.text == "Orbit dashboard is ready to render."

    studio.preview.project.value = " "
    studio.preview.create.emit("click")
    assert studio.preview.result.text == "Name the project before launch."


def test_cli_dispatches_integrated_studio_smoke_test(monkeypatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr(cli, "installation_report", lambda: {"ready": True})
    monkeypatch.setattr(
        studio_module,
        "run",
        lambda *, smoke_test=False: called.append(smoke_test) or 0,
    )

    assert cli.main(["studio", "--smoke-test"]) == 0
    assert called == [True]
