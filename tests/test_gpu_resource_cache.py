from swirui import App, Window
from swirui.platforms import NullPlatformBackend
from swirui.rendering import WgpuRenderer


class CacheContext:
    adapter_name = "Cache Test GPU"
    graphics_backend = "cache-test"

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height
        self.register_calls: list[tuple[str, int, int, bytes]] = []
        self.unregister_calls: list[str] = []
        self.resources: dict[str, tuple[int, int, bytes]] = {}

    def register_image_rgba(
        self, resource_id: str, width: int, height: int, rgba: bytes
    ) -> None:
        data = bytes(rgba)
        self.register_calls.append((resource_id, width, height, data))
        self.resources[resource_id] = (width, height, data)

    def unregister_image(self, resource_id: str) -> bool:
        self.unregister_calls.append(resource_id)
        return self.resources.pop(resource_id, None) is not None

    def clear(self, *_background: object) -> None:
        return None

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


class FailingCacheContext(CacheContext):
    def register_image_rgba(
        self, resource_id: str, width: int, height: int, rgba: bytes
    ) -> None:
        raise RuntimeError("synthetic GPU upload failure")


class CacheNative:
    def __init__(self) -> None:
        self.contexts: list[CacheContext] = []

    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> CacheContext:
        context = CacheContext(hwnd, width, height)
        self.contexts.append(context)
        return context


class PartiallyFailingCacheNative(CacheNative):
    def Win32GpuRenderer(self, hwnd: int, width: int, height: int) -> CacheContext:
        if self.contexts:
            context = FailingCacheContext(hwnd, width, height)
        else:
            context = CacheContext(hwnd, width, height)
        self.contexts.append(context)
        return context


def test_identical_image_registration_is_a_gpu_cache_hit() -> None:
    native = CacheNative()
    renderer = WgpuRenderer(native_module=native)
    pixels = bytes((10, 20, 30, 255))
    renderer.register_image_rgba("logo", 1, 1, pixels)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    app.add_window(Window(width=320, height=240))
    app.start()

    context = native.contexts[0]
    assert renderer.image_resource_count == 1
    assert renderer.image_gpu_resource_count == 1
    assert renderer.image_alias_count == 0
    assert renderer.image_resource_bytes == 4
    assert renderer.image_native_uploads == 1
    assert renderer.image_cache_hits == 0
    assert context.register_calls == [("logo", 1, 1, pixels)]

    renderer.register_image_rgba("logo", 1, 1, pixels)
    renderer.register_image_rgba("logo", 1, 1, bytearray(pixels))

    assert renderer.image_cache_hits == 2
    assert renderer.image_native_uploads == 1
    assert context.register_calls == [("logo", 1, 1, pixels)]

    replacement = bytes((200, 100, 50, 255))
    renderer.register_image_rgba("logo", 1, 1, replacement)

    assert renderer.image_cache_hits == 2
    assert renderer.image_native_uploads == 2
    assert renderer.image_resource_bytes == 4
    assert context.register_calls[-1][1:] == (1, 1, replacement)
    assert len(context.resources) == 1

    assert renderer.unregister_image("missing") is False
    assert renderer.unregister_image("logo") is True
    assert len(context.unregister_calls) == 2
    assert renderer.image_resource_count == 0
    assert renderer.image_gpu_resource_count == 0
    assert renderer.image_resource_bytes == 0
    app.stop()


def test_cross_id_identical_images_share_one_native_gpu_resource() -> None:
    native = CacheNative()
    renderer = WgpuRenderer(native_module=native)
    pixels = bytes((1, 40, 200, 255))

    renderer.register_image_rgba("logo", 1, 1, pixels)
    renderer.register_image_rgba("logo-copy", 1, 1, memoryview(pixels))

    assert renderer.image_resource_count == 2
    assert renderer.image_gpu_resource_count == 1
    assert renderer.image_alias_count == 1
    assert renderer.image_resource_bytes == 4
    assert renderer.image_cache_hits == 1

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    app.add_window(Window(width=320, height=240))
    app.start()

    context = native.contexts[0]
    assert renderer.image_native_uploads == 1
    assert context.register_calls == [("logo", 1, 1, pixels)]
    assert len(context.resources) == 1

    assert renderer.unregister_image("logo") is True
    assert context.unregister_calls == []
    assert renderer.image_resource_count == 1
    assert renderer.image_gpu_resource_count == 1

    assert renderer.unregister_image("logo-copy") is True
    assert context.unregister_calls == ["logo"]
    assert renderer.image_resource_count == 0
    assert renderer.image_gpu_resource_count == 0
    app.stop()


