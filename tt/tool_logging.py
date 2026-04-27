import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
LOG_DIR = PACKAGE_DIR / "logs"
TOOL_CALL_LOG_PATH = LOG_DIR / "tool_calls.jsonl"
MODEL_USAGE_LOG_PATH = LOG_DIR / "model_usage.jsonl"
TOKEN_CHARS_PER_TOKEN = int(os.getenv("CURRICULUM_TOKEN_CHARS_PER_TOKEN", "4"))
INPUT_COST_PER_1M_TOKENS = os.getenv("CURRICULUM_INPUT_COST_PER_1M_TOKENS")
OUTPUT_COST_PER_1M_TOKENS = os.getenv("CURRICULUM_OUTPUT_COST_PER_1M_TOKENS")
AUTO_UPDATE_USAGE_REPORT = os.getenv(
    "CURRICULUM_AUTO_UPDATE_USAGE_REPORT",
    "1",
).lower() not in {"0", "false", "no"}


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


def estimate_tokens(value: str | None) -> int:
    """Estimate tokens from text length when provider usage metadata is unavailable."""
    if not value:
        return 0
    return max(1, round(len(str(value)) / TOKEN_CHARS_PER_TOKEN))


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float | None:
    """Estimate cost from configured per-1M token prices."""
    if INPUT_COST_PER_1M_TOKENS is None or OUTPUT_COST_PER_1M_TOKENS is None:
        return None
    try:
        input_price = float(INPUT_COST_PER_1M_TOKENS)
        output_price = float(OUTPUT_COST_PER_1M_TOKENS)
    except ValueError:
        return None
    return round(
        (input_tokens / 1_000_000 * input_price)
        + (output_tokens / 1_000_000 * output_price),
        8,
    )


def refresh_usage_report() -> tuple[Path, Path] | None:
    """Regenerate usage report files from the current tool-call log."""
    try:
        from .usage_report import build_usage_report, write_usage_report
    except ImportError:
        return None
    return write_usage_report(build_usage_report())


def log_model_usage(
    *,
    agent_name: str,
    model: str | None = None,
    invocation_id: str | None = None,
    event_id: str | None = None,
    prompt_token_count: int | None = None,
    candidates_token_count: int | None = None,
    thoughts_token_count: int | None = None,
    cached_content_token_count: int | None = None,
    total_token_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Append actual model usage metadata from ADK/GenAI responses."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    input_tokens = prompt_token_count or 0
    output_tokens = candidates_token_count or 0
    billable_total = total_token_count
    if billable_total is None:
        billable_total = input_tokens + output_tokens + (thoughts_token_count or 0)
    cost_usd = estimate_cost_usd(input_tokens, output_tokens)
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": _utc_now(),
        "agent_name": agent_name,
        "model": model,
        "invocation_id": invocation_id,
        "event_id": event_id,
        "prompt_token_count": prompt_token_count,
        "candidates_token_count": candidates_token_count,
        "thoughts_token_count": thoughts_token_count,
        "cached_content_token_count": cached_content_token_count,
        "total_token_count": total_token_count,
        "billable_total_token_count": billable_total,
        "cost_usd_estimate": cost_usd,
        "metadata": _coerce_jsonable(metadata or {}),
    }
    with MODEL_USAGE_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    if AUTO_UPDATE_USAGE_REPORT:
        refresh_usage_report()
    return MODEL_USAGE_LOG_PATH


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
    input_tokens = estimate_tokens(input_summary)
    output_tokens = estimate_tokens(output_summary)
    cost_usd = estimate_cost_usd(input_tokens, output_tokens)
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": _utc_now(),
        "tool_name": tool_name,
        "agent_name": agent_name,
        "input_summary": summarize_text(input_summary),
        "output_summary": summarize_text(output_summary),
        "success": success,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "input_tokens_estimate": input_tokens,
        "output_tokens_estimate": output_tokens,
        "total_tokens_estimate": input_tokens + output_tokens,
        "cost_usd_estimate": cost_usd,
        "error_category": error_category,
        "error_message": summarize_text(error_message),
        "metadata": _coerce_jsonable(metadata or {}),
    }
    with TOOL_CALL_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    if AUTO_UPDATE_USAGE_REPORT:
        refresh_usage_report()
    return TOOL_CALL_LOG_PATH


def elapsed_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000
