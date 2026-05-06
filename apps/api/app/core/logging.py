"""Logging configuration — TraceJsonFormatter for B-1 structured spans."""
import json
import logging


class TraceJsonFormatter(logging.Formatter):
    """Emits trace span records as one JSON line each.

    Records that don't carry a `_trace_record` attribute fall through to the
    default formatter (so non-trace logs aren't disturbed).
    """

    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "_trace_record"):
            return json.dumps({"kind": "span", **record._trace_record}, ensure_ascii=False, default=str)
        return super().format(record)


def configure_trace_logger(stream=None) -> None:
    """Install a StreamHandler on the 'webtoon.trace' logger with our JSON formatter.

    Idempotent — safe to call multiple times. Pass `stream=None` for stderr default,
    or a file-like for redirection.
    """
    logger = logging.getLogger("webtoon.trace")
    if any(isinstance(h.formatter, TraceJsonFormatter) for h in logger.handlers):
        return  # already configured
    handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(TraceJsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
