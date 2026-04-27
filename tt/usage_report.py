import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .tool_logging import (
    LOG_DIR,
    MODEL_USAGE_LOG_PATH,
    PACKAGE_DIR,
    TOOL_CALL_LOG_PATH,
    estimate_cost_usd,
    estimate_tokens,
)


USAGE_REPORT_JSON_PATH = LOG_DIR / "usage_report.json"
USAGE_REPORT_MD_PATH = LOG_DIR / "usage_report.md"
SESSION_DB_PATH = PACKAGE_DIR / ".adk" / "session.db"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def _record_input_tokens(record: dict[str, Any]) -> int:
    value = record.get("input_tokens_estimate")
    if isinstance(value, int):
        return value
    return estimate_tokens(record.get("input_summary"))


def _record_output_tokens(record: dict[str, Any]) -> int:
    value = record.get("output_tokens_estimate")
    if isinstance(value, int):
        return value
    return estimate_tokens(record.get("output_summary"))


def _record_cost(record: dict[str, Any], input_tokens: int, output_tokens: int) -> float | None:
    value = record.get("cost_usd_estimate")
    if isinstance(value, int | float):
        return float(value)
    return estimate_cost_usd(input_tokens, output_tokens)


def _usage_record_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("event_id"),
        record.get("agent_name"),
        record.get("invocation_id"),
        record.get("prompt_token_count"),
        record.get("candidates_token_count"),
        record.get("thoughts_token_count"),
        record.get("total_token_count"),
    )


def _read_session_model_usage(path: Path = SESSION_DB_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        connection = sqlite3.connect(path)
        rows = connection.execute(
            "select id, invocation_id, timestamp, event_data from events"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass

    for event_id, invocation_id, timestamp, event_data in rows:
        try:
            event = json.loads(event_data)
        except (TypeError, ValueError):
            continue
        usage = event.get("usage_metadata")
        if not isinstance(usage, dict):
            continue
        records.append(
            {
                "id": f"session:{event_id}",
                "timestamp": datetime.fromtimestamp(
                    float(timestamp),
                    timezone.utc,
                ).isoformat(),
                "agent_name": event.get("author"),
                "model": None,
                "invocation_id": invocation_id,
                "event_id": event_id,
                "prompt_token_count": usage.get("prompt_token_count"),
                "candidates_token_count": usage.get("candidates_token_count"),
                "thoughts_token_count": usage.get("thoughts_token_count"),
                "cached_content_token_count": usage.get("cached_content_token_count"),
                "total_token_count": usage.get("total_token_count"),
                "billable_total_token_count": usage.get("total_token_count"),
                "cost_usd_estimate": None,
                "metadata": {"source": "adk_session_db"},
            }
        )
    return records


def _read_model_usage_records() -> list[dict[str, Any]]:
    combined = [*_read_jsonl(MODEL_USAGE_LOG_PATH), *_read_session_model_usage()]
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in combined:
        key = _usage_record_key(record)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _build_model_usage_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = [
        int(record.get("prompt_token_count") or 0)
        for record in records
    ]
    output_tokens = [
        int(record.get("candidates_token_count") or 0)
        for record in records
    ]
    thought_tokens = [
        int(record.get("thoughts_token_count") or 0)
        for record in records
    ]
    cached_tokens = [
        int(record.get("cached_content_token_count") or 0)
        for record in records
    ]
    total_tokens = [
        int(record.get("total_token_count") or 0)
        for record in records
    ]
    costs = []
    by_agent: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "thoughts_token_count": 0,
            "cached_content_token_count": 0,
            "total_token_count": 0,
            "cost_usd_estimate": None,
        }
    )

    for record in records:
        prompt_count = int(record.get("prompt_token_count") or 0)
        candidate_count = int(record.get("candidates_token_count") or 0)
        thought_count = int(record.get("thoughts_token_count") or 0)
        cached_count = int(record.get("cached_content_token_count") or 0)
        total_count = int(record.get("total_token_count") or 0)
        cost = record.get("cost_usd_estimate")
        if not isinstance(cost, int | float):
            cost = estimate_cost_usd(prompt_count, candidate_count)
        if cost is not None:
            costs.append(float(cost))

        agent_name = str(record.get("agent_name") or "unknown")
        summary = by_agent[agent_name]
        summary["calls"] += 1
        summary["prompt_token_count"] += prompt_count
        summary["candidates_token_count"] += candidate_count
        summary["thoughts_token_count"] += thought_count
        summary["cached_content_token_count"] += cached_count
        summary["total_token_count"] += total_count
        if cost is not None:
            summary["cost_usd_estimate"] = round(
                (summary["cost_usd_estimate"] or 0.0) + float(cost),
                8,
            )

    by_agent_report = {}
    for agent_name, summary in by_agent.items():
        calls = summary["calls"]
        summary["average_prompt_token_count"] = round(
            summary["prompt_token_count"] / calls,
            2,
        )
        summary["average_candidates_token_count"] = round(
            summary["candidates_token_count"] / calls,
            2,
        )
        summary["average_total_token_count"] = round(
            summary["total_token_count"] / calls,
            2,
        )
        summary["average_cost_usd_estimate"] = (
            round(summary["cost_usd_estimate"] / calls, 8)
            if summary["cost_usd_estimate"] is not None
            else None
        )
        by_agent_report[agent_name] = summary

    return {
        "model_call_count": len(records),
        "prompt_token_count": sum(input_tokens),
        "candidates_token_count": sum(output_tokens),
        "thoughts_token_count": sum(thought_tokens),
        "cached_content_token_count": sum(cached_tokens),
        "total_token_count": sum(total_tokens),
        "average_prompt_token_count": round(mean(input_tokens), 2)
        if input_tokens
        else None,
        "average_candidates_token_count": round(mean(output_tokens), 2)
        if output_tokens
        else None,
        "average_total_token_count": round(mean(total_tokens), 2)
        if total_tokens
        else None,
        "cost_usd_estimate": round(sum(costs), 8) if costs else None,
        "average_cost_usd_estimate": round(mean(costs), 8) if costs else None,
        "by_agent": by_agent_report,
    }


