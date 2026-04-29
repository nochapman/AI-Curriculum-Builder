import html
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from google.adk.agents.callback_context import CallbackContext
from google.genai.types import Content

from .guardrails import (
    REFUSAL_MESSAGE,
    find_many_guardrail_violations,
    format_guardrail_violations,
)
from .schemas import CoursePageBundle, CurriculumBundle, QuizBundle
from .tool_logging import elapsed_ms, log_tool_call, summarize_text
from .tool_logging import log_model_usage
from .tools import (
    _build_static_course_page_html,
    _resolve_curriculum_session,
    create_curriculum_session_dir,
    refresh_canvas_dashboard,
    safe_curriculum_filename,
    save_text_file,
)


VALIDATION_TIMEOUT_SECS = 6
RECENCY_WINDOW_YEARS = 3
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
}
URL_PATTERN = re.compile(r"https?://[^\s<>)\"']+")
SOFT_ERROR_PATTERNS = (
    re.compile(r"<title>[^<]*(404|not found|page not found|does not exist)[^<]*</title>", re.I),
    re.compile(r"\b(404|page not found|this page does not exist|the page you requested)[\s.]", re.I),
)
GROUNDING_REDIRECT_HOST = "vertexaisearch.cloud.google.com"


def _normalize_bundle(raw_bundle: Any) -> CurriculumBundle:
    if isinstance(raw_bundle, CurriculumBundle):
        return raw_bundle
    if isinstance(raw_bundle, str):
        return CurriculumBundle.model_validate_json(raw_bundle)
    if hasattr(raw_bundle, "model_dump"):
        return CurriculumBundle.model_validate(raw_bundle.model_dump())
    return CurriculumBundle.model_validate(raw_bundle)


def _normalize_quiz_bundle(raw_bundle: Any) -> QuizBundle:
    if isinstance(raw_bundle, QuizBundle):
        return raw_bundle
    if isinstance(raw_bundle, str):
        return QuizBundle.model_validate_json(raw_bundle)
    if hasattr(raw_bundle, "model_dump"):
        return QuizBundle.model_validate(raw_bundle.model_dump())
    return QuizBundle.model_validate(raw_bundle)


def _normalize_course_page_bundle(raw_bundle: Any) -> CoursePageBundle:
    if isinstance(raw_bundle, CoursePageBundle):
        return raw_bundle
    if isinstance(raw_bundle, str):
        return CoursePageBundle.model_validate_json(raw_bundle)
    if hasattr(raw_bundle, "model_dump"):
        return CoursePageBundle.model_validate(raw_bundle.model_dump())
    return CoursePageBundle.model_validate(raw_bundle)


def _build_report(bundle: CurriculumBundle, artifact_dir: str | None = None) -> str:
    lines = [
        f"Learner summary: {bundle.learner_summary}",
        "",
        "Saved files:",
    ]
    if artifact_dir:
        lines.extend([f"Folder: {artifact_dir}", ""])
    for file in bundle.files:
        lines.append(f"- {file.filename}: {file.summary}")

    if bundle.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        for assumption in bundle.assumptions:
            lines.append(f"- {assumption}")

    return "\n".join(lines)


def _agent_name(callback_context: CallbackContext, fallback: str) -> str:
    invocation_context = getattr(callback_context, "_invocation_context", None)
    agent = getattr(invocation_context, "agent", None)
    return getattr(agent, "name", None) or fallback


def _invocation_id(callback_context: CallbackContext) -> str | None:
    invocation_context = getattr(callback_context, "_invocation_context", None)
    return getattr(invocation_context, "invocation_id", None)


def log_model_usage_callback(
    callback_context: CallbackContext,
    llm_response: Any,
) -> None:
    usage_metadata = getattr(llm_response, "usage_metadata", None)
    if not usage_metadata:
        return None

    log_model_usage(
        agent_name=_agent_name(callback_context, "unknown_agent"),
        model=getattr(llm_response, "model_version", None),
        invocation_id=_invocation_id(callback_context),
        prompt_token_count=getattr(usage_metadata, "prompt_token_count", None),
        candidates_token_count=getattr(usage_metadata, "candidates_token_count", None),
        thoughts_token_count=getattr(usage_metadata, "thoughts_token_count", None),
        cached_content_token_count=getattr(
            usage_metadata,
            "cached_content_token_count",
            None,
        ),
        total_token_count=getattr(usage_metadata, "total_token_count", None),
        metadata={
            "traffic_type": str(getattr(usage_metadata, "traffic_type", "")),
        },
    )
    return None


def _bundle_guardrail_values(bundle: CurriculumBundle) -> list[str]:
    values = [bundle.learner_summary, *bundle.assumptions]
    for file in bundle.files:
        values.extend([file.filename, file.summary, file.content])
    return values


def _quiz_guardrail_values(bundle: QuizBundle) -> list[str]:
    values = [bundle.source_session_dir, bundle.quiz_title]
    for unit in bundle.units:
        values.extend([unit.unit_title, unit.source_file])
        for question in unit.questions:
            values.extend([question.question, question.explanation, *question.options])
    return values


