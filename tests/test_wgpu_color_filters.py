from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import ColorFilter, WgpuRenderer


class FakeColorContext:
    adapter_name = "Color Filter Fake GPU"
    graphics_backend = "fake-wgpu"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.filter_updates: list[tuple[float, ...]] = []
        self.clear_filter_calls = 0
        self.blur_radius = 0.0

    def set_color_filter(self, values: list[float]) -> None:
        self.filter_updates.append(tuple(values))

    def clear_color_filter(self) -> None:
        self.clear_filter_calls += 1

    def set_postprocess_blur_radius(self, radius: float) -> None:
        self.blur_radius = radius

    def clear(self, *background: float) -> None:
        assert len(background) == 4

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FakeColorNative:
    def __init__(self) -> None:
        self.contexts: list[FakeColorContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> FakeColorContext:
        context = FakeColorContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def test_color_filter_configures_new_context_and_updates_in_place() -> None:
    native = FakeColorNative()
    initial = ColorFilter.grayscale(0.8)
    renderer = WgpuRenderer(native_module=native, color_filter=initial)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    window = Window(width=480, height=300)
    app.add_window(window)

    app.start()

    context = native.contexts[0]
    assert context.filter_updates == [initial.native_values()]
    assert renderer.persistent_context_count == 1

    replacement = ColorFilter.contrast(1.25).then(ColorFilter.hue_rotate(25.0))
    renderer.set_color_filter(replacement)
    assert context.filter_updates[-1] == replacement.native_values()
    assert len(context.filter_updates) == 2

    renderer.set_color_filter(None)
    assert context.clear_filter_calls == 1
    app.stop()


def test_color_filter_is_applied_to_each_persistent_window_context() -> None:
    native = FakeColorNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    first = Window(title="First", width=320, height=220)
    second = Window(title="Second", width=360, height=240)
    app.add_window(first)
    app.add_window(second)
    app.start()

    assert len(native.contexts) == 2
    color_filter = ColorFilter.invert(0.4)
    renderer.set_color_filter(color_filter)
    expected = [color_filter.native_values()]
    assert all(context.filter_updates == expected for context in native.contexts)
    app.stop()
