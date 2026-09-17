"""Interactive retained modal Dialog demo.

Run on Windows with the native renderer installed::

    python examples/core_dialog_demo.py
"""

from __future__ import annotations

from swirui import App, Button, Component, Dialog, Label, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App("SwirUI Dialog Demo")
    window = Window("SwirUI Modal / Dialog", width=760, height=460)

    root = Component("dialog-demo", key="dialog-demo")
    heading = Label(
        "Retained modal focus containment",
        key="heading",
        bounds=Rect(40.0, 42.0, 520.0, 34.0),
        font_size=24.0,
    )
    status = Label(
        "Open the dialog, then try Tab / Shift+Tab / Escape.",
        key="status",
        bounds=Rect(40.0, 92.0, 620.0, 28.0),
    )
    open_button = Button(
        "Open dialog",
        key="open-dialog",
        bounds=Rect(40.0, 150.0, 180.0, 46.0),
    )

    dialog = Dialog(
        "Save changes?",
        key="save-dialog",
        bounds=Rect(0.0, 0.0, 760.0, 460.0),
        panel_bounds=Rect(190.0, 105.0, 380.0, 240.0),
        accessible_description="Choose whether to save the current changes.",
    )
    prompt = Label(
        "Your changes are ready to be saved.",
        key="dialog-prompt",
        bounds=Rect(24.0, 72.0, 330.0, 28.0),
    )
    cancel = Button(
        "Cancel",
        key="dialog-cancel",
        bounds=Rect(76.0, 154.0, 105.0, 42.0),
    )
    save = Button(
        "Save",
        key="dialog-save",
        bounds=Rect(199.0, 154.0, 105.0, 42.0),
    )
    dialog.add(prompt, cancel, save)
    root.add(heading, status, open_button, dialog)

    def open_modal(_event: object) -> None:
        dialog.open(window, initial_focus=cancel)

    def cancel_modal(_event: object) -> None:
        dialog.cancel()
        status.text = "Dialog cancelled. Focus returned to Open dialog."

    def accept_modal(_event: object) -> None:
        dialog.accept()
        status.text = "Changes saved. Focus returned to Open dialog."

    open_button.on("click", open_modal)
    cancel.on("click", cancel_modal)
    save.on("click", accept_modal)

    app.add_window(window)
    mount(window, root)
    app.run()


if __name__ == "__main__":
    main()
