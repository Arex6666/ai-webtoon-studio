"""Tests for Doubao Seedream anchor generation (Phase C)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scene.anchor_generator import (
    SceneAnchorSpec, _enforce_seedream_min_pixels,
)


def test_enforce_seedream_min_pixels_keeps_large_sizes():
    # Already satisfies 3,686,400-pixel minimum
    assert _enforce_seedream_min_pixels((1920, 1920)) == (1920, 1920)
    assert _enforce_seedream_min_pixels((2304, 1632)) == (2304, 1632)


def test_enforce_seedream_min_pixels_coerces_small_sizes():
    # 768×512 = 393,216 — way below 3,686,400; coerce to default
    assert _enforce_seedream_min_pixels((768, 512)) == (2304, 1632)
    assert _enforce_seedream_min_pixels((1024, 768)) == (2304, 1632)
