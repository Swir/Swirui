"""Interactive retained Expander / Accordion demo.

Run on Windows with the native renderer installed::

    python examples/expander_accordion_demo.py
"""

from __future__ import annotations

from swirui import Accordion, App, Expander, Label, Window, mount
from swirui.rendering import Rect


def main() -> None:
    app = App()
    window = Window("SwirUI Expander / Accordion", width=720, height=460)

    graphics = Label(
        "GPU effects, presentation and retained caches",
        bounds=Rect(52.0, 102.0, 500.0, 28.0),
        key="graphics-content",
    )
    input_runtime = Label(
        "Focus routing, keyboard navigation and native input",
        bounds=Rect(52.0, 170.0, 500.0, 28.0),
        key="runtime-content",
    )
    packaging = Label(
        "Maturin / PyO3 ABI3 native build pipeline",
        bounds=Rect(52.0, 238.0, 500.0, 28.0),
        key="packaging-content",
    )

    accordion = Accordion(
        Expander(
            "Visual Engine",
            bounds=Rect(36.0, 48.0, 620.0, 44.0),
            content=graphics,
            expanded=True,
            key="visual-engine",
        ),
        Expander(
            "Input Runtime",
            bounds=Rect(36.0, 116.0, 620.0, 44.0),
            content=input_runtime,
            key="input-runtime",
        ),
        Expander(
            "Native Packaging",
            bounds=Rect(36.0, 184.0, 620.0, 44.0),
            content=packaging,
            key="native-packaging",
        ),
        key="demo-accordion",
        require_one=True,
        accessible_name="SwirUI feature groups",
    )

    app.add_window(window)
    mount(window, accordion)
    app.run()


if __name__ == "__main__":
    main()
