import json
import os
import re
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

try:
    from google.adk.tools.tool_context import ToolContext
except ImportError:  # Allows lightweight local imports when ADK is unavailable.
    ToolContext = Any

from .tool_logging import elapsed_ms, log_tool_call, refresh_usage_report


PACKAGE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = PACKAGE_DIR / "long_term_memory"
CHAT_URL = "http://localhost:8000"


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


def _resolve_curriculum_session_for_read(
    session_hint: str | None = None,
) -> tuple[Path, str | None]:
    """Resolve a session for read-only tools, falling back instead of crashing."""
    try:
        return _resolve_curriculum_session(session_hint), None
    except FileNotFoundError as exc:
        session_dirs = _list_curriculum_session_dirs()
        if not session_dirs:
            raise
        fallback = session_dirs[0].resolve()
        return fallback, (
            f"{exc}. Falling back to latest curriculum session: {fallback.name}"
        )


def _relative_memory_path(path: Path) -> str:
    resolved = path.resolve()
    memory_dir = _ensure_memory_dir().resolve()
    if resolved == memory_dir or memory_dir in resolved.parents:
        return str(resolved.relative_to(PACKAGE_DIR.parent))
    return str(path)


def _course_progress_percent(unit_count: int, quiz_available: bool = False) -> int:
    return 0


def _course_achievement_count(unit_count: int, quiz_available: bool = False) -> int:
    return 0


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
    fallback_warning = None
    try:
        session_dir, fallback_warning = _resolve_curriculum_session_for_read(session_hint)
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
        if not units:
            raise FileNotFoundError(
                f"No unit_*.md files found for session_hint={session_hint!r} "
                f"and unit_filter={unit_filter!r}"
            )
        result = {
            "source_session_dir": _relative_memory_path(session_dir),
            "unit_count": len(units),
            "units": units,
        }
        if fallback_warning:
            result["warning"] = fallback_warning
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
        output_summary=(
            f"Loaded {len(units)} unit files from {result['source_session_dir']}"
            + (f" ({fallback_warning})" if fallback_warning else "")
        ),
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "source_session_dir": result["source_session_dir"],
            "unit_count": len(units),
            "filenames": [unit["filename"] for unit in units],
            "fallback_warning": fallback_warning,
        },
    )
    return json.dumps(result, ensure_ascii=False)


def store_learner_profile(
    assessed_knowledge: str,
    target_goal: str,
    goal_archetype: str,
    interview_transcript: str,
    tool_context: ToolContext,
) -> str:
    """Store the intake transcript and learner profile in shared agent state."""
    start_time = time.perf_counter()
    normalized_archetype = goal_archetype.strip().upper()
    if normalized_archetype not in {"THEORETICAL", "PRACTICAL_PROJECT"}:
        normalized_archetype = "PRACTICAL_PROJECT"

    profile = {
        "assessed_knowledge": assessed_knowledge.strip(),
        "target_goal": target_goal.strip(),
        "goal_archetype": normalized_archetype,
    }
    profile_json = json.dumps(profile, ensure_ascii=False)
    tool_context.state["interview_transcript"] = interview_transcript.strip()
    tool_context.state["user_profile_json"] = profile_json

    log_tool_call(
        tool_name="state.store_learner_profile",
        agent_name="interviewer_agent",
        input_summary=summarize_profile_input(profile),
        output_summary="Stored interview_transcript and user_profile_json in shared state.",
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "goal_archetype": normalized_archetype,
            "target_goal": target_goal[:120],
        },
    )
    return profile_json


def summarize_profile_input(profile: dict[str, str]) -> str:
    return (
        f"goal={profile.get('target_goal', '')[:120]}; "
        f"archetype={profile.get('goal_archetype', '')}"
    )


def load_curriculum_units_for_course_page(
    session_hint: str | None = None,
    unit_filter: str | None = None,
) -> str:
    """Load generated unit markdown files for course page creation as JSON."""
    start_time = time.perf_counter()
    fallback_warning = None
    try:
        session_dir, fallback_warning = _resolve_curriculum_session_for_read(session_hint)
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
        if not units:
            raise FileNotFoundError(
                f"No unit_*.md files found for session_hint={session_hint!r} "
                f"and unit_filter={unit_filter!r}"
            )
        result = {
            "source_session_dir": _relative_memory_path(session_dir),
            "unit_count": len(units),
            "units": units,
        }
        if fallback_warning:
            result["warning"] = fallback_warning
    except (OSError, FileNotFoundError, ValueError) as exc:
        log_tool_call(
            tool_name="file_io.load_curriculum_units_for_course_page",
            agent_name="course_page_generator_agent",
            input_summary=f"session_hint={session_hint}; unit_filter={unit_filter}",
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
        )
        raise

    log_tool_call(
        tool_name="file_io.load_curriculum_units_for_course_page",
        agent_name="course_page_generator_agent",
        input_summary=f"session_hint={session_hint}; unit_filter={unit_filter}",
        output_summary=(
            f"Loaded {len(units)} unit files from {result['source_session_dir']}"
            + (f" ({fallback_warning})" if fallback_warning else "")
        ),
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "source_session_dir": result["source_session_dir"],
            "unit_count": len(units),
            "filenames": [unit["filename"] for unit in units],
            "fallback_warning": fallback_warning,
        },
    )
    return json.dumps(result, ensure_ascii=False)


def _extract_markdown_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return fallback


