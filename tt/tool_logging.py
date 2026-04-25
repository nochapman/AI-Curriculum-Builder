import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
LOG_DIR = PACKAGE_DIR / "logs"
TOOL_CALL_LOG_PATH = LOG_DIR / "tool_calls.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def summarize_text(value: str | None, max_chars: int = 500) -> str:
    if value is None:
        return ""
    compact = " ".join(str(value).split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def log_tool_call(
    *,
    tool_name: str,
    agent_name: str,
    input_summary: str = "",
    output_summary: str = "",
    success: bool,
    latency_ms: float | None = None,
    error_category: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Append one structured tool-call record to tt/logs/tool_calls.jsonl."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": _utc_now(),
        "tool_name": tool_name,
        "agent_name": agent_name,
        "input_summary": summarize_text(input_summary),
        "output_summary": summarize_text(output_summary),
        "success": success,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "error_category": error_category,
        "error_message": summarize_text(error_message),
        "metadata": _coerce_jsonable(metadata or {}),
    }
    with TOOL_CALL_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return TOOL_CALL_LOG_PATH


def elapsed_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000
