"""SwirUI 0.1 foundation demo.

This example exercises the public lifecycle and reactive primitives. A real
native window will replace the headless foundation runtime in a later milestone.
"""

from swirui import App, Component, State, Window

counter = State(0)

app = App(name="SwirUI Foundation Demo")
window = Window(title="SwirUI — Future starts here", width=1100, height=720)

root = Component("dashboard", key="dashboard")
header = Component("header", key="header")
content = Component("content", key="content")
root.add(header, content)

window.set_root(root)
app.add_window(window)

counter.subscribe(lambda value: print(f"Counter changed -> {value}"), immediate=True)
counter.update(lambda value: value + 1)

exit_code = app.run()

print(f"App running: {app.running}")
print(f"Window visible: {window.visible}")
print(f"Component count: {sum(1 for _ in root.walk())}")
print(f"Foundation exit code: {exit_code}")

app.stop()