def _friendly_session_title(session_dir: Path, unit_files: list[Path]) -> str:
    if unit_files:
        first_content = unit_files[0].read_text(encoding="utf-8")
        first_title = _extract_markdown_title(first_content, unit_files[0].stem)
        cleaned = re.sub(r"^Unit\s+\d+\s*:\s*", "", first_title, flags=re.I)
        cleaned = re.sub(r"\s*\[Resources not verified - use caution\]\s*", "", cleaned)
        if cleaned:
            return cleaned

    name = re.sub(r"^\d{8}_\d{6}_", "", session_dir.name)
    return name.replace("_", " ").strip().title() or "Saved Course"


def _classify_course_session(session_dir: Path) -> str:
    profile_path = session_dir / "user_profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            goal_archetype = str(profile.get("goal_archetype", "")).upper()
        except (OSError, ValueError, AttributeError):
            goal_archetype = ""
        if goal_archetype == "THEORETICAL":
            return "theoretical"
        if goal_archetype == "PRACTICAL_PROJECT":
            return "project"

    syllabus_path = session_dir / "syllabus.json"
    if syllabus_path.exists():
        try:
            syllabus = json.loads(syllabus_path.read_text(encoding="utf-8"))
            units = syllabus.get("units", []) if isinstance(syllabus, dict) else []
            module_types = [
                str(unit.get("module_type", "")).upper()
                for unit in units
                if isinstance(unit, dict)
            ]
        except (OSError, ValueError, AttributeError):
            module_types = []
        if module_types:
            project_count = module_types.count("PROJECT_MILESTONE")
            concept_count = module_types.count("CONCEPT_LECTURE")
            if project_count > 0 and project_count >= concept_count:
                return "project"
            return "theoretical"

    searchable_text = " ".join(
        [session_dir.name]
        + [path.name for path in session_dir.glob("unit_*.md")]
    ).lower()
    project_keywords = (
        "project",
        "build",
        "cook",
        "configure",
        "implement",
        "assemble",
        "hands_on",
        "tutorial",
    )
    if any(keyword in searchable_text for keyword in project_keywords):
        return "project"
    return "theoretical"


