import pytest

from swirui.rendering import ImageResource


def test_image_resource_validates_rgba8_payload() -> None:
    resource = ImageResource("logo", 2, 2, bytes(range(16)))

    assert resource.resource_id == "logo"
    assert resource.width == 2
    assert resource.height == 2
    assert resource.byte_size == 16


def test_image_resource_rejects_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="resource_id"):
        ImageResource("", 1, 1, b"\x00\x00\x00\xff")

    with pytest.raises(ValueError, match="dimensions"):
        ImageResource("bad", 0, 1, b"")

    with pytest.raises(ValueError, match="requires 16 bytes"):
        ImageResource("bad", 2, 2, b"\x00" * 15)
