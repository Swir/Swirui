from swirui import FUTURE_LIGHT, NEON_BLUE, ThemePackage, Window, mount
from swirui import __main__ as cli
from swirui import studio_comparison as comparison_module
from swirui import studio_suite as studio_module
from swirui.platforms import NativeWindowHandle, PlatformEvent, PlatformEventKind, PointerButton
from swirui.rendering import Rect
from swirui.studio import Studio
from swirui.widgets import compile_component_scene


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


def test_preview_theme_lists_and_validates_files_without_graphics(tmp_path, capsys, monkeypatch):
    def unexpected_renderer_check():
        raise AssertionError("Listing and validating a file must precede the graphics check")

    monkeypatch.setattr(cli, "installation_report", unexpected_renderer_check)
    path = tmp_path / "Mój motyw.json"
    ThemePackage("Custom", {"day": FUTURE_LIGHT, "night": NEON_BLUE}, "night").save(path)
    command = ["preview-theme", str(path)]
    assert cli.main([*command, "--list-variants"]) == 0
    assert capsys.readouterr().out.splitlines() == ["day", "night (default)"]
    for keys, message in ((["typo"], "Unknown variant"), (["day", "day"], "distinct"),
                          (["day", "night", "day"], "one or two")):
        flags = [part for key in keys for part in ("--variant", key)]
        assert cli.main([*command, *flags]) == 1
        assert message in capsys.readouterr().err
    path.write_text("{}", encoding="utf-8")
    assert cli.main(command) == 1 and "Theme package" in capsys.readouterr().err
    assert cli.main(["preview-theme", str(tmp_path / "missing.json")]) == 1
    assert "missing.json" in capsys.readouterr().err


def test_preview_theme_shows_default_first_and_respects_a_single_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "installation_report", lambda: {"ready": True})
    roots = []

    def capture(root, *, smoke_test, source, pane_limit):
        assert source == path and pane_limit in (1, 2)
        roots.append(root)
        return 0

    monkeypatch.setattr(comparison_module, "run_package_preview", capture)
    path = tmp_path / "saved.json"
    ThemePackage("Custom", {"day": FUTURE_LIGHT, "night": NEON_BLUE}, "night").save(path)
    command = ["preview-theme", str(path)]
    assert cli.main(command) == 0
    assert [pane.mode for pane in roots[-1].panes] == ["night", "day"]
    assert cli.main([*command, "--variant", "day"]) == 0
    pane, = roots[-1].panes
    roots[-1].prepare_layout(Rect(0, 0, 480, 460))
    assert pane.theme == FUTURE_LIGHT and pane.bounds.width == 480
    ThemePackage("Solo", {"solo": NEON_BLUE}, "solo").save(path)
    assert cli.main(command) == 0
    assert [pane.mode for pane in roots[-1].panes] == ["solo"]


def test_reload_saved_package_keeps_surviving_drafts_and_rebuilds_variant_choices(tmp_path):
    path = tmp_path / "motyw.json"
    first = ThemePackage("Initial", {"night": NEON_BLUE, "day": FUTURE_LIGHT}, "night")
    first.save(path)
    root = comparison_module.AppearanceComparison(first, "Project settings",
                                                  variants=("night", "day"))
    window = Window()
    mount(window, root)
    comparison_module.bind_package_reload(window, root, path, pane_limit=2)
    night, day = root.panes
    day.field.value = "Draft project"
    day.field.select(8, 1)
    window.focus_component(day.field)

    def reload():
        window._apply_platform_event(PlatformEvent(PlatformEventKind.KEY_DOWN,
                                                  NativeWindowHandle(1), key_code=0x74))

    path.write_text("{", encoding="utf-8")
    reload()
    assert "F5 to retry" in window.title and root.panes == (night, day)
    assert window.focused_component is day.field and day.field.caret_index == 1
    copper = FUTURE_LIGHT.with_accent("#D16C42")
    ThemePackage("Copper", {"day": copper}, "day").save(path)
    reload()
    assert root.panes == (day,) and day.theme == copper and "Copper" in window.title
    assert day.field.value == "Draft project" and day.field.selected_text == "raft pr"
    assert window.focused_component is day.field and day.field.caret_index == 1
    ThemePackage("Three", {"sand": FUTURE_LIGHT, "day": copper, "ink": NEON_BLUE}, "ink").save(path)
    reload()
    assert root.panes[0] is day and [p.mode for p in root.panes] == ["day", "ink"]
    day.mode_label.emit("click")
    assert [item.key for item in root._variant_dialog.search.items] == ["day", "sand"]
    ThemePackage("Two", {"sand": FUTURE_LIGHT, "ink": NEON_BLUE}, "ink").save(path)
    reload()
    assert root._variant_dialog is None and [p.mode for p in root.panes] == ["sand", "ink"]
    assert window.focused_component is day.field and day.field.caret_index == 1


