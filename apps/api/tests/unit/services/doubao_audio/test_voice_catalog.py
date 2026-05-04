"""Bug #22: voice catalog labels must be self-consistent."""
import sys
import importlib


def _warmup_app_import():
    """Absorb pre-existing ImportError (subtitle_provider).

    Importing ``app.main`` triggers the broken
    ``app.services.doubao_audio.subtitle_provider`` module, which
    raises ``ImportError`` (a separate, pre-existing bug). The warmup
    swallows that error; ``app.services.doubao_audio.tts_provider`` is
    still registered in ``sys.modules`` because Python imports the
    submodules of a package one-by-one and ``tts_provider`` is loaded
    *before* ``subtitle_provider`` in ``__init__.py``. We therefore
    fetch ``tts_provider`` via ``importlib`` instead of
    ``from app.services.doubao_audio import tts_provider``, which would
    re-run the broken parent ``__init__``.
    """
    try:
        from app.main import app  # noqa: F401
    except Exception:
        pass


_warmup_app_import()


def _load_voices():
    """Load the voice catalog regardless of how it's exported."""
    # Avoid ``from app.services.doubao_audio import tts_provider`` because
    # that re-runs the broken package ``__init__``. Pull the already-loaded
    # submodule out of sys.modules, falling back to importlib if needed.
    mod = sys.modules.get("app.services.doubao_audio.tts_provider")
    if mod is None:
        mod = importlib.import_module("app.services.doubao_audio.tts_provider")
    # Try common export names
    for name in ("VOICES", "VOICE_CATALOG", "DOUBAO_VOICES", "voice_catalog"):
        if hasattr(mod, name):
            obj = getattr(mod, name)
            if isinstance(obj, (list, tuple)):
                return list(obj)
            if isinstance(obj, dict):
                return list(obj.values())
    # Try the function form
    if hasattr(mod, "get_available_voices"):
        result = mod.get_available_voices()
        if isinstance(result, (list, tuple)):
            return list(result)
        if isinstance(result, dict):
            return list(result.values())
    # Fallback: scan module for VoiceInfo instances
    from app.services.doubao_audio.tts_provider import VoiceInfo
    found = []
    for v in vars(mod).values():
        if isinstance(v, list):
            found.extend(x for x in v if isinstance(x, VoiceInfo))
        elif isinstance(v, dict):
            found.extend(x for x in v.values() if isinstance(x, VoiceInfo))
        elif isinstance(v, VoiceInfo):
            found.append(v)
    return found


def test_voice_id_and_gender_agree():
    voices = _load_voices()
    assert voices, "Could not locate voice catalog in tts_provider module"
    for v in voices:
        if "_male_" in v.voice_id:
            assert v.gender == "male", (
                f"voice_id {v.voice_id!r} has gender={v.gender!r} (should be 'male')"
            )
        if "_female_" in v.voice_id:
            assert v.gender == "female", (
                f"voice_id {v.voice_id!r} has gender={v.gender!r} (should be 'female')"
            )
