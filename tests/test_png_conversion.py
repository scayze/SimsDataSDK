from io import BytesIO

import pytest
from PIL import Image

from sims4_sdk import GameImage, ImageError, ResourceKey, Sims4Workspace


def test_game_image_dds_to_png_preserves_pixels_and_alpha():
    source = Image.new("RGBA", (4, 4), (20, 50, 100, 128))
    dds = BytesIO()
    source.save(dds, format="DDS")
    image = GameImage(ResourceKey(1, 0, 2), dds.getvalue(), "DDS")
    with Image.open(BytesIO(image.to_png())) as result:
        assert result.format == "PNG"
        assert result.size == (4, 4)
        assert result.convert("RGBA").getpixel((0, 0)) == (20, 50, 100, 128)


def test_game_image_invalid_png_raises_sdk_error():
    with pytest.raises(ImageError, match="convert"):
        GameImage(ResourceKey(1, 0, 2), b"invalid").to_png()


def test_workspace_icon_png_returns_none_if_unavailable():
    workspace = Sims4Workspace.__new__(Sims4Workspace)
    workspace.installation = None
    assert workspace.icon_png("missing") is None


def test_workspace_icon_png_returns_converted_icon(monkeypatch):
    source = BytesIO()
    Image.new("RGBA", (1, 1), (1, 2, 3, 64)).save(source, format="PNG")
    image = GameImage(ResourceKey(1, 0, 2), source.getvalue(), "PNG")
    workspace = Sims4Workspace.__new__(Sims4Workspace)
    monkeypatch.setattr(workspace, "icon_for", lambda key: image)
    with Image.open(BytesIO(workspace.icon_png("example"))) as result:
        assert result.getpixel((0, 0)) == (1, 2, 3, 64)
