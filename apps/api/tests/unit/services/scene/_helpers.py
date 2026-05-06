"""Shared test fixtures for scene anchor tests."""
import io
import numpy as np
from PIL import Image


def make_test_png_bytes(width: int = 32, height: int = 32, color: str = "RGB") -> bytes:
    """Generate a tiny PNG image in-memory for tests."""
    img = Image.new(color, (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_grayscale_gradient_png(width: int = 64, height: int = 64) -> bytes:
    """Generate a PNG with a horizontal gradient — gives canny something to detect."""
    arr = np.zeros((height, width), dtype=np.uint8)
    for y in range(height):
        arr[y, :] = np.linspace(0, 255, width).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