def _course_page_guardrail_values(bundle: CoursePageBundle) -> list[str]:
    values = [bundle.source_session_dir, bundle.course_title, bundle.course_summary]
    for unit in bundle.units:
        values.extend([unit.unit_title, unit.source_file, unit.markdown_content])
    return values


def _hydrate_course_page_units(bundle: CoursePageBundle) -> None:
    source_dir = _resolve_curriculum_session(bundle.source_session_dir)
    for unit in bundle.units:
        exact_path = source_dir / Path(unit.source_file).name
        fallback_path = source_dir / safe_curriculum_filename(unit.source_file)
        if exact_path.exists():
            unit.markdown_content = exact_path.read_text(encoding="utf-8")
        elif fallback_path.exists():
            unit.markdown_content = fallback_path.read_text(encoding="utf-8")
        elif not unit.markdown_content:
            raise FileNotFoundError(
                f"Could not find source markdown file {unit.source_file!r} "
                f"in {source_dir}"
            )


def _extract_urls(text: str) -> set[str]:
    return {
        _normalize_source_url(match.rstrip(".,;:"))
        for match in URL_PATTERN.findall(text or "")
    }


def _verified_source_urls(callback_context: CallbackContext) -> set[str]:
    verified_urls = {
        _normalize_source_url(url)
        for url in callback_context.state.get("verified_source_urls", {})
    }
    verified_sources_json = callback_context.state.get("verified_sources_json")
    if verified_sources_json:
        try:
            verified_sources = json.loads(verified_sources_json)
        except (TypeError, ValueError):
            verified_sources = []
        for source in verified_sources:
            url = source.get("url") if isinstance(source, dict) else None
            if url:
                verified_urls.add(_normalize_source_url(url))
    return verified_urls


def _find_unverified_bundle_urls(
    bundle: CurriculumBundle,
    verified_urls: set[str],
) -> dict[str, list[str]]:
    unverified_urls: dict[str, list[str]] = {}
    for file in bundle.files:
        file_urls = _extract_urls(file.content)
        bad_urls = sorted(url for url in file_urls if url not in verified_urls)
        if bad_urls:
            unverified_urls[file.filename] = bad_urls
    return unverified_urls


def _add_unverified_source_warning(content: str, urls: list[str]) -> str:
    warning = (
        "> **Resource verification warning:** One or more references in this lesson "
        "could not be verified automatically. Use caution before relying on these "
        "links, and confirm that each page exists and is trustworthy.\n\n"
    )
    url_list = "\n".join(f"> - {url}" for url in urls)
    warning_block = f"{warning}{url_list}\n\n"

    if content.startswith("# "):
        first_line, separator, rest = content.partition("\n")
        marked_title = f"{first_line} [Resources not verified - use caution]"
        return f"{marked_title}{separator}{warning_block}{rest}"

    return f"# Resources not verified - use caution\n\n{warning_block}{content}"


def _annotate_unverified_bundle_urls(
    bundle: CurriculumBundle,
    unverified_urls: dict[str, list[str]],
) -> None:
    for file in bundle.files:
        urls = unverified_urls.get(file.filename)
        if urls:
            file.content = _add_unverified_source_warning(file.content, urls)
            file.summary = (
                f"{file.summary} Some resource links were not automatically verified; "
                "the saved file includes a caution note."
            )


