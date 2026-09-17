from swirui import AccessibilityRole, Component, build_accessibility_tree


def test_accessibility_tree_exposes_role_labels_state_and_focus() -> None:
    root = Component(
        "settings",
        key="root",
        accessibility_role=AccessibilityRole.GROUP,
        accessible_name="Settings",
    )
    button = Component(
        "save-button",
        key="save",
        focusable=True,
        accessibility_role=AccessibilityRole.BUTTON,
        accessible_name="Save changes",
        accessible_description="Writes the current settings to disk.",
    )
    root.add(button)

    tree = build_accessibility_tree(root, focused=button)

    assert tree is not None
    assert tree.role is AccessibilityRole.GROUP
    assert tree.name == "Settings"
    save = tree.find("save")
    assert save is not None
    assert save.role is AccessibilityRole.BUTTON
    assert save.name == "Save changes"
    assert save.description == "Writes the current settings to disk."
    assert save.enabled is True
    assert save.focusable is True
    assert save.focused is True


def test_component_name_is_accessible_name_fallback() -> None:
    component = Component("Readable fallback", key="fallback")

    tree = build_accessibility_tree(component)

    assert tree is not None
    assert tree.name == "Readable fallback"
    assert tree.role is AccessibilityRole.GENERIC


def test_invisible_component_prunes_its_full_semantic_subtree() -> None:
    root = Component("root", key="root")
    hidden_group = Component("hidden", key="hidden")
    hidden_group.visible = False
    hidden_group.add(
        Component(
            "secret",
            key="secret",
            accessibility_role=AccessibilityRole.TEXT,
        )
    )
    visible = Component(
        "visible",
        key="visible",
        accessibility_role=AccessibilityRole.TEXT,
    )
    root.add(hidden_group, visible)

    tree = build_accessibility_tree(root)

    assert tree is not None
    assert tree.find("hidden") is None
    assert tree.find("secret") is None
    assert tree.find("visible") is not None


def test_disabled_component_remains_semantic_but_reports_disabled_state() -> None:
    root = Component("root")
    disabled = Component(
        "Unavailable action",
        key="disabled",
        accessibility_role=AccessibilityRole.BUTTON,
    )
    disabled.enabled = False
    root.add(disabled)

    tree = build_accessibility_tree(root)

    assert tree is not None
    node = tree.find("disabled")
    assert node is not None
    assert node.enabled is False


def test_none_or_invisible_root_has_no_accessibility_tree() -> None:
    assert build_accessibility_tree(None) is None

    root = Component("hidden-root")
    root.visible = False
    assert build_accessibility_tree(root) is None