def build_usage_report(log_path: Path = TOOL_CALL_LOG_PATH) -> dict[str, Any]:
    records = _read_jsonl(log_path)
    model_usage_records = _read_model_usage_records()
    actual_model_usage = _build_model_usage_summary(model_usage_records)
    successful_records = [record for record in records if record.get("success") is True]
    failed_records = [record for record in records if record.get("success") is False]

    input_tokens_by_record: list[int] = []
    output_tokens_by_record: list[int] = []
    total_tokens_by_record: list[int] = []
    costs_by_record: list[float] = []
    latency_values = [
        float(record["latency_ms"])
        for record in records
        if isinstance(record.get("latency_ms"), int | float)
    ]

    by_tool: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "input_tokens_estimate": 0,
            "output_tokens_estimate": 0,
            "total_tokens_estimate": 0,
            "cost_usd_estimate": None,
            "latencies_ms": [],
        }
    )

    for record in records:
        input_tokens = _record_input_tokens(record)
        output_tokens = _record_output_tokens(record)
        total_tokens = input_tokens + output_tokens
        cost = _record_cost(record, input_tokens, output_tokens)
        tool_name = str(record.get("tool_name") or "unknown")

        input_tokens_by_record.append(input_tokens)
        output_tokens_by_record.append(output_tokens)
        total_tokens_by_record.append(total_tokens)
        if cost is not None:
            costs_by_record.append(cost)

        tool_summary = by_tool[tool_name]
        tool_summary["calls"] += 1
        tool_summary["successes"] += 1 if record.get("success") is True else 0
        tool_summary["failures"] += 1 if record.get("success") is False else 0
        tool_summary["input_tokens_estimate"] += input_tokens
        tool_summary["output_tokens_estimate"] += output_tokens
        tool_summary["total_tokens_estimate"] += total_tokens
        if cost is not None:
            existing_cost = tool_summary["cost_usd_estimate"] or 0.0
            tool_summary["cost_usd_estimate"] = round(existing_cost + cost, 8)
        if isinstance(record.get("latency_ms"), int | float):
            tool_summary["latencies_ms"].append(float(record["latency_ms"]))

    tool_reports = {}
    for tool_name, summary in by_tool.items():
        latencies = summary.pop("latencies_ms")
        calls = summary["calls"]
        summary["average_input_tokens_estimate"] = round(
            summary["input_tokens_estimate"] / calls, 2
        )
        summary["average_output_tokens_estimate"] = round(
            summary["output_tokens_estimate"] / calls, 2
        )
        summary["average_total_tokens_estimate"] = round(
            summary["total_tokens_estimate"] / calls, 2
        )
        summary["average_cost_usd_estimate"] = (
            round(summary["cost_usd_estimate"] / calls, 8)
            if summary["cost_usd_estimate"] is not None
            else None
        )
        summary["average_latency_ms"] = round(mean(latencies), 2) if latencies else None
        tool_reports[tool_name] = summary

    error_categories = Counter(
        str(record.get("error_category"))
        for record in failed_records
        if record.get("error_category")
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "log_path": str(log_path),
        "model_usage_log_path": str(MODEL_USAGE_LOG_PATH),
        "session_db_path": str(SESSION_DB_PATH),
        "actual_model_usage": actual_model_usage,
        "call_count": len(records),
        "success_count": len(successful_records),
        "failure_count": len(failed_records),
        "success_rate": round(len(successful_records) / len(records), 4)
        if records
        else None,
        "average_latency_ms": round(mean(latency_values), 2)
        if latency_values
        else None,
        "input_tokens_estimate": sum(input_tokens_by_record),
        "output_tokens_estimate": sum(output_tokens_by_record),
        "total_tokens_estimate": sum(total_tokens_by_record),
        "average_input_tokens_estimate": round(mean(input_tokens_by_record), 2)
        if input_tokens_by_record
        else None,
        "average_output_tokens_estimate": round(mean(output_tokens_by_record), 2)
        if output_tokens_by_record
        else None,
        "average_total_tokens_estimate": round(mean(total_tokens_by_record), 2)
        if total_tokens_by_record
        else None,
        "cost_usd_estimate": round(sum(costs_by_record), 8)
        if costs_by_record
        else None,
        "average_cost_usd_estimate": round(mean(costs_by_record), 8)
        if costs_by_record
        else None,
        "cost_note": (
            "Cost is estimated only when CURRICULUM_INPUT_COST_PER_1M_TOKENS "
            "and CURRICULUM_OUTPUT_COST_PER_1M_TOKENS are set."
        ),
        "error_categories": dict(error_categories),
        "by_tool": tool_reports,
    }
    return report


