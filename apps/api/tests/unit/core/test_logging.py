"""Test TraceJsonFormatter."""
import io
import json
import logging

from app.core.logging import TraceJsonFormatter, configure_trace_logger


def test_formatter_emits_json_for_trace_record():
    f = TraceJsonFormatter()
    rec = logging.LogRecord("webtoon.trace", logging.INFO, "", 0, "span", None, None)
    rec._trace_record = {"trace_id": "x", "name": "y", "duration_ms": 1.5}
    out = f.format(rec)
    parsed = json.loads(out)
    assert parsed["kind"] == "span"
    assert parsed["trace_id"] == "x"


def test_formatter_falls_through_for_normal_record():
    f = TraceJsonFormatter()
    rec = logging.LogRecord("ordinary", logging.INFO, "", 0, "hello", None, None)
    out = f.format(rec)
    assert out == "hello"


def test_configure_trace_logger_is_idempotent():
    configure_trace_logger()
    h_before = list(logging.getLogger("webtoon.trace").handlers)
    configure_trace_logger()
    h_after = list(logging.getLogger("webtoon.trace").handlers)
    assert len(h_before) == len(h_after)
