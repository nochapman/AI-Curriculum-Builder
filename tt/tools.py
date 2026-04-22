import re
from pathlib import Path


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


def save_curriculum_artifact(filename: str, content: str) -> str:
    """Save a curriculum artifact to tt/long_term_memory."""
    target_dir = _ensure_memory_dir()
    safe_name = _safe_filename(filename)
    file_path = target_dir / safe_name
    file_path.write_text(_normalize_text_content(content), encoding="utf-8")
    return f"Saved curriculum artifact to {file_path}"


def save_module_to_disk(unit_order: int, unit_title: str, content: str) -> str:
    """Save a generated unit module to tt/long_term_memory with a stable filename."""
    target_dir = _ensure_memory_dir()
    safe_title = _slugify(unit_title)
    file_path = target_dir / f"unit_{int(unit_order):02d}_{safe_title}.md"
    file_path.write_text(_normalize_text_content(content), encoding="utf-8")
    return f"Saved module to {file_path}"


def save_text_file(filename: str, content: str) -> str:
    """Save any curriculum-related text file into tt/long_term_memory."""
    target_dir = _ensure_memory_dir()
    safe_name = _safe_filename(filename)
    file_path = target_dir / safe_name
    file_path.write_text(_normalize_text_content(content), encoding="utf-8")
    return f"Saved text file to {file_path}"