def write_usage_report(report: dict[str, Any]) -> tuple[Path, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    USAGE_REPORT_JSON_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Usage Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Source log: {report['log_path']}",
        f"- Model usage log: {report['model_usage_log_path']}",
        f"- ADK session DB: {report['session_db_path']}",
        "",
        "## Actual Model Token Usage",
        f"- Model calls: {report['actual_model_usage']['model_call_count']}",
        f"- Prompt/input tokens: {report['actual_model_usage']['prompt_token_count']}",
        f"- Candidate/output tokens: {report['actual_model_usage']['candidates_token_count']}",
        f"- Thoughts tokens: {report['actual_model_usage']['thoughts_token_count']}",
        f"- Cached content tokens: {report['actual_model_usage']['cached_content_token_count']}",
        f"- Total tokens: {report['actual_model_usage']['total_token_count']}",
        f"- Average prompt/input tokens: {report['actual_model_usage']['average_prompt_token_count']}",
        f"- Average candidate/output tokens: {report['actual_model_usage']['average_candidates_token_count']}",
        f"- Average total tokens: {report['actual_model_usage']['average_total_token_count']}",
        f"- Total cost USD estimate: {report['actual_model_usage']['cost_usd_estimate']}",
        f"- Average cost USD estimate: {report['actual_model_usage']['average_cost_usd_estimate']}",
        "",
        "## Tool Log Summary",
        f"- Tool calls: {report['call_count']}",
        f"- Success rate: {report['success_rate']}",
        f"- Average latency ms: {report['average_latency_ms']}",
        f"- Total input tokens estimate: {report['input_tokens_estimate']}",
        f"- Total output tokens estimate: {report['output_tokens_estimate']}",
        f"- Total tokens estimate: {report['total_tokens_estimate']}",
        f"- Average input tokens estimate: {report['average_input_tokens_estimate']}",
        f"- Average output tokens estimate: {report['average_output_tokens_estimate']}",
        f"- Average total tokens estimate: {report['average_total_tokens_estimate']}",
        f"- Total cost USD estimate: {report['cost_usd_estimate']}",
        f"- Average cost USD estimate: {report['average_cost_usd_estimate']}",
        f"- Cost note: {report['cost_note']}",
        "",
        "## Error Categories",
    ]
    if report["error_categories"]:
        for category, count in sorted(report["error_categories"].items()):
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Actual Model Usage By Agent"])
    if report["actual_model_usage"]["by_agent"]:
        for agent_name, summary in sorted(report["actual_model_usage"]["by_agent"].items()):
            lines.extend(
                [
                    f"### {agent_name}",
                    f"- Calls: {summary['calls']}",
                    f"- Prompt/input tokens: {summary['prompt_token_count']}",
                    f"- Candidate/output tokens: {summary['candidates_token_count']}",
                    f"- Total tokens: {summary['total_token_count']}",
                    f"- Average total tokens: {summary['average_total_token_count']}",
                    f"- Average cost USD estimate: {summary['average_cost_usd_estimate']}",
                    "",
                ]
            )
    else:
        lines.append("- None")

    lines.extend(["", "## By Tool"])
    for tool_name, summary in sorted(report["by_tool"].items()):
        lines.extend(
            [
                f"### {tool_name}",
                f"- Calls: {summary['calls']}",
                f"- Successes: {summary['successes']}",
                f"- Failures: {summary['failures']}",
                f"- Average latency ms: {summary['average_latency_ms']}",
                f"- Average total tokens estimate: {summary['average_total_tokens_estimate']}",
                f"- Average cost USD estimate: {summary['average_cost_usd_estimate']}",
                "",
            ]
        )

    USAGE_REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    return USAGE_REPORT_JSON_PATH, USAGE_REPORT_MD_PATH


def main() -> None:
    json_path, md_path = write_usage_report(build_usage_report())
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
