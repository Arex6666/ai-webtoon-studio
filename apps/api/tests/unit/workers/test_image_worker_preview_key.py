"""Architectural follow-up to Bug #18: image_worker must persist the raw
storage key on Panel.preview_key (and on LayerPack.file_full) so that readers
can re-sign on demand instead of caching the presigned URL with a finite TTL.

This is a static-source regression test — the runtime path requires Celery,
SQLAlchemy session machinery, and a ComfyUI/storage stack that aren't
plausible to spin up in a unit test. The patterns being asserted are
narrow and specific, so a future refactor that breaks the contract will fail
this test loudly.
"""
import inspect


def test_comfyui_adapter_returns_full_key():
    """ComfyUIAdapter.fetch_and_upload's return dict must include ``full_key``
    so downstream consumers (image_worker, panel_renderer) can persist it."""
    from app.services.layer_factory import comfyui_adapter
    src = inspect.getsource(comfyui_adapter.ComfyUIAdapter.fetch_and_upload)
    assert '"full_key": full_key' in src, (
        "ComfyUIAdapter.fetch_and_upload no longer exposes full_key in its "
        "return dict — image_worker can't persist Panel.preview_key without "
        "it, breaking the re-sign-on-read flow added in migration 021."
    )


def test_image_worker_persists_preview_key():
    """The image worker writes Panel.preview_url after a successful render;
    it must also write Panel.preview_key so readers re-sign on demand."""
    from app.workers import image_worker
    src = inspect.getsource(image_worker)
    assert 'panel.preview_key = outputs.get("full_key")' in src, (
        "image_worker no longer persists Panel.preview_key. Without this, "
        "the presigned preview_url's TTL eventually expires and panel "
        "thumbnails break in the studio aggregate endpoint."
    )


def test_image_worker_persists_layerpack_file_full():
    """LayerPack.file_full holds the raw storage key for the composite render
    image. Persisting it lets the layerpacks 'set active' route propagate the
    key to Panel.preview_key when an older layerpack is reactivated."""
    from app.workers import image_worker
    src = inspect.getsource(image_worker)
    assert 'file_full=outputs.get("full_key")' in src, (
        "image_worker no longer sets LayerPack.file_full from outputs — the "
        "layerpacks 'set active' route can't propagate preview_key without it."
    )


def test_layerpacks_set_active_propagates_preview_key():
    """When the user re-activates an older LayerPack, Panel.preview_key must
    follow LayerPack.file_full so the resolved preview URL stays fresh."""
    from app.api.routes import layerpacks
    src = inspect.getsource(layerpacks)
    assert "panel.preview_key = lp.file_full or None" in src, (
        "layerpacks 'set active' route no longer syncs Panel.preview_key — "
        "reactivating an older LayerPack will leave the panel's preview "
        "pointing at the previous render's expired presigned URL."
    )
