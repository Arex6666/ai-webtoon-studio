"""Regression: subtitle_provider must import without errors.

Bug: ``app.services.doubao_audio.subtitle_provider`` imported a non-existent
symbol ``get_llm_service`` from ``app.services.brain.standard_llm``. That
caused the very first ``from app.main import app`` in any pytest session to
raise ``ImportError`` (subsequent imports succeed because Python caches the
partial module — hence the ``_warmup_app_import()`` workarounds scattered
across the test suite).
"""
import importlib
import sys


def test_subtitle_provider_imports_cleanly():
    mod = importlib.import_module("app.services.doubao_audio.subtitle_provider")
    assert mod is not None


def test_app_main_imports_cleanly():
    sys.modules.pop("app.main", None)
    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app")
