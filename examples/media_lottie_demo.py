"""Lottie media demo using native Rust rasterization and the persistent GPU image cache."""

from __future__ import annotations

from swirui import App, AppConfig, Lottie, Panel, Window, mount
from swirui.media import decode_lottie
from swirui.rendering import Rect, WgpuRenderer

LOTTIE_CARD = br'''{
  "v":"5.7.4","fr":60,"ip":0,"op":120,"w":320,"h":180,
  "layers":[
    {"ty":1,"ip":0,"op":120,"sw":320,"sh":180,"sc":"#0d1627",
     "ks":{"p":{"k":[0,0]},"a":{"k":[0,0]},"s":{"k":[100,100]},"o":{"k":100}}},
    {"ty":4,"ip":0,"op":120,
     "ks":{"p":{"a":1,"k":[{"t":0,"s":[0,0]},{"t":60,"s":[120,0]},{"t":120,"s":[0,0]}]},
           "a":{"k":[0,0]},"s":{"k":[100,100]},"o":{"k":100}},
     "shapes":[
       {"ty":"el","p":{"k":[80,90]},"s":{"k":[54,54]}},
       {"ty":"fl","c":{"k":[0,0.66,1,1]},"o":{"k":100}},
       {"ty":"tr","p":{"k":[0,0]},"a":{"k":[0,0]},"s":{"k":[100,100]},"o":{"k":100}}
     ]}
  ]
}'''


def main() -> None:
    renderer = WgpuRenderer()
    composition = decode_lottie(LOTTIE_CARD)
    player = Lottie(
        composition,
        renderer,
        "media:lottie",
        bounds=Rect(110.0, 70.0, 680.0, 360.0),
        accessible_name="Native Lottie preview",
    )

    app = App("SwirUI Lottie", config=AppConfig(target_fps=120), renderer=renderer)
    window = app.add_window(Window(title="SwirUI Lottie", width=900, height=500))
    root = Panel(bounds=Rect(0.0, 0.0, 900.0, 500.0), key="media-lottie-demo")
    root.add(player)
    mount(window, root)

    # Application runtimes can call player.tick(delta_ms) from their frame clock;
    # seek() remains available for deterministic previews and tooling.
    player.seek(750.0)
    raise SystemExit(app.run())


if __name__ == "__main__":
    main()