def _build_quiz_html(bundle: QuizBundle) -> str:
    nav_items: list[str] = []
    sections: list[str] = []
    total_questions = 0
    for unit_index, unit in enumerate(bundle.units):
        unit_id = f"unit-{unit_index}"
        active_class = " active" if unit_index == 0 else ""
        hidden_attr = "" if unit_index == 0 else " hidden"
        nav_items.append(
            "<button type=\"button\" "
            f"class=\"unit-tab{active_class}\" data-target=\"{unit_id}\">"
            "<span>{number:02d}</span><strong>{title}</strong>"
            "</button>".format(
                number=unit_index + 1,
                title=html.escape(unit.unit_title),
            )
        )

        question_blocks: list[str] = []
        for question_index, question in enumerate(unit.questions):
            total_questions += 1
            options = []
            for option_index, option in enumerate(question.options):
                input_id = f"{unit_id}-q{question_index}-o{option_index}"
                options.append(
                    "<label class=\"option\" for=\"{input_id}\">"
                    "<input id=\"{input_id}\" type=\"radio\" "
                    "name=\"{unit_id}-q{question_index}\" value=\"{option_index}\">"
                    "<span>{option}</span>"
                    "</label>".format(
                        input_id=input_id,
                        unit_id=unit_id,
                        question_index=question_index,
                        option_index=option_index,
                        option=html.escape(option),
                    )
                )
            question_blocks.append(
                "<article class=\"question\" data-correct=\"{correct}\" "
                "data-explanation=\"{explanation}\">"
                "<h3>{number}. {question}</h3>"
                "<div class=\"options\">{options}</div>"
                "<p class=\"feedback\" aria-live=\"polite\"></p>"
                "</article>".format(
                    correct=question.correct_option_index,
                    explanation=html.escape(question.explanation, quote=True),
                    number=question_index + 1,
                    question=html.escape(question.question),
                    options="".join(options),
                )
            )

        sections.append(
            "<section id=\"{unit_id}\" class=\"unit-panel\"{hidden}>"
            "<div class=\"unit-heading\">"
            "<p>{source}</p>"
            "<h2>{title}</h2>"
            "</div>"
            "{questions}"
            "<div class=\"actions\">"
            "<button type=\"button\" class=\"check-button\">Check answers</button>"
            "<button type=\"button\" class=\"reset-button\">Reset unit</button>"
            "<span class=\"score\" aria-live=\"polite\"></span>"
            "</div>"
            "</section>".format(
                unit_id=unit_id,
                hidden=hidden_attr,
                source=html.escape(unit.source_file),
                title=html.escape(unit.unit_title),
                questions="".join(question_blocks),
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
      --bg: #f4f1ea;
      --panel: #ffffff;
      --ink: #181a1f;
      --muted: #6f756f;
      --line: #ddd8cc;
      --accent: #f05a43;
      --accent-dark: #d9432f;
      --accent-soft: #fff0eb;
      --surface: #f9f7f0;
      --good: #2d7a55;
      --bad: #b42318;
      --shadow: 0 18px 38px rgba(26, 22, 18, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.65; text-rendering: optimizeLegibility; }}
    .top-nav {{ display: flex; align-items: center; justify-content: center; gap: 18px; padding: 18px clamp(20px, 4vw, 54px); background: rgba(255,255,255,0.76); border-bottom: 1px solid var(--line); backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 10; }}
    .brand-mark {{ position: absolute; left: clamp(20px, 4vw, 54px); font-weight: 950; font-size: 1.15rem; }}
    .nav-pills {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 6px; border-radius: 999px; background: #ebe7dc; }}
    .nav-pills a {{ min-height: 38px; padding: 9px 16px; border-radius: 999px; color: var(--ink); text-decoration: none; font-weight: 850; font-size: 0.92rem; }}
    .nav-pills a.active, .nav-pills a:hover {{ background: #181a1f; color: white; }}
    .quiz-shell {{ display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 24px; padding: 26px clamp(20px, 4vw, 54px) 54px; }}
    .quiz-nav, .unit-panel, .quiz-hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }}
    .quiz-nav {{ align-self: start; position: sticky; top: 112px; padding: 20px; }}
    .quiz-nav h2 {{ margin: 0 0 14px; font-size: 1.12rem; }}
    .unit-tabs {{ display: grid; gap: 8px; }}
    .unit-tab {{ width: 100%; min-height: 52px; display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; align-items: center; padding: 10px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); text-align: left; cursor: pointer; font: inherit; }}
    .unit-tab span {{ width: 26px; height: 26px; display: grid; place-items: center; border-radius: 8px; background: var(--accent-soft); color: var(--accent); font-weight: 950; }}
    .unit-tab strong {{ overflow-wrap: anywhere; }}
    .unit-tab:hover {{ background: white; border-color: var(--accent); }}
    .unit-tab.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
    .unit-tab.active span {{ background: rgba(255,255,255,0.22); color: white; }}
    .quiz-hero {{ margin-bottom: 22px; padding: 26px; background: var(--accent); color: white; }}
    .quiz-hero h1 {{ margin: 0; font-size: clamp(1.8rem, 3vw, 2.65rem); line-height: 1.08; }}
    .quiz-hero p {{ margin: 9px 0 0; color: rgba(255,255,255,0.86); }}
    .quiz-hero .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
    .quiz-hero .meta span {{ padding: 8px 10px; border-radius: 999px; background: rgba(255,255,255,0.18); font-weight: 850; }}
    .unit-panel {{ padding: clamp(22px, 3vw, 34px); }}
    .unit-heading p {{ margin: 0 0 7px; color: var(--muted); font-size: 0.86rem; font-weight: 800; overflow-wrap: anywhere; }}
    h2 {{ margin: 0 0 20px; font-size: clamp(1.35rem, 2.2vw, 1.95rem); line-height: 1.2; }}
    .question {{ padding: 18px 0; border-top: 1px solid var(--line); }}
    .question h3 {{ margin: 0 0 12px; font-size: 1rem; }}
    .options {{ display: grid; gap: 8px; }}
    .option {{ display: flex; gap: 10px; align-items: flex-start; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); cursor: pointer; }}
    .option:hover {{ border-color: var(--accent); background: var(--accent-soft); }}
    .option input {{ margin-top: 4px; }}
    .feedback {{ min-height: 24px; margin: 10px 0 0; color: var(--muted); }}
    .question.correct .feedback {{ color: var(--good); }}
    .question.incorrect .feedback {{ color: var(--bad); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding-top: 18px; border-top: 1px solid var(--line); }}
    .check-button, .reset-button {{ min-height: 40px; padding: 8px 14px; border-radius: 8px; border: 1px solid var(--accent); cursor: pointer; font-weight: 850; }}
    .check-button {{ background: var(--accent); color: white; }}
    .reset-button {{ background: white; color: var(--accent); }}
    .score {{ color: var(--muted); font-weight: 850; }}
    @media (max-width: 980px) {{ .quiz-shell {{ grid-template-columns: 1fr; }} .quiz-nav {{ position: static; }} .unit-tabs {{ grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }} }}
    @media (max-width: 720px) {{ .top-nav {{ align-items: flex-start; flex-direction: column; justify-content: flex-start; }} .brand-mark {{ position: static; }} .nav-pills {{ border-radius: 8px; }} .quiz-shell {{ padding-inline: 16px; }} }}
  </style>
