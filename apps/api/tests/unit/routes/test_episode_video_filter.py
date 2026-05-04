"""Bug #11: filter by episode_num must be applied before LIMIT.

The original implementation pulled at most 50 jobs from the DB and
then filtered the Python list by ``episode_number``. If the most
recent 50 jobs across the whole project happen to belong to other
episodes, the caller gets back an empty list even though older
matching jobs exist.

Acceptable shapes after the fix:
  (a) Push the filter into the SQL query, then ``.limit(50)``
  (b) Pull a generous ``.limit(N)`` (large), filter in Python,
      slice down to 50

Both apply the filter before truncation. The check below permits
either by enforcing that any in-source post-filter on
``episode_number`` happens *before* the ``.limit(`` call.
"""
import inspect


def _warmup_app_import() -> None:
    try:
        from app.main import app  # noqa: F401
    except Exception:
        pass


_warmup_app_import()


def test_filter_runs_before_limit_in_query():
    from app.api.routes import episode_video
    src = inspect.getsource(episode_video.list_episode_video_jobs)
    lim_idx = src.find(".limit(")
    # Look for any post-filter on episode_number AFTER .limit(...)
    filter_idx = src.find('inputs.get("episode_number")')
    if filter_idx >= 0:
        # If a Python-side filter exists, it must be BEFORE the .limit() call
        assert filter_idx < lim_idx or lim_idx < 0, (
            "episode_num post-filter happens after .limit()"
        )
    # Acceptable forms:
    # (a) DB-side: query.filter(...) then .limit()
    # (b) Python-side: pull then filter then slice [:50]
