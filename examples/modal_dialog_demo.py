"""Retained Modal/Dialog demo with focus trapping and dismissal behavior."""

from swirui import Button, Component, Dialog, Window, mount
from swirui.rendering import Rect


def build_demo(window: Window) -> tuple[Component, Dialog]:
    root = Component("root")
    launch = Button(
        "Open dialog",
        key="launch-dialog",
        bounds=Rect(36.0, 36.0, 160.0, 46.0),
    )

    dialog_content = Component("dialog-content")
    confirm = Button(
        "Confirm",
        key="confirm-dialog",
        bounds=Rect(24.0, 92.0, 130.0, 44.0),
    )
    cancel = Button(
        "Cancel",
        key="cancel-dialog",
        bounds=Rect(170.0, 92.0, 130.0, 44.0),
    )
    dialog_content.add(confirm, cancel)

    dialog = Dialog(
        key="settings-dialog",
        bounds=Rect(0.0, 0.0, float(window.width), float(window.height)),
        dialog_bounds=Rect(180.0, 105.0, 350.0, 180.0),
        content=dialog_content,
        initially_open=False,
        accessible_name="Confirm settings",
    )

    launch.on("click", lambda _event: dialog.show(reason="launch-button"))
    confirm.on("click", lambda _event: dialog.dismiss(reason="confirm"))
    cancel.on("click", lambda _event: dialog.dismiss(reason="cancel"))
    root.add(launch, dialog)
    return root, dialog


def main() -> None:
    window = Window(title="SwirUI Modal/Dialog demo", width=720, height=420)
    root, _dialog = build_demo(window)
    mount(window, root)
    print(
        "Modal/Dialog scene prepared. Tab remains inside the open dialog; "
        "Escape or a scrim click dismisses it and restores previous focus."
    )


if __name__ == "__main__":
    main()