</head>
<body>
  <header class="top-nav">
    <div class="brand-mark">Agentic Tutor</div>
    <nav class="nav-pills" aria-label="Main navigation">
      <a href="../index.html">Dashboard</a>
      <a class="active" href="quiz.html">Quiz</a>
      <a href="../agent_chat.html">AI assistant</a>
    </nav>
  </header>
  <main class="quiz-shell">
    <aside class="quiz-nav"><h2>Quiz units</h2><nav class="unit-tabs" aria-label="Quiz units">{nav}</nav></aside>
    <section>
      <header class="quiz-hero"><h1>{title}</h1><p>Choose a unit, answer the questions, and check your score.</p><div class="meta"><span>{unit_count} unit(s)</span><span>{question_count} question(s)</span></div></header>
      <div>{sections}</div>
    </section>
  </main>
  <script>
    const tabs = document.querySelectorAll(".unit-tab");
    const panels = document.querySelectorAll(".unit-panel");
    const courseKey = decodeURIComponent(location.pathname.split("/").filter(Boolean).slice(-2, -1)[0] || "current-course");
    const progressKey = "tt.quizProgress." + courseKey;

    function readProgress() {{
      try {{
        return JSON.parse(localStorage.getItem(progressKey)) || {{}};
      }} catch (error) {{
        return {{}};
      }}
    }}

    function setUnitComplete(unitId, complete) {{
      const progress = readProgress();
      if (complete) {{
        progress[unitId] = true;
      }} else {{
        delete progress[unitId];
      }}
      localStorage.setItem(progressKey, JSON.stringify(progress));
    }}

    tabs.forEach((tab) => {{
      tab.addEventListener("click", () => {{
        tabs.forEach((item) => item.classList.remove("active"));
        panels.forEach((panel) => panel.hidden = true);
        tab.classList.add("active");
        document.getElementById(tab.dataset.target).hidden = false;
      }});
    }});

    document.querySelectorAll(".unit-panel").forEach((panel) => {{
      const checkButton = panel.querySelector(".check-button");
      const resetButton = panel.querySelector(".reset-button");
      const score = panel.querySelector(".score");
      checkButton.addEventListener("click", () => {{
        let correct = 0;
        const questions = panel.querySelectorAll(".question");
        questions.forEach((question) => {{
          question.classList.remove("correct", "incorrect");
          const selected = question.querySelector("input:checked");
          const feedback = question.querySelector(".feedback");
          if (!selected) {{
            feedback.textContent = "Choose an answer before checking.";
            question.classList.add("incorrect");
            return;
          }}
          if (Number(selected.value) === Number(question.dataset.correct)) {{
            correct += 1;
            feedback.textContent = "Correct. " + question.dataset.explanation;
            question.classList.add("correct");
          }} else {{
            feedback.textContent = "Not quite. " + question.dataset.explanation;
            question.classList.add("incorrect");
          }}
        }});
        const perfect = correct === questions.length && questions.length > 0;
        if (perfect) {{
          setUnitComplete(panel.id, true);
        }}
        score.textContent = `${{correct}} / ${{questions.length}} correct` + (perfect ? " - unit complete" : "");
      }});
      resetButton.addEventListener("click", () => {{
        panel.querySelectorAll("input").forEach((input) => input.checked = false);
        panel.querySelectorAll(".question").forEach((question) => {{
          question.classList.remove("correct", "incorrect");
          question.querySelector(".feedback").textContent = "";
        }});
        score.textContent = "";
      }});
    }});
  </script>