def test_rebinding_one_alias_preserves_shared_texture_for_other_aliases() -> None:
    native = CacheNative()
    renderer = WgpuRenderer(native_module=native)
    shared = bytes((1, 2, 3, 255))
    changed = bytes((9, 8, 7, 255))
    renderer.register_image_rgba("primary", 1, 1, shared)
    renderer.register_image_rgba("secondary", 1, 1, shared)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    app.add_window(Window(width=320, height=240))
    app.start()

    context = native.contexts[0]
    renderer.register_image_rgba("secondary", 1, 1, changed)

    assert renderer.image_resource_count == 2
    assert renderer.image_gpu_resource_count == 2
    assert renderer.image_alias_count == 0
    assert renderer.image_resource_bytes == 8
    assert renderer.image_native_uploads == 2
    assert len(context.resources) == 2
    assert context.resources["primary"] == (1, 1, shared)
    assert context.resources["secondary"] == (1, 1, changed)

    assert renderer.unregister_image("primary") is True
    assert context.unregister_calls == ["primary"]
    assert renderer.image_resource_count == 1
    assert renderer.image_gpu_resource_count == 1
    assert context.resources["secondary"] == (1, 1, changed)
    app.stop()


def test_new_context_receives_each_unique_cached_resource_once() -> None:
    native = CacheNative()
    renderer = WgpuRenderer(native_module=native)
    shared = bytes((4, 5, 6, 255))
    unique = bytes((9, 8, 7, 255))
    renderer.register_image_rgba("shared-a", 1, 1, shared)
    renderer.register_image_rgba("shared-b", 1, 1, shared)
    renderer.register_image_rgba("unique", 1, 1, unique)

    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    first_window = Window(width=320, height=240)
    second_window = Window(width=400, height=300)
    app.add_window(first_window)
    app.add_window(second_window)
    app.start()

    assert len(native.contexts) == 2
    assert renderer.image_resource_count == 3
    assert renderer.image_gpu_resource_count == 2
    assert renderer.image_alias_count == 1
    assert renderer.image_native_uploads == 4
    for context in native.contexts:
        assert len(context.register_calls) == 2
        assert len(context.resources) == 2

    renderer.register_image_rgba("shared-b", 1, 1, shared)
    assert renderer.image_cache_hits == 2
    assert renderer.image_native_uploads == 4
    for context in native.contexts:
        assert len(context.register_calls) == 2

    app.stop()


def test_failed_multi_context_upload_rolls_back_without_cache_mutation() -> None:
    native = PartiallyFailingCacheNative()
    renderer = WgpuRenderer(native_module=native)
    app = App(platform_backend=NullPlatformBackend(), renderer=renderer)
    app.add_window(Window(width=320, height=240))
    app.add_window(Window(width=400, height=300))
    app.start()

    first, failing = native.contexts
    pixels = bytes((100, 120, 140, 255))

    try:
        renderer.register_image_rgba("transactional", 1, 1, pixels)
    except RuntimeError as exc:
        assert str(exc) == "synthetic GPU upload failure"
    else:
        raise AssertionError("Expected synthetic upload failure")

    assert renderer.image_resource_count == 0
    assert renderer.image_gpu_resource_count == 0
    assert renderer.image_resource_bytes == 0
    assert renderer.image_native_uploads == 0
    assert first.register_calls == [("transactional", 1, 1, pixels)]
    assert first.unregister_calls == ["transactional"]
    assert first.resources == {}
    assert failing.resources == {}
    app.stop()
