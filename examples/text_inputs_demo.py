"""Interactive retained Input / PasswordInput / TextArea demo."""

from swirui import App, Button, Component, Input, Label, PasswordInput, TextArea, Window, mount
from swirui.rendering import Color, Rect

app = App("SwirUI retained text inputs")
window = app.add_window(Window(title="SwirUI — Core text inputs", width=760, height=520))
root = Component("form")

heading = Label(
    "SwirUI 0.4 — retained text inputs",
    bounds=Rect(44.0, 34.0, 560.0, 38.0),
    font_size=24.0,
    color=Color.from_hex("#62E5FF"),
)
name = Input(
    bounds=Rect(44.0, 98.0, 420.0, 48.0),
    placeholder="Display name",
    accessible_name="Display name",
)
password = PasswordInput(
    bounds=Rect(44.0, 164.0, 420.0, 48.0),
    placeholder="Password",
    accessible_name="Password",
)
notes = TextArea(
    bounds=Rect(44.0, 230.0, 620.0, 150.0),
    placeholder="Notes — multiline input supports selection and keyboard navigation",
    accessible_name="Notes",
)
submit = Button("Submit", bounds=Rect(44.0, 406.0, 160.0, 50.0))
status = Label(
    "Tab through fields • Enter submits single-line inputs",
    bounds=Rect(224.0, 416.0, 440.0, 30.0),
    color=Color.from_hex("#8DA8B8"),
)

root.add(heading, name, password, notes, submit, status)
mount(window, root)


def show_status(message: str) -> None:
    status.text = message


name.on("submitted", lambda _event: show_status(f"Name submitted: {name.value or '(empty)'}"))
password.on("submitted", lambda _event: show_status("Password submitted (value stays masked)"))
submit.on(
    "click",
    lambda _event: show_status(
        f"Form values ready — name={name.value!r}, notes={len(notes.value)} chars"
    ),
)

app.run()