def test_reload_uses_the_backend_f5_without_intercepting_typing_or_modified_shortcuts(tmp_path):
    path = tmp_path / "Atelier.json"
    original = ThemePackage("Before", {"ink": NEON_BLUE}, "ink")
    ThemePackage("After", {"ink": FUTURE_LIGHT}, "ink").save(path)
    for backend, f5, other in (("win32", 0x74, 0x54), ("x11", 0xFFC2, ord("t")),
                               ("cocoa", 0x60, 0x74)):
        root = comparison_module.AppearanceComparison(original, "Settings", variants=("ink",))
        window = Window()
        mount(window, root)
        comparison_module.bind_package_reload(window, root, path, pane_limit=1,
                                              backend_name=backend)
        for key, ctrl in ((other, False), (f5, True), (f5, False)):
            window._apply_platform_event(PlatformEvent(PlatformEventKind.KEY_DOWN,
                                                      NativeWindowHandle(1), key_code=key,
                                                      ctrl=ctrl))
            assert root.panes[0].theme == (FUTURE_LIGHT if key == f5 and not ctrl else NEON_BLUE)
        assert window.focused_component is None


def test_comparison_reflows_both_forms_at_the_minimum_width_and_restores_them():
    package = ThemePackage("Field notes", {"paper": FUTURE_LIGHT, "ink": NEON_BLUE}, "paper")
    root = comparison_module.AppearanceComparison(package, "Project settings",
                                                  variants=("ink", "paper"))
    first, second = root.panes
    second.field.value = "Unsubmitted edit"
    second.field.select(12, 4)
    for width, height in ((960, 460), (639, 390), (320, 390), (420, 840), (640, 390)):
        scene = compile_component_scene(root, width=width, height=height)
        if width < 640:
            assert first.bounds.bottom == second.bounds.y
            assert first.bounds.width == second.bounds.width == width
        else:
            assert first.bounds.right == second.bounds.x
            assert first.bounds.height == second.bounds.height == height
        for pane in root.panes:
            if pane.bounds.height < 370:
                assert pane.title.bounds.right < pane.mode_label.bounds.x
                assert pane.title.bounds.bottom <= pane.ribbon.bounds.y
                assert pane.field.bounds.right < pane.apply.bounds.x
                assert pane.field.bounds.y == pane.apply.bounds.y
            for widget in (pane.mode_label, pane.title, pane.card, pane.headline,
                           pane.caption, pane.field, pane.apply, pane.disable_form):
                b = widget.bounds
                assert pane.bounds.x <= b.x < b.right <= pane.bounds.right
                assert pane.bounds.y <= b.y < b.bottom <= pane.bounds.bottom
            assert scene.hit_test_xy(pane.apply.bounds.x + 20,
                                     pane.apply.bounds.y + 18).key == pane.apply.key
            check = pane.disable_form.bounds
            assert scene.hit_test_xy(check.x + 10, check.y + check.height / 2).key == (
                pane.disable_form.key
            )
        assert second.field.value == "Unsubmitted edit" and second.field.caret_index == 4
        assert second.field.selected_text == "bmitted "


