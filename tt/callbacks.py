import json
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.genai.types import Content

from .schemas import CurriculumBundle
from .tools import save_text_file


def _normalize_bundle(raw_bundle: Any) -> CurriculumBundle:
    if isinstance(raw_bundle, CurriculumBundle):
        return raw_bundle
    if isinstance(raw_bundle, str):
        return CurriculumBundle.model_validate_json(raw_bundle)
    if hasattr(raw_bundle, "model_dump"):
        return CurriculumBundle.model_validate(raw_bundle.model_dump())
    return CurriculumBundle.model_validate(raw_bundle)


def _build_report(bundle: CurriculumBundle) -> str:
    lines = [
        f"Learner summary: {bundle.learner_summary}",
        "",
        "Saved files:",
    ]
    for file in bundle.files:
        lines.append(f"- {file.filename}: {file.summary}")

    if bundle.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        for assumption in bundle.assumptions:
            lines.append(f"- {assumption}")

    return "\n".join(lines)


def collect_verified_sources_callback(
    callback_context: CallbackContext,
) -> None:
    """Extract canonical web URLs from grounding metadata and store them in state."""
    session = callback_context._invocation_context.session
    seen_urls = callback_context.state.get("verified_source_urls", {})

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

            url = web.uri
            if "vertexaisearch.cloud.google.com/grounding-api-redirect/" in url:
                continue

            seen_urls[url] = {
                "title": getattr(web, "title", "") or getattr(web, "domain", url),
                "domain": getattr(web, "domain", ""),
                "url": url,
            }

    verified_sources = list(seen_urls.values())
    callback_context.state["verified_source_urls"] = seen_urls
    callback_context.state["verified_sources_json"] = json.dumps(
        verified_sources,
        ensure_ascii=False,
        indent=2,
    )


def save_curriculum_bundle_callback(
    callback_context: CallbackContext,
) -> Content:
    raw_bundle = callback_context.state.get("curriculum_bundle")
    if not raw_bundle:
        callback_context.state["generated_curriculum_report"] = (
            "No curriculum bundle was available to save."
        )
        return Content()

    bundle = _normalize_bundle(raw_bundle)

    saved_files: list[str] = []
    for file in bundle.files:
        save_text_file(file.filename, file.content)
        saved_files.append(file.filename)

    callback_context.state["saved_artifacts_summary"] = json.dumps(saved_files)
    callback_context.state["generated_curriculum_report"] = _build_report(bundle)
    return Content()