</body>
</html>
""".format(
        title=html.escape(bundle.quiz_title),
        nav="".join(nav_items),
        sections="".join(sections),
        unit_count=len(bundle.units),
        question_count=total_questions,
    )


def _format_markdown_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)

    def link_replacer(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        if not url.startswith(("http://", "https://")):
            return match.group(0)
        return (
            f"<a href=\"{html.escape(url, quote=True)}\" "
            "target=\"_blank\" rel=\"noopener noreferrer\">"
            f"{label}</a>"
        )

    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", link_replacer, escaped)


def _render_markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
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

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                html_lines.append(
                    "<pre><code>"
                    + html.escape("\n".join(code_lines))
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
            text = _format_markdown_inline(heading_match.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
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
            "<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>"
        )
    flush_paragraph()
    flush_list()
    return "\n".join(html_lines)


def _build_course_page_html(bundle: CoursePageBundle) -> str:
    units = [
        {
            "filename": unit.source_file,
            "title": unit.unit_title,
            "content": unit.markdown_content,
        }
        for unit in bundle.units
    ]
    source_dir = Path(bundle.source_session_dir)
    return _build_static_course_page_html(
        bundle.course_title,
        bundle.course_summary,
        units,
        quiz_available=(source_dir / "quiz.html").exists(),
    )

def _normalize_source_url(url: str) -> str:
    parsed = urlparse(url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    normalized_path = parsed.path or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def _extract_year(*values: str | None) -> int | None:
    current_year = datetime.now(timezone.utc).year
    for value in values:
        if not value:
            continue
        years = [int(match) for match in YEAR_PATTERN.findall(value)]
        for year in sorted(years, reverse=True):
            if 2000 <= year <= current_year + 1:
                return year
    return None


def _parse_last_modified(header_value: str | None) -> str | None:
    if not header_value:
        return None
    try:
        parsed = parsedate_to_datetime(header_value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _looks_like_soft_error(content_type: str, body: bytes) -> bool:
    if "html" not in content_type:
        return False
    try:
        text = body.decode("utf-8", errors="ignore")
    except (AttributeError, UnicodeDecodeError):
        return False
    return any(pattern.search(text) for pattern in SOFT_ERROR_PATTERNS)


def _validate_source_url(url: str) -> dict[str, Any] | None:
    start_time = time.perf_counter()
    normalized_url = _normalize_source_url(url)
    headers = {
        "User-Agent": "AI-Curriculum-Builder/1.0",
        "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1",
    }
    last_error_category: str | None = None
    last_error_message: str | None = None

    for method in ("GET", "HEAD"):
        request = Request(normalized_url, headers=headers, method=method)
        try:
            with urlopen(request, timeout=VALIDATION_TIMEOUT_SECS) as response:
                status_code = getattr(response, "status", None) or response.getcode()
                if status_code and status_code >= 400:
                    log_tool_call(
                        tool_name="web.url_validation",
                        agent_name="research_agent",
                        input_summary=normalized_url,
                        output_summary=f"{method} returned HTTP {status_code}",
                        success=False,
                        latency_ms=elapsed_ms(start_time),
                        error_category="http_error",
                        metadata={"method": method, "status_code": status_code},
                    )
                    return None

                final_url = _normalize_source_url(response.geturl())
                header_map = response.headers
                last_modified = _parse_last_modified(header_map.get("Last-Modified"))
                content_type = header_map.get_content_type()
                body_sample = response.read(32768) if method == "GET" else b""
                if _looks_like_soft_error(content_type, body_sample):
                    log_tool_call(
                        tool_name="web.url_validation",
                        agent_name="research_agent",
                        input_summary=normalized_url,
                        output_summary=f"{method} looked like a soft 404: {final_url}",
                        success=False,
                        latency_ms=elapsed_ms(start_time),
                        error_category="soft_404",
                        metadata={
                            "method": method,
                            "status_code": status_code,
                            "content_type": content_type,
                        },
                    )
                    return None
                if GROUNDING_REDIRECT_HOST in urlparse(final_url).netloc:
                    log_tool_call(
                        tool_name="web.url_validation",
                        agent_name="research_agent",
                        input_summary=normalized_url,
                        output_summary=f"Grounding redirect did not resolve: {final_url}",
                        success=False,
                        latency_ms=elapsed_ms(start_time),
                        error_category="unresolved_grounding_redirect",
                        metadata={"method": method, "status_code": status_code},
                    )
                    return None
                result = {
                    "url": final_url,
                    "status_code": status_code,
                    "content_type": content_type,
                    "last_modified": last_modified,
                    "year_hint": _extract_year(
                        final_url,
                        last_modified,
                    ),
                }
                log_tool_call(
                    tool_name="web.url_validation",
                    agent_name="research_agent",
                    input_summary=normalized_url,
                    output_summary=final_url,
                    success=True,
                    latency_ms=elapsed_ms(start_time),
                    metadata={
                        "method": method,
                        "status_code": status_code,
                        "content_type": content_type,
                        "last_modified": last_modified,
                    },
                )
                return result
        except HTTPError as exc:
            if method == "HEAD" and exc.code in {403, 405}:
                last_error_category = "head_not_allowed"
                last_error_message = str(exc)
                continue
            log_tool_call(
                tool_name="web.url_validation",
                agent_name="research_agent",
                input_summary=normalized_url,
                success=False,
                latency_ms=elapsed_ms(start_time),
                error_category="http_error",
                error_message=str(exc),
                metadata={"method": method, "status_code": exc.code},
            )
            return None
        except (URLError, TimeoutError, ValueError) as exc:
            log_tool_call(
                tool_name="web.url_validation",
                agent_name="research_agent",
                input_summary=normalized_url,
                success=False,
                latency_ms=elapsed_ms(start_time),
                error_category=type(exc).__name__,
                error_message=str(exc),
                metadata={"method": method},
            )
            return None

    log_tool_call(
        tool_name="web.url_validation",
        agent_name="research_agent",
        input_summary=normalized_url,
        success=False,
        latency_ms=elapsed_ms(start_time),
        error_category=last_error_category or "validation_failed",
        error_message=last_error_message,
    )
    return None


def _source_sort_key(source: dict[str, Any]) -> tuple[int, int, str]:
    current_year = datetime.now(timezone.utc).year
    year_hint = source.get("year_hint")
    if isinstance(year_hint, int):
        recency_score = max(0, RECENCY_WINDOW_YEARS + 1 - abs(current_year - year_hint))
    else:
        recency_score = 0
    official_bonus = 1 if str(source.get("domain", "")).endswith((".gov", ".edu")) else 0
    return (
        recency_score,
        official_bonus,
        source.get("title", ""),
    )


def collect_verified_sources_callback(
    callback_context: CallbackContext,
) -> None:
    """Extract live canonical web URLs from grounding metadata and store them in state."""
    start_time = time.perf_counter()
    agent_name = _agent_name(callback_context, "research_agent")
    session = callback_context._invocation_context.session
    seen_urls = callback_context.state.get("verified_source_urls", {})
    validation_cache = callback_context.state.get("source_validation_cache", {})
    raw_url_count = 0
    skipped_redirect_count = 0
    failed_validation_count = 0
    verified_before_count = len(seen_urls)

    for event in session.events:
        grounding_metadata = getattr(event, "grounding_metadata", None)
        grounding_chunks = (
            grounding_metadata.grounding_chunks if grounding_metadata else None
        )
        if not grounding_chunks:
            continue

        for chunk in grounding_chunks:
            web = getattr(chunk, "web", None)
            if not web or not getattr(web, "uri", None):
                continue

            raw_url = web.uri
            raw_url_count += 1
            if "vertexaisearch.cloud.google.com/grounding-api-redirect/" in raw_url:
                skipped_redirect_count += 1

            normalized_url = _normalize_source_url(raw_url)
            cached_validation = validation_cache.get(normalized_url)
            if cached_validation is None:
                cached_validation = _validate_source_url(raw_url) or False
                validation_cache[normalized_url] = cached_validation

            if not cached_validation:
                failed_validation_count += 1
                continue

            live_url = cached_validation["url"]
            seen_urls[live_url] = {
                "title": getattr(web, "title", "") or getattr(web, "domain", live_url),
                "domain": getattr(web, "domain", "") or urlparse(live_url).netloc,
                "url": live_url,
                "original_url": raw_url,
                "status_code": cached_validation.get("status_code"),
                "content_type": cached_validation.get("content_type"),
                "last_modified": cached_validation.get("last_modified"),
                "last_verified_at": datetime.now(timezone.utc).isoformat(),
                "year_hint": cached_validation.get("year_hint"),
            }

    verified_sources = sorted(
        seen_urls.values(),
        key=_source_sort_key,
        reverse=True,
    )
    callback_context.state["verified_source_urls"] = seen_urls
    callback_context.state["source_validation_cache"] = validation_cache
    callback_context.state["verified_sources_json"] = json.dumps(
        verified_sources,
        ensure_ascii=False,
        indent=2,
    )
    callback_context.state["tool_call_log_path"] = "tt/logs/tool_calls.jsonl"

    verified_after_count = len(seen_urls)
    log_tool_call(
        tool_name="google_search",
        agent_name=agent_name,
        input_summary=(
            f"profile={summarize_text(callback_context.state.get('user_profile_json'))}; "
            f"syllabus={summarize_text(callback_context.state.get('syllabus_json'))}"
        ),
        output_summary=f"Verified {verified_after_count} unique source URLs.",
        success=verified_after_count > 0,
        latency_ms=elapsed_ms(start_time),
        error_category=None
        if verified_after_count > 0
        else "no_verified_sources"
        if raw_url_count
        else "no_grounding_metadata",
        metadata={
            "raw_url_count": raw_url_count,
            "skipped_redirect_count": skipped_redirect_count,
            "failed_validation_count": failed_validation_count,
            "verified_before_count": verified_before_count,
            "verified_after_count": verified_after_count,
            "new_verified_count": max(0, verified_after_count - verified_before_count),
        },
    )


def save_curriculum_bundle_callback(
    callback_context: CallbackContext,
) -> Content:
    raw_bundle = callback_context.state.get("curriculum_bundle")
    if not raw_bundle:
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "curriculum_writer_agent"),
            input_summary="curriculum_bundle missing",
            output_summary="No curriculum bundle was available to save.",
            success=False,
            error_category="missing_curriculum_bundle",
        )
        callback_context.state["generated_curriculum_report"] = (
            "No curriculum bundle was available to save."
        )
        return Content()

    bundle = _normalize_bundle(raw_bundle)
    violations = find_many_guardrail_violations(_bundle_guardrail_values(bundle))
    if violations:
        formatted_violations = format_guardrail_violations(violations)
        callback_context.state["guardrail_blocked"] = True
        callback_context.state["guardrail_violations_report"] = formatted_violations
        callback_context.state["saved_artifacts_summary"] = json.dumps([])
        callback_context.state["generated_curriculum_report"] = (
            "Curriculum generation was blocked by guardrails. No files were saved.\n\n"
            f"{REFUSAL_MESSAGE}\n\n"
            "Detected policy categories:\n"
            f"{formatted_violations}"
        )
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "curriculum_writer_agent"),
            input_summary=bundle.learner_summary,
            output_summary=formatted_violations,
            success=False,
            error_category="guardrail_violation",
            metadata={"violation_count": len(violations)},
        )
        return Content()

    verified_urls = _verified_source_urls(callback_context)
    unverified_urls = _find_unverified_bundle_urls(bundle, verified_urls)
    if unverified_urls:
        formatted_unverified = json.dumps(
            unverified_urls,
            ensure_ascii=False,
            indent=2,
        )
        _annotate_unverified_bundle_urls(bundle, unverified_urls)
        callback_context.state["source_integrity_warning"] = True
        callback_context.state["source_integrity_report"] = formatted_unverified
        log_tool_call(
            tool_name="source_integrity_check",
            agent_name=_agent_name(callback_context, "curriculum_writer_agent"),
            input_summary=bundle.learner_summary,
            output_summary=(
                "Some lesson URLs were not verified. Curriculum will be saved "
                "with caution notes.\n"
                f"{formatted_unverified}"
            ),
            success=True,
            metadata={
                "verified_url_count": len(verified_urls),
                "affected_file_count": len(unverified_urls),
                "warning_category": "unverified_url",
            },
        )
    else:
        log_tool_call(
            tool_name="source_integrity_check",
            agent_name=_agent_name(callback_context, "curriculum_writer_agent"),
            input_summary=bundle.learner_summary,
            output_summary="All lesson URLs are present in the verified source list.",
            success=True,
            metadata={
                "verified_url_count": len(verified_urls),
                "file_count": len(bundle.files),
            },
        )

    log_tool_call(
        tool_name="guardrail_check",
        agent_name=_agent_name(callback_context, "curriculum_writer_agent"),
        input_summary=bundle.learner_summary,
        output_summary="Curriculum bundle passed guardrail scan.",
        success=True,
        metadata={"file_count": len(bundle.files)},
    )

    session_dir = create_curriculum_session_dir(bundle.learner_summary)
    relative_session_dir = f"tt/{session_dir.parent.name}/{session_dir.name}"
    callback_context.state["generated_curriculum_dir"] = str(relative_session_dir)

    saved_files: list[str] = []
    for file in bundle.files:
        save_text_file(file.filename, file.content, session_dir=str(session_dir))
        saved_files.append(
            f"{relative_session_dir}/{safe_curriculum_filename(file.filename)}"
        )

    callback_context.state["saved_artifacts_summary"] = json.dumps(saved_files)
    callback_context.state["generated_curriculum_report"] = _build_report(
        bundle,
        artifact_dir=str(relative_session_dir),
    )
    if unverified_urls:
        callback_context.state["generated_curriculum_report"] += (
            "\n\nSource verification warning:\n"
            "Some files include references that could not be verified automatically. "
            "Those files were saved with '[Resources not verified - use caution]' "
            "in the title and a warning note near the top."
        )
    try:
        dashboard_result = refresh_canvas_dashboard(
            agent_name="dashboard_manager_agent"
        )
        callback_context.state["generated_dashboard_report"] = (
            f"Dashboard refreshed at {dashboard_result['dashboard_path']} "
            f"with {dashboard_result['course_count']} course card(s)."
        )
    except (OSError, ValueError) as exc:
        callback_context.state["generated_dashboard_report"] = (
            f"Dashboard refresh failed after curriculum save: {exc}"
        )
    return Content()


def save_quiz_bundle_callback(
    callback_context: CallbackContext,
) -> Content:
    raw_bundle = callback_context.state.get("quiz_bundle")
    if not raw_bundle:
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "quiz_generator_agent"),
            input_summary="quiz_bundle missing",
            output_summary="No quiz bundle was available to save.",
            success=False,
            error_category="missing_quiz_bundle",
        )
        callback_context.state["generated_quiz_report"] = (
            "No quiz bundle was available to save."
        )
        return Content()

    bundle = _normalize_quiz_bundle(raw_bundle)
    violations = find_many_guardrail_violations(_quiz_guardrail_values(bundle))
    if violations:
        formatted_violations = format_guardrail_violations(violations)
        callback_context.state["guardrail_blocked"] = True
        callback_context.state["guardrail_violations_report"] = formatted_violations
        callback_context.state["generated_quiz_report"] = (
            "Quiz generation was blocked by guardrails. No quiz file was saved.\n\n"
            f"{REFUSAL_MESSAGE}\n\n"
            "Detected policy categories:\n"
            f"{formatted_violations}"
        )
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "quiz_generator_agent"),
            input_summary=bundle.quiz_title,
            output_summary=formatted_violations,
            success=False,
            error_category="guardrail_violation",
            metadata={"violation_count": len(violations)},
        )
        return Content()

    quiz_html = _build_quiz_html(bundle)
    save_text_file(
        "quiz.html",
        quiz_html,
        session_dir=bundle.source_session_dir,
        agent_name="quiz_generator_agent",
    )
    quiz_path = f"{bundle.source_session_dir}/quiz.html"
    callback_context.state["generated_quiz_html"] = quiz_path
    callback_context.state["generated_quiz_report"] = (
        f"Quiz saved to {quiz_path}. It includes navigation for "
        f"{len(bundle.units)} unit quiz section(s)."
    )
    try:
        dashboard_result = refresh_canvas_dashboard(
            agent_name="dashboard_manager_agent"
        )
        callback_context.state["generated_quiz_report"] += (
            f" Dashboard and course page links refreshed at "
            f"{dashboard_result['dashboard_path']}."
        )
    except (OSError, ValueError) as exc:
        callback_context.state["generated_quiz_report"] += (
            f" Dashboard refresh failed: {exc}"
        )
    log_tool_call(
        tool_name="guardrail_check",
        agent_name=_agent_name(callback_context, "quiz_generator_agent"),
        input_summary=bundle.quiz_title,
        output_summary="Quiz bundle passed guardrail scan.",
        success=True,
        metadata={"unit_count": len(bundle.units), "quiz_path": quiz_path},
    )
    return Content()


def save_course_page_bundle_callback(
    callback_context: CallbackContext,
) -> Content:
    raw_bundle = callback_context.state.get("course_page_bundle")
    if not raw_bundle:
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "course_page_generator_agent"),
            input_summary="course_page_bundle missing",
            output_summary="No course page bundle was available to save.",
            success=False,
            error_category="missing_course_page_bundle",
        )
        callback_context.state["generated_course_page_report"] = (
            "No course page bundle was available to save."
        )
        return Content()

    bundle = _normalize_course_page_bundle(raw_bundle)
    try:
        _hydrate_course_page_units(bundle)
    except (OSError, ValueError) as exc:
        callback_context.state["generated_course_page_report"] = (
            "Course page generation failed because one or more source unit files "
            f"could not be loaded: {exc}"
        )
        log_tool_call(
            tool_name="file_io.load_course_page_source_files",
            agent_name=_agent_name(callback_context, "course_page_generator_agent"),
            input_summary=bundle.source_session_dir,
            output_summary=str(exc),
            success=False,
            error_category="file_io_error",
            error_message=str(exc),
            metadata={"unit_count": len(bundle.units)},
        )
        return Content()

    violations = find_many_guardrail_violations(_course_page_guardrail_values(bundle))
    if violations:
        formatted_violations = format_guardrail_violations(violations)
        callback_context.state["guardrail_blocked"] = True
        callback_context.state["guardrail_violations_report"] = formatted_violations
        callback_context.state["generated_course_page_report"] = (
            "Course page generation was blocked by guardrails. "
            "No course page file was saved.\n\n"
            f"{REFUSAL_MESSAGE}\n\n"
            "Detected policy categories:\n"
            f"{formatted_violations}"
        )
        log_tool_call(
            tool_name="guardrail_check",
            agent_name=_agent_name(callback_context, "course_page_generator_agent"),
            input_summary=bundle.course_title,
            output_summary=formatted_violations,
            success=False,
            error_category="guardrail_violation",
            metadata={"violation_count": len(violations)},
        )
        return Content()

    course_html = _build_course_page_html(bundle)
    save_text_file(
        "course_page.html",
        course_html,
        session_dir=bundle.source_session_dir,
        agent_name="course_page_generator_agent",
    )
    course_page_path = f"{bundle.source_session_dir}/course_page.html"
    callback_context.state["generated_course_page_html"] = course_page_path
    callback_context.state["generated_course_page_report"] = (
        f"Course page saved to {course_page_path}. It displays "
        f"{len(bundle.units)} unit lesson section(s) in a Canvas-style layout."
    )
    try:
        dashboard_result = refresh_canvas_dashboard(
            agent_name="dashboard_manager_agent"
        )
        callback_context.state["generated_course_page_report"] += (
            f" Dashboard refreshed at {dashboard_result['dashboard_path']}."
        )
    except (OSError, ValueError) as exc:
        callback_context.state["generated_course_page_report"] += (
            f" Dashboard refresh failed: {exc}"
        )
    log_tool_call(
        tool_name="guardrail_check",
        agent_name=_agent_name(callback_context, "course_page_generator_agent"),
        input_summary=bundle.course_title,
        output_summary="Course page bundle passed guardrail scan.",
        success=True,
        metadata={
            "unit_count": len(bundle.units),
            "course_page_path": course_page_path,
        },
    )
    return Content()