def _format_markdown_inline(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    def link_replacer(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        return (
            f"<a href=\"{escape(url, quote=True)}\" "
            "target=\"_blank\" rel=\"noopener noreferrer\">"
            f"{label}</a>"
        )

    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", link_replacer, escaped)


def _render_markdown_to_html(markdown_text: str) -> str:
    html_lines: list[str] = []
    paragraph_lines: list[str] = []
    list_type: str | None = None
    in_code_block = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            paragraph = " ".join(line.strip() for line in paragraph_lines)
            html_lines.append(f"<p>{_format_markdown_inline(paragraph)}</p>")
            paragraph_lines.clear()

    def flush_list() -> None:
        nonlocal list_type
        if list_type:
            html_lines.append(f"</{list_type}>")
            list_type = None

    def open_list(next_type: str) -> None:
        nonlocal list_type
        if list_type != next_type:
            flush_list()
            html_lines.append(f"<{next_type}>")
            list_type = next_type

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code_block:
                html_lines.append(
                    "<pre><code>"
                    + escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                code_lines.clear()
                in_code_block = False
            else:
                flush_paragraph()
                flush_list()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = min(len(heading_match.group(1)) + 1, 5)
            html_lines.append(
                f"<h{level}>{_format_markdown_inline(heading_match.group(2))}</h{level}>"
            )
            continue

        unordered_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if unordered_match:
            flush_paragraph()
            open_list("ul")
            html_lines.append(f"<li>{_format_markdown_inline(unordered_match.group(1))}</li>")
            continue

        ordered_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ordered_match:
            flush_paragraph()
            open_list("ol")
            html_lines.append(f"<li>{_format_markdown_inline(ordered_match.group(1))}</li>")
            continue

        quote_match = re.match(r"^>\s?(.+)$", stripped)
        if quote_match:
            flush_paragraph()
            flush_list()
            html_lines.append(
                f"<blockquote>{_format_markdown_inline(quote_match.group(1))}</blockquote>"
            )
            continue

        paragraph_lines.append(line)

    if in_code_block:
        html_lines.append(
            "<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>"
        )
    flush_paragraph()
    flush_list()
    return "\n".join(html_lines)


def _build_static_course_page_html(
    course_title: str,
    course_summary: str,
    units: list[dict[str, str]],
    quiz_available: bool = False,
) -> str:
    nav_items: list[str] = []
    sections: list[str] = []
    quiz_sidebar_link = (
        '<a class="quiz-link" href="quiz.html">Quiz</a>'
        if quiz_available
        else '<a class="quiz-link" href="../agent_chat.html">Generate quiz</a>'
    )
    quiz_topbar_link = (
        '<a class="topbar-quiz-link" href="quiz.html">Quiz</a>'
        if quiz_available
        else '<a class="topbar-quiz-link" href="../agent_chat.html">Generate quiz</a>'
    )
    for index, unit in enumerate(units):
        unit_id = f"unit-{index}"
        active_class = " active" if index == 0 else ""
        hidden_attr = "" if index == 0 else " hidden"
        nav_items.append(
            "<button type=\"button\" class=\"unit-link{active}\" data-target=\"{unit_id}\">"
            "<span class=\"unit-number\">{number:02d}</span><span>{title}</span>"
            "</button>".format(
                active=active_class,
                unit_id=unit_id,
                number=index + 1,
                title=escape(unit["title"]),
            )
        )
        sections.append(
            "<article id=\"{unit_id}\" class=\"lesson-panel\"{hidden}>"
            "<header class=\"lesson-header\"><p>{source}</p><h2>{title}</h2></header>"
            "<div class=\"lesson-body\">{body}</div></article>".format(
                unit_id=unit_id,
                hidden=hidden_attr,
                source=escape(unit["filename"]),
                title=escape(unit["title"]),
                body=_render_markdown_to_html(unit["content"]),
            )
        )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --page: #f4f1ea;
      --panel: #ffffff;
      --ink: #181a1f;
      --muted: #6f756f;
      --line: #ddd8cc;
      --accent: #f05a43;
      --accent-dark: #d9432f;
      --accent-soft: #fff0eb;
      --surface: #f9f7f0;
      --shadow: 0 18px 38px rgba(26, 22, 18, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--page); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.65; text-rendering: optimizeLegibility; }}
    .top-nav {{ display: flex; align-items: center; justify-content: center; gap: 18px; padding: 18px clamp(20px, 4vw, 54px); background: rgba(255,255,255,0.76); border-bottom: 1px solid var(--line); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 10; }}
    .brand-mark {{ position: absolute; left: clamp(20px, 4vw, 54px); font-weight: 950; font-size: 1.15rem; }}
    .nav-pills {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 6px; border-radius: 999px; background: #ebe7dc; }}
    .nav-pills a {{ min-height: 38px; padding: 9px 16px; border-radius: 999px; color: var(--ink); text-decoration: none; font-weight: 850; font-size: 0.92rem; }}
    .nav-pills a.active, .nav-pills a:hover {{ background: #181a1f; color: white; }}
    .course-shell {{ display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; padding: 26px clamp(20px, 4vw, 54px) 54px; }}
    .unit-sidebar, .lesson-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }}
    .unit-sidebar {{ align-self: start; position: sticky; top: 112px; display: flex; max-height: calc(100vh - 136px); flex-direction: column; padding: 20px; }}
    .unit-sidebar h2 {{ margin: 0 0 14px; font-size: 1.12rem; }}
    .unit-nav {{ min-height: 0; display: grid; gap: 8px; overflow-y: auto; padding-right: 4px; }}
    .unit-link {{ width: 100%; min-height: 46px; display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; align-items: center; padding: 10px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); text-align: left; cursor: pointer; font: inherit; font-size: 0.92rem; }}
    .unit-link span:last-child {{ overflow-wrap: anywhere; }}
    .unit-link:hover {{ background: white; border-color: var(--accent); }}
    .unit-link.active {{ background: var(--accent); color: white; border-color: var(--accent); font-weight: 800; }}
    .unit-number {{ width: 26px; height: 26px; display: grid; place-items: center; border-radius: 8px; background: var(--accent-soft); color: var(--accent); font-variant-numeric: tabular-nums; font-weight: 900; }}
    .unit-link.active .unit-number {{ background: rgba(255,255,255,0.22); color: white; }}
    .course-hero {{ margin-bottom: 22px; padding: 26px; border-radius: 8px; background: var(--accent); color: white; box-shadow: var(--shadow); }}
    .course-hero h1 {{ color: white; }}
    .course-hero p {{ max-width: 840px; color: rgba(255,255,255,0.86); }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .hero-actions a {{ padding: 10px 14px; border-radius: 999px; background: white; color: var(--accent); text-decoration: none; font-weight: 900; }}
    h1 {{ margin: 0; font-size: clamp(1.65rem, 3vw, 2.45rem); letter-spacing: 0; line-height: 1.15; }}
    .lesson-panel {{ overflow: hidden; }}
    .lesson-header {{ padding: clamp(22px, 3vw, 36px); border-bottom: 1px solid var(--line); background: #faf8f1; }}
    .lesson-header p {{ margin: 0 0 7px; color: var(--muted); font-size: 0.86rem; font-weight: 700; overflow-wrap: anywhere; }}
    .lesson-header h2 {{ margin: 0; font-size: clamp(1.35rem, 2.2vw, 1.95rem); letter-spacing: 0; line-height: 1.2; }}
    .lesson-body {{ padding: clamp(24px, 3vw, 40px); max-width: 920px; }}
    .lesson-body h2, .lesson-body h3, .lesson-body h4, .lesson-body h5 {{ margin: 1.3em 0 0.45em; letter-spacing: 0; line-height: 1.25; }}
    .lesson-body h2:first-child, .lesson-body h3:first-child {{ margin-top: 0; }}
    .lesson-body p, .lesson-body li {{ font-size: 1.02rem; }}
    .lesson-body p {{ margin: 0 0 1rem; }}
    .lesson-body ul, .lesson-body ol {{ padding-left: 1.35rem; }}
    .lesson-body li + li {{ margin-top: 0.34rem; }}
    .lesson-body a {{ color: var(--accent); font-weight: 700; }}
    .lesson-body blockquote {{ margin: 18px 0; padding: 14px 16px; border-left: 4px solid var(--accent); background: var(--accent-soft); color: var(--ink); border-radius: 0 8px 8px 0; }}
    .lesson-body pre {{ overflow: auto; padding: 16px; border-radius: 8px; background: #111827; color: #e5e7eb; }}
    .lesson-body code {{ padding: 0.08rem 0.25rem; border-radius: 4px; background: #eef2f7; }}
    .lesson-body pre code {{ padding: 0; background: transparent; }}
    @media (max-width: 980px) {{ .course-shell {{ grid-template-columns: 1fr; }} .unit-sidebar {{ position: static; max-height: 360px; }} .unit-nav {{ grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }} }}
    @media (max-width: 720px) {{ .top-nav {{ align-items: flex-start; flex-direction: column; justify-content: flex-start; }} .brand-mark {{ position: static; }} .nav-pills {{ border-radius: 8px; }} .course-shell {{ padding-inline: 16px; }} }}
  </style>
</head>
<body>
  <div>
    <header class="top-nav">
      <div class="brand-mark">Agentic Tutor</div>
      <nav class="nav-pills" aria-label="Main navigation">
        <a class="active" href="../index.html">Dashboard</a>
        <a href="quiz.html">Quiz</a>
        <a href="../agent_chat.html">AI assistant</a>
      </nav>
    </header>
    <main class="course-shell">
      <aside class="unit-sidebar"><h2>Course units</h2><nav class="unit-nav" aria-label="Course units">{nav}</nav></aside>
      <section>
        <header class="course-hero"><h1>{title}</h1><p>{summary}</p><div class="hero-actions"><a href="../index.html">Dashboard</a>{quiz_topbar_link}</div></header>
        <div aria-label="Lesson content">{sections}</div>
      </section>
    </main>
  </div>
  <script>
    const buttons = document.querySelectorAll("[data-target]");
    const navButtons = document.querySelectorAll(".unit-link");
    const lessons = document.querySelectorAll(".lesson-panel");
    function showLesson(targetId) {{
      lessons.forEach((lesson) => lesson.hidden = lesson.id !== targetId);
      navButtons.forEach((button) => button.classList.toggle("active", button.dataset.target === targetId));
      document.getElementById(targetId)?.scrollIntoView({{ behavior: "smooth", block: "start" }});
    }}
    buttons.forEach((button) => button.addEventListener("click", () => showLesson(button.dataset.target)));
  </script>
</body>
</html>
""".format(
        title=escape(course_title),
        summary=escape(course_summary),
        quiz_topbar_link=quiz_topbar_link,
        nav="".join(nav_items),
        sections="".join(sections),
    )


def _ensure_course_page_for_session(session_dir: Path) -> dict[str, object]:
    unit_files = sorted(session_dir.glob("unit_*.md"))
    if not unit_files:
        raise FileNotFoundError(f"No unit files found in {session_dir}")

    units = []
    for path in unit_files:
        content = path.read_text(encoding="utf-8")
        units.append(
            {
                "filename": path.name,
                "title": _extract_markdown_title(content, path.stem.replace("_", " ").title()),
                "content": content,
            }
        )

    course_title = _friendly_session_title(session_dir, unit_files)
    summary = f"{len(units)} unit lesson set saved in {session_dir.name}."
    page_path = session_dir / "course_page.html"
    quiz_path = session_dir / "quiz.html"
    page_path.write_text(
        _build_static_course_page_html(
            course_title,
            summary,
            units,
            quiz_available=quiz_path.exists(),
        ),
        encoding="utf-8",
    )

    return {
        "title": course_title,
        "session_name": session_dir.name,
        "category": _classify_course_session(session_dir),
        "unit_count": len(units),
        "progress_percent": _course_progress_percent(len(units), quiz_path.exists()),
        "achievement_count": _course_achievement_count(len(units), quiz_path.exists()),
        "quiz_available": quiz_path.exists(),
        "course_page": page_path,
        "updated_at": datetime.fromtimestamp(
            session_dir.stat().st_mtime,
            tz=timezone.utc,
        ).strftime("%Y-%m-%d"),
    }


def _build_agent_chat_html(chat_url: str) -> str:
    adk_chat_url = f"{chat_url.rstrip('/')}/?app=tt"
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ADK Chat with tt</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{
      color-scheme: light;
      --bg: #f4f1ea;
      --panel: #ffffff;
      --ink: #181a1f;
      --muted: #6f756f;
      --line: #ddd8cc;
      --accent: #f05a43;
      --accent-dark: #d9432f;
      --accent-soft: #fff0eb;
      --shadow: 0 18px 38px rgba(26, 22, 18, 0.11);
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      text-rendering: optimizeLegibility;
    }}
    .app-frame {{ min-height: 100vh; display: grid; grid-template-rows: 86px 1fr; }}
    .top-nav {{ display: flex; align-items: center; justify-content: center; gap: 18px; padding: 18px clamp(20px, 4vw, 54px); background: rgba(255,255,255,0.74); border-bottom: 1px solid var(--line); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 10; }}
    .brand-mark {{ position: absolute; left: clamp(20px, 4vw, 54px); font-weight: 950; font-size: 1.2rem; letter-spacing: 0; }}
    .nav-pills {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 6px; border-radius: 999px; background: #ebe7dc; }}
    .nav-pills a {{ min-height: 38px; padding: 9px 16px; border-radius: 999px; color: var(--ink); text-decoration: none; font-weight: 850; font-size: 0.92rem; }}
    .nav-pills a.active, .nav-pills a:hover {{ background: #181a1f; color: white; }}
    .chat-layout {{ padding: 26px clamp(20px, 4vw, 54px) 54px; }}
    .topbar {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 26px; box-shadow: var(--shadow); margin-bottom: 22px; }}
    .topbar h2 {{
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.65rem);
      letter-spacing: 0;
      line-height: 1.08;
    }}
    .topbar p {{
      margin: 9px 0 0;
      color: var(--muted);
      max-width: 760px;
      line-height: 1.55;
    }}
    .actions {{
      margin-top: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .actions a {{
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      color: var(--accent);
      text-decoration: none;
      font-weight: 800;
    }}
    .actions a.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }}
    .frame-wrap {{ min-height: 0; }}
    iframe {{
      width: 100%;
      height: calc(100vh - 176px);
      min-height: 620px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      box-shadow: var(--shadow);
    }}
    @media (max-width: 760px) {{
      .top-nav {{ align-items: flex-start; flex-direction: column; justify-content: flex-start; }}
      .brand-mark {{ position: static; }}
      .nav-pills {{ border-radius: 8px; }}
      iframe {{ height: calc(100vh - 230px); min-height: 520px; }}
    }}
  </style>
</head>
<body>
  <div class="app-frame">
    <header class="top-nav">
      <div class="brand-mark">Agentic Tutor</div>
      <nav class="nav-pills" aria-label="Main navigation">
        <a href="index.html">Dashboard</a>
        <a class="active" href="agent_chat.html">AI assistant</a>
      </nav>
    </header>
    <main class="chat-layout">
      <header class="topbar">
        <h2>ADK Web: tt</h2>
        <p>This page opens the ADK web interface for the agent app named <strong>tt</strong>.</p>
        <div class="actions">
          <a class="primary" href="{adk_chat_url}" target="_blank" rel="noopener noreferrer">Open ADK Web</a>
          <a href="index.html">Back to Dashboard</a>
        </div>
      </header>
      <section class="frame-wrap" aria-label="ADK web chat">
        <iframe src="{adk_chat_url}" title="ADK web chat for tt"></iframe>
      </section>
    </main>
  </div>
</body>
</html>
""".format(
        adk_chat_url=escape(adk_chat_url, quote=True),
    )


def _build_dashboard_html(courses: list[dict[str, object]], chat_url: str) -> str:
    def render_cards(category: str) -> str:
        cards = []
        for course in courses:
            if course.get("category") != category:
                continue
            href = f"{course['session_name']}/course_page.html"
            session_name = str(course["session_name"])
            unit_count = int(course.get("unit_count", 0))
            progress = 0
            achievements = 0
            quiz_label = "Quiz ready" if course.get("quiz_available") else "Quiz pending"
            cards.append(
                "<a class=\"course-card\" href=\"{href}\" data-session=\"{session_name}\" "
                "data-units=\"{unit_count}\" data-quiz=\"{quiz_available}\">"
                "<div class=\"card-topline\"><span>{category}</span><span>{quiz_label}</span></div>"
                "<h2>{title}</h2>"
                "<p>{unit_count} learning unit(s)</p>"
                "<div class=\"progress-row\"><strong class=\"course-progress-value\">{progress}%</strong><span>complete</span></div>"
                "<div class=\"progress-track\"><span class=\"course-progress-fill\" style=\"width:{progress}%\"></span></div>"
                "<small><span class=\"course-achievements\">{achievements}</span> achievement(s) • Updated {updated_at}</small>"
                "</a>".format(
                    href=escape(str(href), quote=True),
                    session_name=escape(session_name, quote=True),
                    quiz_available="true" if course.get("quiz_available") else "false",
                    category="Project" if course.get("category") == "project" else "Lesson",
                    quiz_label=quiz_label,
                    title=escape(str(course["title"])),
                    unit_count=unit_count,
                    progress=progress,
                    achievements=achievements,
                    updated_at=escape(str(course["updated_at"])),
                )
            )
        if cards:
            return "".join(cards)
        return (
            "<div class=\"empty-section\">"
            "<h3>No courses yet</h3>"
            "<p>Use Add project/lesson to create one.</p>"
            "</div>"
        )

    theoretical_cards = render_cards("theoretical")
    project_cards = render_cards("project")
    theoretical_count = sum(1 for course in courses if course.get("category") == "theoretical")
    project_count = sum(1 for course in courses if course.get("category") == "project")
    quiz_count = sum(1 for course in courses if course.get("quiz_available"))
    total_units = sum(int(course.get("unit_count", 0)) for course in courses)
    average_progress = 0
    total_achievements = 0

    add_card = (
        "<a class=\"add-card\" href=\"agent_chat.html\">"
        "<span class=\"plus\">+</span>"
        "<div>"
        "<h2>Add project/lesson</h2>"
        "<p>Start a new curriculum with the root agent.</p>"
        "</div>"
        "</a>"
    )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Course Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f1ea;
      --panel: #ffffff;
      --ink: #181a1f;
      --muted: #6f756f;
      --line: #ddd8cc;
      --accent: #f05a43;
      --accent-dark: #d9432f;
      --accent-soft: #fff0eb;
      --sidebar: #f9f7f0;
      --success: #2d7a55;
      --shadow: 0 18px 38px rgba(26, 22, 18, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ max-width: 100%; overflow-x: hidden; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; text-rendering: optimizeLegibility; }}
    .app-frame {{ min-height: 100vh; display: grid; grid-template-rows: 86px 1fr; }}
    .top-nav {{ display: flex; align-items: center; gap: 18px; padding: 18px clamp(20px, 4vw, 54px); background: rgba(255,255,255,0.74); border-bottom: 1px solid var(--line); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 10; }}
    .brand-mark {{ margin-right: auto; font-weight: 950; font-size: 1.2rem; letter-spacing: 0; }}
    .nav-pills {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 6px; border-radius: 999px; background: #ebe7dc; }}
    .nav-pills a {{ min-height: 38px; padding: 9px 16px; border-radius: 999px; color: var(--ink); text-decoration: none; font-weight: 850; font-size: 0.92rem; }}
    .nav-pills a.active, .nav-pills a:hover {{ background: #181a1f; color: white; }}
    .dashboard-layout {{ min-width: 0; display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 24px; padding: 26px clamp(20px, 4vw, 54px) 54px; }}
    .profile-panel, .course-board, .progress-panel, .assistant-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }}
    .profile-panel {{ padding: 24px; align-self: start; display: grid; gap: 22px; }}
    .avatar-ring {{ width: 116px; height: 116px; border-radius: 50%; border: 6px solid var(--accent); display: grid; place-items: center; background: var(--accent-soft); font-size: 2.4rem; font-weight: 950; color: var(--accent-dark); }}
    .profile-panel h1 {{ margin: 0; font-size: 1.7rem; letter-spacing: 0; line-height: 1.1; }}
    .profile-panel p {{ margin: 6px 0 0; color: var(--muted); line-height: 1.5; }}
    .mini-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .mini-stat {{ padding: 16px; border: 1px solid var(--line); border-radius: 8px; background: #fbfaf6; }}
    .mini-stat strong {{ display: block; font-size: 1.8rem; line-height: 1; }}
    .mini-stat span {{ color: var(--muted); font-size: 0.88rem; }}
    .main-stack {{ min-width: 0; display: grid; gap: 24px; }}
    .course-board {{ min-width: 0; overflow: hidden; padding: 26px; background: var(--accent); color: white; }}
    .board-heading {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; }}
    .board-heading h2 {{ margin: 0; font-size: clamp(1.8rem, 3vw, 2.55rem); letter-spacing: 0; }}
    .board-heading a {{ color: var(--accent); background: white; text-decoration: none; border-radius: 999px; padding: 10px 14px; font-weight: 900; }}
    .rail-frame {{ position: relative; }}
    .rail-frame::before, .rail-frame::after {{ content: ""; position: absolute; top: 0; bottom: 8px; width: 42px; z-index: 2; pointer-events: none; opacity: 1; transition: opacity 180ms ease; }}
    .rail-frame::before {{ left: 0; background: linear-gradient(90deg, var(--accent), rgba(240, 90, 67, 0)); }}
    .rail-frame::after {{ right: 0; background: linear-gradient(270deg, var(--accent), rgba(240, 90, 67, 0)); }}
    .rail-frame.at-start::before, .rail-frame.at-end::after {{ opacity: 0; }}
    .course-rail {{ max-width: 100%; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(260px, 320px); gap: 18px; overflow-x: auto; overscroll-behavior-x: contain; padding-bottom: 8px; scroll-snap-type: x proximity; }}
    .course-card, .add-card {{ min-height: 245px; scroll-snap-align: start; display: flex; flex-direction: column; justify-content: space-between; padding: 22px; border: 1px solid rgba(255,255,255,0.38); border-radius: 8px; background: white; color: var(--ink); text-decoration: none; box-shadow: 0 14px 30px rgba(126, 41, 28, 0.16); transition: transform 160ms ease, box-shadow 160ms ease; }}
    .course-card:hover, .add-card:hover {{ transform: translateY(-4px); box-shadow: 0 22px 36px rgba(126, 41, 28, 0.22); }}
    .card-topline {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 0.78rem; font-weight: 850; text-transform: uppercase; }}
    .course-card h2, .add-card h2 {{ margin: 22px 0 8px; font-size: 1.22rem; letter-spacing: 0; line-height: 1.2; overflow-wrap: anywhere; }}
    .course-card p, .add-card p {{ margin: 0; color: var(--muted); }}
    .progress-row {{ display: flex; align-items: baseline; gap: 8px; margin-top: 20px; }}
    .progress-row strong {{ font-size: 1.75rem; }}
    .progress-row span {{ color: var(--muted); font-weight: 750; }}
    .progress-track {{ height: 8px; border-radius: 999px; background: #e8e2d7; overflow: hidden; }}
    .progress-track span {{ display: block; height: 100%; border-radius: inherit; background: var(--accent); }}
    .course-card small {{ color: var(--muted); font-weight: 750; }}
    .add-card {{ background: #fff9f6; border-style: dashed; }}
    .plus {{ width: 48px; height: 48px; display: grid; place-items: center; border-radius: 8px; background: var(--accent); color: white; font-size: 1.9rem; line-height: 1; }}
    .insights-grid {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr); gap: 24px; }}
    .progress-panel, .assistant-panel {{ padding: 24px; }}
    .progress-panel h3, .assistant-panel h3 {{ margin: 0 0 18px; font-size: 1.3rem; letter-spacing: 0; }}
    .bar-list {{ display: grid; gap: 14px; }}
    .bar-item {{ display: grid; grid-template-columns: 96px minmax(0, 1fr) 72px; gap: 12px; align-items: center; color: var(--muted); font-weight: 800; }}
    .bar-track {{ height: 12px; border-radius: 999px; background: #f0eee6; overflow: hidden; }}
    .bar-fill {{ display: block; height: 100%; width: 0%; background: var(--accent); border-radius: inherit; transition: width 180ms ease; }}
    .achievement-list {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }}
    .achievement {{ padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: #fbfaf6; }}
    .achievement strong {{ display: block; font-size: 1.55rem; }}
    .achievement span {{ color: var(--muted); font-size: 0.88rem; }}
    .assistant-panel {{ background: #f8e9ed; display: grid; align-content: space-between; min-height: 280px; }}
    .assistant-panel p {{ color: var(--muted); line-height: 1.5; }}
    .assistant-panel a {{ justify-self: start; padding: 11px 15px; border-radius: 999px; background: var(--ink); color: white; text-decoration: none; font-weight: 900; }}
    .empty-section {{ min-height: 150px; padding: 20px; border: 1px dashed var(--line); border-radius: 8px; background: white; color: var(--muted); }}
    .empty-section h3 {{ margin: 0 0 6px; color: var(--ink); font-size: 1rem; letter-spacing: 0; }}
    .empty-section p {{ margin: 0; }}
    @media (max-width: 980px) {{ .dashboard-layout, .insights-grid {{ grid-template-columns: 1fr; }} .course-rail {{ grid-auto-columns: minmax(240px, 82vw); }} }}
    @media (max-width: 720px) {{ .top-nav {{ align-items: flex-start; flex-direction: column; justify-content: flex-start; }} .brand-mark {{ position: static; }} .nav-pills {{ border-radius: 8px; }} .dashboard-layout {{ padding-inline: 16px; }} .achievement-list {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="app-frame">
    <header class="top-nav">
      <div class="brand-mark">Agentic Tutor</div>
      <nav class="nav-pills" aria-label="Main navigation">
        <a class="active" href="index.html">Dashboard</a>
        <a href="agent_chat.html">AI assistant</a>
      </nav>
    </header>
    <main class="dashboard-layout">
      <aside class="profile-panel" aria-label="Learner summary">
        <div class="avatar-ring">AT</div>
        <div>
          <h1>Welcome back</h1>
          <p>Your generated lessons, projects, quizzes, and achievements are organized here.</p>
        </div>
        <div class="mini-stats">
          <div class="mini-stat"><strong>{course_count}</strong><span>courses</span></div>
          <div class="mini-stat"><strong>{total_units}</strong><span>units</span></div>
          <div class="mini-stat"><strong>{quiz_count}</strong><span>quizzes</span></div>
          <div class="mini-stat"><strong data-stat="avg-progress">{average_progress}%</strong><span>avg progress</span></div>
        </div>
      </aside>
      <div class="main-stack">
        <section class="course-board" aria-labelledby="courses-heading">
          <div class="board-heading">
            <h2 id="courses-heading">Your courses</h2>
            <a href="agent_chat.html">Add project/lesson</a>
          </div>
          <div class="rail-frame at-start"><div class="course-rail">{add_card}{project_cards}{theoretical_cards}</div></div>
        </section>
        <section class="insights-grid" id="progress">
          <div class="progress-panel">
            <div>
              <h3>Study progress</h3>
              <div class="bar-list">
                <div class="bar-item"><span>Courses</span><div class="bar-track"><div class="bar-fill" data-bar="courses"></div></div><strong data-stat="completed-courses">0/{course_count}</strong></div>
                <div class="bar-item"><span>Units</span><div class="bar-track"><div class="bar-fill" data-bar="units"></div></div><strong data-stat="completed-units">0/{total_units}</strong></div>
                <div class="bar-item"><span>Quizzes</span><div class="bar-track"><div class="bar-fill" data-bar="quizzes"></div></div><strong data-stat="completed-quizzes">0/{quiz_count}</strong></div>
              </div>
              <div class="achievement-list">
                <div class="achievement"><strong data-stat="achievements">{total_achievements}</strong><span>achievements earned</span></div>
                <div class="achievement"><strong>{project_count}</strong><span>project paths</span></div>
                <div class="achievement"><strong>{theoretical_count}</strong><span>lesson paths</span></div>
              </div>
            </div>
          </div>
          <div class="assistant-panel" id="support">
            <div>
              <h3>AI assistant</h3>
              <p>Start a new course, create a quiz, rebuild pages, or ask the root agent to revise your learning path.</p>
            </div>
            <a href="agent_chat.html">Open assistant</a>
          </div>
        </section>
      </div>
    </main>
  </div>
  <script>
    function readQuizProgress(sessionName) {{
      try {{
        return JSON.parse(localStorage.getItem("tt.quizProgress." + sessionName)) || {{}};
      }} catch (error) {{
        return {{}};
      }}
    }}

    function setText(selector, value) {{
      const element = document.querySelector(selector);
      if (element) {{
        element.textContent = value;
      }}
    }}

    function setBar(name, percent) {{
      const element = document.querySelector(`[data-bar="${{name}}"]`);
      if (element) {{
        element.style.width = `${{Math.max(0, Math.min(100, percent))}}%`;
      }}
    }}

    function applyQuizProgress() {{
      const cards = Array.from(document.querySelectorAll(".course-card[data-session]"));
      let totalUnits = 0;
      let completedUnits = 0;
      let completedCourses = 0;
      let quizReadyCourses = 0;
      const countedSessions = new Set();

      cards.forEach((card) => {{
        const unitCount = Number(card.dataset.units) || 0;
        const hasQuiz = card.dataset.quiz === "true";
        const progress = hasQuiz ? readQuizProgress(card.dataset.session) : {{}};
        const completed = Math.min(
          unitCount,
          Object.values(progress).filter(Boolean).length
        );
        const percent = unitCount > 0 ? Math.round((completed / unitCount) * 100) : 0;

        if (!countedSessions.has(card.dataset.session)) {{
          countedSessions.add(card.dataset.session);
          totalUnits += unitCount;
          completedUnits += completed;
          if (hasQuiz) {{
            quizReadyCourses += 1;
          }}
          if (unitCount > 0 && completed === unitCount) {{
            completedCourses += 1;
          }}
        }}

        const value = card.querySelector(".course-progress-value");
        const fill = card.querySelector(".course-progress-fill");
        const achievements = card.querySelector(".course-achievements");
        if (value) {{
          value.textContent = `${{percent}}%`;
        }}
        if (fill) {{
          fill.style.width = `${{percent}}%`;
        }}
        if (achievements) {{
          achievements.textContent = String(completed);
        }}
      }});

      const courseCount = countedSessions.size;
      const averageProgress = totalUnits > 0 ? Math.round((completedUnits / totalUnits) * 100) : 0;
      const completedQuizCourses = completedCourses;

      setText('[data-stat="avg-progress"]', `${{averageProgress}}%`);
      setText('[data-stat="completed-courses"]', `${{completedCourses}}/${{courseCount}}`);
      setText('[data-stat="completed-units"]', `${{completedUnits}}/${{totalUnits}}`);
      setText('[data-stat="completed-quizzes"]', `${{completedQuizCourses}}/${{quizReadyCourses}}`);
      setText('[data-stat="achievements"]', String(completedUnits));

      setBar("courses", courseCount ? (completedCourses / courseCount) * 100 : 0);
      setBar("units", totalUnits ? (completedUnits / totalUnits) * 100 : 0);
      setBar("quizzes", quizReadyCourses ? (completedQuizCourses / quizReadyCourses) * 100 : 0);
    }}

    window.addEventListener("storage", applyQuizProgress);
    applyQuizProgress();

    document.querySelectorAll(".rail-frame").forEach((frame) => {{
      const rail = frame.querySelector(".course-rail");
      function updateRailFade() {{
        const maxScroll = rail.scrollWidth - rail.clientWidth;
        frame.classList.toggle("at-start", rail.scrollLeft <= 2);
        frame.classList.toggle("at-end", rail.scrollLeft >= maxScroll - 2);
      }}
      rail.addEventListener("scroll", updateRailFade, {{ passive: true }});
      window.addEventListener("resize", updateRailFade);
      updateRailFade();
    }});
  </script>
</body>
</html>
""".format(
        theoretical_cards=theoretical_cards,
        project_cards=project_cards,
        course_count=len(courses),
        total_units=total_units,
        quiz_count=quiz_count,
        average_progress=average_progress,
        total_achievements=total_achievements,
        theoretical_count=theoretical_count,
        project_count=project_count,
        add_card=add_card,
    )


def refresh_canvas_dashboard(agent_name: str = "dashboard_manager_agent") -> dict[str, object]:
    """Create or refresh the Canvas-style dashboard and linked course pages."""
    start_time = time.perf_counter()
    memory_dir = _ensure_memory_dir()
    chat_url = os.getenv("CURRICULUM_AGENT_CHAT_URL", CHAT_URL)
    courses: list[dict[str, object]] = []
    generated_course_pages = 0
    try:
        for session_dir in _list_curriculum_session_dirs():
            if not list(session_dir.glob("unit_*.md")):
                continue
            page_path = session_dir / "course_page.html"
            existed = page_path.exists()
            course = _ensure_course_page_for_session(session_dir)
            if not existed:
                generated_course_pages += 1
            courses.append(course)

        dashboard_path = memory_dir / "index.html"
        chat_page_path = memory_dir / "agent_chat.html"
        chat_page_path.write_text(
            _build_agent_chat_html(chat_url),
            encoding="utf-8",
        )
        dashboard_path.write_text(
            _build_dashboard_html(courses, chat_url),
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        log_tool_call(
            tool_name="file_io.refresh_canvas_dashboard",
            agent_name=agent_name,
            input_summary="refresh dashboard",
            success=False,
            latency_ms=elapsed_ms(start_time),
            error_category="file_io_error",
            error_message=str(exc),
        )
        raise

    result = {
        "dashboard_path": _relative_memory_path(dashboard_path),
        "chat_page_path": _relative_memory_path(chat_page_path),
        "course_count": len(courses),
        "generated_course_pages": generated_course_pages,
        "chat_url": chat_url,
        "courses": [
            {
                "title": course["title"],
                "category": course["category"],
                "unit_count": course["unit_count"],
                "path": f"tt/long_term_memory/{course['session_name']}/course_page.html",
            }
            for course in courses
        ],
    }
    log_tool_call(
        tool_name="file_io.refresh_canvas_dashboard",
        agent_name=agent_name,
        input_summary="refresh dashboard",
        output_summary=(
            f"Dashboard refreshed with {len(courses)} course cards at "
            f"{result['dashboard_path']}"
        ),
        success=True,
        latency_ms=elapsed_ms(start_time),
        metadata={
            "dashboard_path": result["dashboard_path"],
            "chat_page_path": result["chat_page_path"],
            "course_count": len(courses),
            "theoretical_count": sum(
                1 for course in courses if course.get("category") == "theoretical"
            ),
            "project_count": sum(
                1 for course in courses if course.get("category") == "project"
            ),
            "generated_course_pages": generated_course_pages,
            "chat_url": chat_url,
        },
    )
    return result


def refresh_canvas_dashboard_tool() -> str:
    """Regenerate the Canvas-style main dashboard and linked course pages."""
    result = refresh_canvas_dashboard(agent_name="dashboard_manager_agent")
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
    agent_name: str = "curriculum_writer_agent",
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
            agent_name=agent_name,
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
        agent_name=agent_name,
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
