"""Native professional workspace with live themes and retained sample data."""

from swirui import (
    FUTURE_DARK,
    FUTURE_LIGHT,
    App,
    Badge,
    Button,
    ButtonVariant,
    CommandItem,
    CommandPalette,
    DataGrid,
    DataGridColumn,
    Input,
    Label,
    ListItem,
    ListView,
    Modal,
    NavigationItem,
    Panel,
    Sidebar,
    TabItem,
    Tabs,
    TreeNode,
    TreeView,
    Window,
    mount,
    state_transaction,
)
from swirui.core import Event
from swirui.platforms import PlatformEvent, PlatformEventKind
from swirui.rendering import Rect, WgpuRenderer


class Workspace(Panel):
    def __init__(self) -> None:
        super().__init__(bounds=Rect(0, 0, 1280, 840), theme=FUTURE_DARK)
        self.mode = Button(
            "Light theme", bounds=Rect(1096, 30, 152, 40), variant=ButtonVariant.SECONDARY
        )
        self.mode.on("click", lambda _: self.toggle_theme())
        self.commands = Button(
            "Commands · Ctrl+K", bounds=Rect(884, 30, 196, 40), variant=ButtonVariant.SECONDARY
        )
        self.commands.on("click", lambda _: self.open_commands())
        self.sidebar = Sidebar(
            [
                NavigationItem("projects", "Projects"),
                NavigationItem("assets", "Asset library"),
                NavigationItem("files", "Project files"),
            ],
            bounds=Rect(24, 160, 196, 520),
            item_height=50,
        )
        self.search = Input(bounds=Rect(854, 154, 394, 42), placeholder="Filter projects by name")
        self.search.on("changed", lambda _: self.filter_projects())
        names = ("Aurora", "Orbit", "Prism", "Horizon", "Atlas", "Sora", "Nova", "Solstice")
        rows = [
            {
                "id": i,
                "name": f"{names[i % 8]} / {i // 8 + 1:02}",
                "team": ("Design", "Platform", "Research")[i % 3],
                "status": ("In progress", "Ready", "Draft")[i % 3],
                "updated": "Today" if i < 8 else "Yesterday",
            }
            for i in range(80)
        ]
        self.grid = DataGrid(
            [
                DataGridColumn("name", "PROJECT", width=360),
                DataGridColumn("team", "TEAM", width=210),
                DataGridColumn("status", "STATUS", width=210),
                DataGridColumn("updated", "UPDATED", width=180),
            ],
            rows,
            bounds=Rect(0, 0, 988, 530),
            row_key="id",
            selection_mode="multiple",
            editable_columns=["name"],
            row_height=44,
            header_height=44,
        )
        self.grid.select_row(1)
        self.assets = ListView(
            [
                ListItem(
                    i,
                    f"{names[i % 8]} — visual exploration {i + 1:03}",
                    ("Illustration", "Icon collection", "Motion study")[i % 3],
                )
                for i in range(2000)
            ],
            bounds=Rect(0, 0, 988, 530),
            item_height=46,
            selection_mode="multiple",
        )
        self.assets.select_index(2)
        self.tree = TreeView(
            [
                TreeNode(
                    "workspace",
                    "Workspace",
                    (
                        TreeNode(
                            "src",
                            "src",
                            (
                                TreeNode("app", "app.py"),
                                TreeNode("theme", "theme.py"),
                                TreeNode("views", "views"),
                            ),
                        ),
                        TreeNode(
                            "assets",
                            "assets",
                            (TreeNode("icons", "icons"), TreeNode("images", "images")),
                        ),
                        TreeNode("tests", "tests"),
                        TreeNode("config", "pyproject.toml"),
                    ),
                )
            ],
            bounds=Rect(0, 0, 988, 530),
            expanded_keys=["workspace", "src", "assets"],
            item_height=44,
        )
        self.tabs = Tabs(
            [
                TabItem("projects", "Projects", self.grid),
                TabItem("assets", "Asset library", self.assets),
                TabItem("files", "Project files", self.tree),
            ],
            bounds=Rect(260, 232, 988, 540),
            header_height=48,
        )
        self.sidebar.on(
            "selection_changed", lambda _: self.tabs.select_key(self.sidebar.selected_key)
        )
        self.hint = Label("", bounds=Rect(260, 794, 988, 28), font_size=13)
        self.tabs.on("selection_changed", lambda _: self.sync_page())
        self.palette = CommandPalette(
            [
                CommandItem("theme", "Switch light / dark theme"),
                CommandItem("projects", "Show projects"),
                CommandItem("assets", "Show asset library"),
                CommandItem("files", "Show project files"),
            ]
            + [CommandItem(i, f"Open asset {i + 1:04}") for i in range(0, 2000, 40)],
            bounds=Rect(0, 0, 600, 368),
            max_visible_rows=8,
        )
        self.palette.on("command_invoked", self.invoke_command)
        self.command_dialog = Modal(
            bounds=self.bounds,
            dialog_bounds=Rect(340, 184, 600, 368),
            content=self.palette,
            open=False,
            accessible_name="Workspace commands",
        )
        self.palette.on("dismissed", lambda _: self.command_dialog.dismiss())
        self.command_dialog.on("dismissed", self.commands_dismissed)
        self.add(
            Label("swir", bounds=Rect(28, 36, 180, 42), font_size=30),
            Label("WORKSPACE", bounds=Rect(28, 116, 180, 24), font_size=12),
            self.sidebar,
            Label("Your workspace. In flow.", bounds=Rect(260, 83, 830, 54), font_size=36),
            Badge("80 projects", bounds=Rect(260, 160, 156, 30)),
            Badge("2,000 assets", bounds=Rect(432, 160, 156, 30)),
            self.mode,
            self.commands,
            self.search,
            self.tabs,
            Label("Sample portfolio / local demo", bounds=Rect(260, 35, 720, 26), font_size=13),
            self.hint,
            Label("PYTHON\nNATIVE / GPU", bounds=Rect(28, 766, 180, 56), font_size=12),
            self.command_dialog,
        )
        self.sync_page()

    def on_mount(self, window: Window) -> None:
        window.on("key_down", self.command_shortcut)

    def on_unmount(self, window: Window) -> None:
        window.off("key_down", self.command_shortcut)

    def open_commands(self) -> None:
        self.palette.clear_query()
        self.palette.visible = True
        self.command_dialog.show()
        if self.mounted_window:
            self.mounted_window.focus_component(self.palette)

    def commands_dismissed(self, event: Event) -> None:
        if event.source is self.command_dialog and self.mounted_window:
            self.mounted_window.focus_component(self.commands)

    def command_shortcut(self, event: Event) -> None:
        routed = event.data.get("routed_event")
        if event.default_prevented or isinstance(routed, Event) and routed.default_prevented:
            return
        native = event.data.get("event")
        if (
            isinstance(native, PlatformEvent)
            and native.kind is PlatformEventKind.KEY_DOWN
            and native.ctrl
            and not native.alt
            and not native.meta
            and native.key_code == 0x4B
        ):
            if self.command_dialog.is_open:
                self.command_dialog.dismiss()
            else:
                self.open_commands()
            event.prevent_default()

    def invoke_command(self, event: Event) -> None:
        key = event.data["key"]
        if key == "theme":
            self.toggle_theme()
        elif isinstance(key, int):
            self.tabs.select_key("assets")
            self.assets.select_index(key, ensure_visible=True)
        else:
            self.tabs.select_key(key)

    def sync_page(self) -> None:
        with state_transaction():
            self.sidebar.select_key(self.tabs.selected_key)
            self.search.visible = self.tabs.selected_key == "projects"
            self.hint.text = {
                "projects": "F2 edits project names · Enter commits · Ctrl+click adds selection",
                "assets": "Home / End jumps through the library · Ctrl+click adds selection",
                "files": "Left / Right collapses or expands folders · Up / Down selects",
            }[self.tabs.selected_key]

    def toggle_theme(self) -> None:
        with state_transaction():
            self.theme = FUTURE_LIGHT if self.theme == FUTURE_DARK else FUTURE_DARK
            self.mode.text = "Dark theme" if self.theme == FUTURE_LIGHT else "Light theme"

    def filter_projects(self) -> None:
        query = self.search.value.strip().casefold()
        self.grid.set_filter((lambda row: query in str(row["name"]).casefold()) if query else None)


def main() -> int:
    app = App("SwirUI professional workspace", renderer=WgpuRenderer())
    window = Window(
        title="SwirUI — Professional workspace",
        width=1280,
        height=840,
        min_width=1280,
        min_height=840,
    )
    mount(window, Workspace())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
