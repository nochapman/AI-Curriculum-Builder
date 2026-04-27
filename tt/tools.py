import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .tool_logging import elapsed_ms, log_tool_call, refresh_usage_report


PACKAGE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = PACKAGE_DIR / "long_term_memory"


def _ensure_memory_dir() -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "curriculum_artifact"


def _safe_filename(filename: str) -> str:
    path = Path(filename)
    stem = _slugify(path.stem)
    suffix = path.suffix if path.suffix else ".md"
    return f"{stem}{suffix}"


def safe_curriculum_filename(filename: str) -> str:
    """Return the sanitized filename used for saved curriculum artifacts."""
    return _safe_filename(filename)


def _resolve_target_dir(session_dir: str | Path | None = None) -> Path:
    memory_dir = _ensure_memory_dir().resolve()
    if session_dir is None:
        return memory_dir

    target_dir = Path(session_dir)
    if not target_dir.is_absolute():
        parts = target_dir.parts
        if len(parts) >= 2 and parts[0] == PACKAGE_DIR.name and parts[1] == MEMORY_DIR.name:
            target_dir = PACKAGE_DIR.parent / target_dir
        elif parts and parts[0] == MEMORY_DIR.name:
            target_dir = PACKAGE_DIR / target_dir
        else:
            target_dir = memory_dir / target_dir

    resolved = target_dir.resolve()
    if resolved != memory_dir and memory_dir not in resolved.parents:
        raise ValueError(f"Session directory must stay inside {memory_dir}")

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def create_curriculum_session_dir(label: str) -> Path:
    """Create a unique folder for one generated curriculum/session."""
    memory_dir = _ensure_memory_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"{timestamp}_{_slugify(label)[:60]}"
    session_dir = memory_dir / base_name
    counter = 2
    while session_dir.exists():
        session_dir = memory_dir / f"{base_name}_{counter}"
        counter += 1
    session_dir.mkdir(parents=True, exist_ok=False)
    return session_dir


