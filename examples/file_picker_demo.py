"""Interactive retained FilePicker and FolderPicker demo."""

from pathlib import Path

from swirui import App, FileFilter, FilePicker, FolderPicker, Panel, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App("SwirUI File Pickers")
    window = app.add_window(
        Window(title="SwirUI Professional File Pickers", width=1120, height=660)
    )
    root = Panel(bounds=Rect(0.0, 0.0, 1120.0, 660.0), key="file-picker-demo")

    files = FilePicker(
        bounds=Rect(40.0, 50.0, 500.0, 550.0),
        directory=Path.cwd(),
        filters=(
            FileFilter("Python", ("*.py",)),
            FileFilter("Documents", ("*.md", "*.txt", "*.json")),
        ),
        key="demo-files",
    )
    folders = FolderPicker(
        bounds=Rect(580.0, 50.0, 500.0, 550.0),
        directory=Path.cwd(),
        key="demo-folders",
    )
    files.on("selection_confirmed", lambda event: print("File:", event.data["path"]))
    folders.on("selection_confirmed", lambda event: print("Folder:", event.data["path"]))
    root.add(files, folders)
    mount(window, root)
    app.run()


if __name__ == "__main__":
    main()
