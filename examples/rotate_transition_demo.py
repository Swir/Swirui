"""Show the retained GPU RotateTransition on geometry-only content."""

import math

from swirui import AnimationController, App, RotateTransition, Widget, Window, linear, mount
from swirui.rendering import Color, Rect, SceneNode, SceneNodeKind


class Tile(Widget):
    """Simple geometry-only tile that can use the complete affine renderer path."""

    def build_scene_node(self) -> SceneNode:
        return SceneNode(
            key=self.key,
            kind=SceneNodeKind.RECTANGLE,
            bounds=self.bounds,
            opacity=self.opacity,
            fill=Color(0.0, 0.53, 1.0, 1.0),
            clip_to_bounds=self.clip_to_bounds,
        )


app = App("SwirUI rotate transition")
window = app.add_window(Window(title="RotateTransition", width=720, height=420))
tile = Tile(
    key="rotate-demo-tile",
    bounds=Rect(250.0, 160.0, 220.0, 100.0),
    clip_to_bounds=True,
)
mount(window, tile)

controller = AnimationController(app, window)
controller.play(
    RotateTransition(
        tile,
        math.tau,
        duration=2.0,
        easing=linear,
    )
)

app.run()