def _list_curriculum_session_dirs() -> list[Path]:
    memory_dir = _ensure_memory_dir()
    return sorted(
        [path for path in memory_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _resolve_curriculum_session(session_hint: str | None = None) -> Path:
    memory_dir = _ensure_memory_dir().resolve()
    if session_hint:
        hint_path = Path(session_hint)
        candidates = []
        if hint_path.is_absolute():
            candidates.append(hint_path)
        else:
            candidates.extend(
                [
                    memory_dir / session_hint,
                    PACKAGE_DIR / session_hint,
                    PACKAGE_DIR.parent / session_hint,
                ]
            )
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_dir() and (resolved == memory_dir or memory_dir in resolved.parents):
                return resolved

        normalized_hint = _slugify(session_hint)
        for session_dir in _list_curriculum_session_dirs():
            if normalized_hint in _slugify(session_dir.name):
                return session_dir.resolve()

        raise FileNotFoundError(f"No curriculum session matched {session_hint!r}")

    session_dirs = _list_curriculum_session_dirs()
    if session_dirs:
        return session_dirs[0].resolve()

    return memory_dir


def _relative_memory_path(path: Path) -> str:
    resolved = path.resolve()
    memory_dir = _ensure_memory_dir().resolve()
    if resolved == memory_dir or memory_dir in resolved.parents:
        return str(resolved.relative_to(PACKAGE_DIR.parent))
    return str(path)


def _unit_matches_filter(path: Path, unit_filter: str) -> bool:
    normalized_filter = _slugify(unit_filter)
    normalized_stem = _slugify(path.stem)

    number_match = re.search(r"\d+", normalized_filter)
    if number_match:
        unit_number = int(number_match.group(0))
        return bool(re.match(rf"unit_0*{unit_number}(?:_|$)", normalized_stem))

    if normalized_filter in normalized_stem:
        return True

    preview = path.read_text(encoding="utf-8")[:500]
    return normalized_filter in _slugify(preview)


def load_curriculum_units_for_quiz(
    session_hint: str | None = None,
    unit_filter: str | None = None,
) -> str:
    """Load generated unit markdown files for quiz creation as JSON."""
    start_time = time.perf_counter()
    try:
        session_dir = _resolve_curriculum_session(session_hint)
        unit_files = sorted(session_dir.glob("unit_*.md"))
        if unit_filter:
            unit_files = [
                path
                for path in unit_files
                if _unit_matches_filter(path, unit_filter)
            ]

        units = [
            {
                "filename": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
            for path in unit_files
        ]
        result = {
            "source_session_dir": _relative_memory_path(session_dir),
            "unit_count": len(units),
            "units": units,
        }
    except (OSError, FileNotFoundError, ValueError) as exc:
        log_tool_call(
            tool_name="file_io.load_curriculum_units_for_quiz",
            agent_name="quiz_generator_agent",
            input_summary=f"session_hint={session_hint}; unit_filter={unit_filter}",
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
        )
        raise

    log_tool_call(
        tool_name="file_io.load_curriculum_units_for_quiz",
        agent_name="quiz_generator_agent",
        input_summary=f"session_hint={session_hint}; unit_filter={unit_filter}",
        output_summary=f"Loaded {len(units)} unit files from {result['source_session_dir']}",
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "source_session_dir": result["source_session_dir"],
            "unit_count": len(units),
            "filenames": [unit["filename"] for unit in units],
        },
    )
    return json.dumps(result, ensure_ascii=False)


def _normalize_text_content(content: str) -> str:
    """Convert common literal escape sequences into real text formatting."""
    if not isinstance(content, str):
        return content

    if "\\n" not in content and "\\t" not in content and "\\r" not in content and "\\'" not in content and '\\"' not in content:
        return content

    normalized = content.replace("\\r\\n", "\n")
    normalized = normalized.replace("\\n", "\n")
    normalized = normalized.replace("\\t", "\t")
    normalized = normalized.replace("\\'", "'")
    normalized = normalized.replace('\\"', '"')
    return normalized


def save_curriculum_artifact(
    filename: str,
    content: str,
    session_dir: str | None = None,
) -> str:
    """Save a curriculum artifact to tt/long_term_memory."""
    start_time = time.perf_counter()
    target_dir = _resolve_target_dir(session_dir)
    safe_name = _safe_filename(filename)
    file_path = target_dir / safe_name
    try:
        normalized_content = _normalize_text_content(content)
        file_path.write_text(normalized_content, encoding="utf-8")
    except OSError as exc:
        log_tool_call(
            tool_name="file_io.save_curriculum_artifact",
            agent_name="curriculum_writer_agent",
            input_summary=filename,
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
            metadata={
                "safe_filename": safe_name,
                "path": str(file_path),
                "session_dir": str(target_dir),
            },
        )
        raise

    log_tool_call(
        tool_name="file_io.save_curriculum_artifact",
        agent_name="curriculum_writer_agent",
        input_summary=filename,
        output_summary=f"Saved curriculum artifact to {file_path}",
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "safe_filename": safe_name,
            "path": str(file_path),
            "session_dir": str(target_dir),
            "bytes_written": len(normalized_content.encode("utf-8")),
        },
    )
    return f"Saved curriculum artifact to {file_path}"


def save_module_to_disk(
    unit_order: int,
    unit_title: str,
    content: str,
    session_dir: str | None = None,
) -> str:
    """Save a generated unit module to tt/long_term_memory with a stable filename."""
    start_time = time.perf_counter()
    target_dir = _resolve_target_dir(session_dir)
    safe_title = _slugify(unit_title)
    file_path = target_dir / f"unit_{int(unit_order):02d}_{safe_title}.md"
    try:
        normalized_content = _normalize_text_content(content)
        file_path.write_text(normalized_content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        log_tool_call(
            tool_name="file_io.save_module_to_disk",
            agent_name="curriculum_writer_agent",
            input_summary=f"{unit_order}: {unit_title}",
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
            metadata={
                "safe_title": safe_title,
                "path": str(file_path),
                "session_dir": str(target_dir),
            },
        )
        raise

    log_tool_call(
        tool_name="file_io.save_module_to_disk",
        agent_name="curriculum_writer_agent",
        input_summary=f"{unit_order}: {unit_title}",
        output_summary=f"Saved module to {file_path}",
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "safe_title": safe_title,
            "path": str(file_path),
            "session_dir": str(target_dir),
            "bytes_written": len(normalized_content.encode("utf-8")),
        },
    )
    return f"Saved module to {file_path}"


def save_text_file(
    filename: str,
    content: str,
    session_dir: str | None = None,
) -> str:
    """Save any curriculum-related text file into tt/long_term_memory."""
    start_time = time.perf_counter()
    target_dir = _resolve_target_dir(session_dir)
    safe_name = _safe_filename(filename)
    file_path = target_dir / safe_name
    try:
        normalized_content = _normalize_text_content(content)
        file_path.write_text(normalized_content, encoding="utf-8")
    except OSError as exc:
        log_tool_call(
            tool_name="file_io.save_text_file",
            agent_name="curriculum_writer_agent",
            input_summary=filename,
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
            metadata={
                "safe_filename": safe_name,
                "path": str(file_path),
                "session_dir": str(target_dir),
            },
        )
        raise

    log_tool_call(
        tool_name="file_io.save_text_file",
        agent_name="curriculum_writer_agent",
        input_summary=filename,
        output_summary=f"Saved text file to {file_path}",
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "safe_filename": safe_name,
            "path": str(file_path),
            "session_dir": str(target_dir),
            "bytes_written": len(normalized_content.encode("utf-8")),
        },
    )
    return f"Saved text file to {file_path}"


def refresh_usage_report_tool() -> str:
    """Regenerate usage_report.json and usage_report.md from tool_calls.jsonl."""
    start_time = time.perf_counter()
    result = refresh_usage_report()
    if result is None:
        message = "Usage report refresh failed because the report module could not be imported."
        log_tool_call(
            tool_name="usage_report.refresh",
            agent_name="usage_report_agent",
            input_summary="manual refresh",
            output_summary=message,
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="report_import_error",
        )
        return message

    json_path, md_path = result
    message = f"Usage reports updated: {json_path}, {md_path}"
    log_tool_call(
        tool_name="usage_report.refresh",
        agent_name="usage_report_agent",
        input_summary="manual refresh",
        output_summary=message,
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={"json_path": str(json_path), "md_path": str(md_path)},
    )
    return message