def test_long_comparison_titles_fit_each_pane_without_renaming_the_project():
    name = "Pracownia Światła Północy"
    headline = "Powierzchnie ze szkła i satyny"
    package = ThemePackage(name, {"dark": NEON_BLUE, "light": FUTURE_LIGHT}, "dark")
    root = comparison_module.AppearanceComparison(package, headline)
    for width in (1100, 680, 320, 1100):
        compile_component_scene(root, width=width, height=460)
        for pane in root.panes:
            for label, text in ((pane.title, name), (pane.headline, headline)):
                node = label.build_scene_node()
                assert label.min_font_size <= node.font_size <= label.font_size
                assert node.text == label.accessible_name == text
                if width == 1100:
                    assert node.font_size == label.font_size
                if width == 680:
                    assert node.font_size < label.font_size
            assert pane.field.value == name


def test_disabled_preview_is_local_and_focus_survives_package_changes():
    package = ThemePackage("Workshop", {"ink": NEON_BLUE, "paper": FUTURE_LIGHT}, "ink")
    root = comparison_module.AppearanceComparison(package, "Settings", variants=("ink", "paper"))
    window = Window(width=320, height=390)
    mount(window, root)
    ink, paper = root.panes
    ink.field.value = "Unsubmitted draft"
    window.focus_component(ink.field)
    ink.disable_form.checked = True
    assert window.focused_component is ink.disable_form
    assert not ink.field.enabled and not ink.apply.enabled
    assert paper.field.enabled and paper.apply.enabled
    b = ink.apply.bounds
    for kind in (PlatformEventKind.POINTER_DOWN, PlatformEventKind.POINTER_UP):
        window._apply_platform_event(PlatformEvent(kind, NativeWindowHandle(1),
                                                  x=b.x + b.width / 2, y=b.y + b.height / 2,
                                                  button=PointerButton.LEFT))
    assert ink.title.text == paper.title.text == "Workshop"
    window.focus_component(ink.disable_form)
    assert window.focus_next() is paper.field
    assert window.focus_next(reverse=True) is ink.disable_form
    assert window.focus_next(reverse=True) is paper.disable_form

    # Reload while the focused pane disappears. The survivor's field is disabled.
    solo = ThemePackage("Updated", {"ink": FUTURE_LIGHT}, "ink")
    root._reload_package(solo, pane_limit=2)
    assert root.panes == (ink,) and ink.disable_form.checked
    assert window.focused_component is ink.disable_form
    assert ink.field.value == "Unsubmitted draft" and ink.theme == FUTURE_LIGHT
    for kind in (PlatformEventKind.KEY_DOWN, PlatformEventKind.KEY_UP):
        window._apply_platform_event(PlatformEvent(kind, NativeWindowHandle(1), key_code=0x20))
    assert ink.field.enabled and ink.apply.enabled and not ink.disable_form.checked
    assert window.focus_next() is ink.field


def test_variant_search_reaches_last_of_32_and_escape_restores_focus():
    package = ThemePackage("Library", {f"finish-{i}": NEON_BLUE for i in range(32)}, "finish-0")
    root = comparison_module.AppearanceComparison(package, "Settings", variants=("finish-0",))
    window = Window(width=320, height=390)
    mount(window, root)
    pane, = root.panes
    pane.mode_label.emit("click")
    dialog = root._variant_dialog
    assert dialog.search is window.focused_component
    assert len(dialog.search.items) == 32
    dialog.search.set_query("missing")
    assert any(n.text == "No matching variants" for n in window.scene.walk())
    window._apply_platform_event(PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1),
                                              key_code=0x1B))
    assert root._variant_dialog is None and pane.mode == "finish-0"
    assert window.focused_component is pane.mode_label
    pane.mode_label.emit("click")
    palette = window.focused_component
    assert palette.query == ""
    palette.set_query("finish-31")
    window._apply_platform_event(PlatformEvent(PlatformEventKind.KEY_DOWN, NativeWindowHandle(1),
                                              key_code=0x0D))
    assert pane.mode == "finish-31" and window.focused_component is pane.mode_label
    assert pane.field.accessible_name == "Finish-31 preview project name"
