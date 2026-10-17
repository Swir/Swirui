"""Author and reuse a complete custom theme, including materials and depth."""

from dataclasses import replace

from swirui import (
    NEON_BLUE,
    App,
    Button,
    ButtonVariant,
    Input,
    Label,
    Panel,
    SurfaceStyle,
    Switch,
    ThemePackage,
    ThemeSurface,
    Window,
    mount,
)
from swirui.rendering import Color, Rect, WgpuRenderer


def make_package() -> ThemePackage:
    ocean = replace(
        NEON_BLUE, control_radius=20,
        surface_style=SurfaceStyle(kind="glass", tint_opacity=.66, blur_radius=28,
                                   elevation=14, glow_radius=20, depth_layers=3,
                                   depth_spacing=12),
    )
    return ThemePackage(
        "Ocean Studio", {"glass": ocean, "acrylic": replace(ocean, surface_style=replace(
            ocean.surface_style, kind="acrylic", grain_samples=48)),
            "solid": replace(ocean, surface_style=replace(ocean.surface_style, kind="solid"))},
        "glass", description="A custom palette, material, glow and perspective backplates.",
    )


def main() -> int:
    package = make_package()
    root = Panel(bounds=Rect(0, 0, 1100, 760), theme=package.default,
                 background=Color(.005, .009, .025))
    root.add(
        Panel(bounds=Rect(70, 260, 300, 300), background=Color(.01, .21, .36),
              corner_radius=150),
        Panel(bounds=Rect(760, 280, 240, 240), background=Color(.13, .04, .29),
              corner_radius=120),
    )
    heading = Label("Glass / your own signature", bounds=Rect(80, 252, 500, 48), font_size=28)
    surface = ThemeSurface(bounds=Rect(52, 226, 570, 380))
    surface.add(
        heading,
        Label("A workspace with dimension.", bounds=Rect(80, 312, 510, 36), font_size=20),
        Input("Ocean Studio", bounds=Rect(80, 376, 510, 48), font_size=20),
        Switch("Keep ideas flowing", bounds=Rect(80, 446, 480, 44), checked=True),
        Button("Start creating", bounds=Rect(80, 518, 240, 48)),
    )
    aside = ThemeSurface(bounds=Rect(686, 280, 340, 270),
                         style=SurfaceStyle(kind="acrylic", tint_opacity=.8, elevation=8))
    aside.add(
        Label("Made by you.", bounds=Rect(710, 308, 290, 44), font_size=28),
        Label("Your colors.\nYour materials.\nYour sense of depth.",
              bounds=Rect(710, 378, 290, 100), font_size=19),
    )
    choices = {}
    for index, name in enumerate(package.themes):
        button = Button(name.title(), bounds=Rect(52 + index * 190, 148, 172, 46),
                        variant=ButtonVariant.SECONDARY)
        choices[name] = button

    def choose(name: str) -> None:
        root.theme = package.themes[name]
        heading.text = f"{name.title()} / your own signature"
        for key, button in choices.items():
            button.variant = ButtonVariant.PRIMARY if key == name else ButtonVariant.SECONDARY

    for name, button in choices.items():
        button.on("click", lambda _, name=name: choose(name))
    root.add(
        Label("swir / custom materials", bounds=Rect(52, 24, 900, 36), font_size=19),
        Label("Give your ideas depth.", bounds=Rect(52, 72, 980, 62), font_size=40),
        *choices.values(), surface, aside,
        Label("One theme. Your palette, glass, glow and layered perspective.",
              bounds=Rect(52, 700, 980, 32), font_size=18),
    )
    choose("glass")
    window = Window(title="SwirUI — Custom Materials", width=1100, height=760,
                    min_width=1100, min_height=760)
    mount(window, root)
    app = App("SwirUI Custom Materials", renderer=WgpuRenderer())
    app.add_window(window)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
