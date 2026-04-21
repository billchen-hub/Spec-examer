"""Load spec content from files and folders.

Supports:
  - Text formats: .md / .txt / .log (read as UTF-8, with latin-1 fallback)
  - PDF: .pdf (text extraction via pypdf)

Inputs can be individual files or directories. Directories are scanned
recursively; supported files are collected in sorted path order so the
combined content is deterministic.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

TEXT_EXTS = {".md", ".txt", ".log"}
PDF_EXTS = {".pdf"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS

# Directory / file names to skip during recursive scans.
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
_SKIP_FILES = {".gitkeep", ".gitignore", ".DS_Store"}


class SpecLoadError(Exception):
    """Raised when a spec input cannot be loaded."""


def _is_supported(filename: str) -> bool:
    if filename in _SKIP_FILES:
        return False
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTS


def collect_spec_files(paths: Iterable[str]) -> List[str]:
    """Expand a list of paths (files or directories) into spec file paths.

    - Files are included directly if the extension is supported.
    - Directories are walked recursively; supported files only.
    - Raises SpecLoadError if a path does not exist or an explicit file has
      an unsupported extension. Unsupported files inside a directory are
      silently skipped so mixed folders still work.

    Deduplication uses `os.path.realpath`, so the same file reached via a
    symlink/junction/case-different path is read only once. `paths` is
    consumed once.
    """
    collected: List[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        key = os.path.realpath(path)
        if key in seen:
            return
        seen.add(key)
        collected.append(path)

    for raw in paths:
        if not raw:
            continue
        path = os.path.abspath(raw)
        if not os.path.exists(path):
            raise SpecLoadError(f"Path not found: {raw}")

        if os.path.isfile(path):
            if not _is_supported(os.path.basename(path)):
                raise SpecLoadError(
                    f"Unsupported file type: {raw} "
                    f"(supported: {', '.join(sorted(SUPPORTED_EXTS))})"
                )
            _add(path)
            continue

        # Directory — walk recursively. followlinks stays False (default) so
        # symlinked sub-directories don't cause loops.
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in sorted(filenames):
                if not _is_supported(name):
                    continue
                _add(os.path.join(dirpath, name))

    collected.sort()
    return collected


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Fallback so rare non-UTF8 logs/txt still load rather than crashing.
        with open(path, "r", encoding="latin-1") as f:
            return f.read()


def _read_pdf_file(path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise SpecLoadError(
            "pypdf is required for PDF input. Install with: pip install pypdf"
        ) from e

    try:
        reader = PdfReader(path)
    except Exception as e:
        raise SpecLoadError(f"Failed to open PDF {path}: {e}") from e

    parts: List[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            parts.append(f"[Page {i}]\n{text}")

    if not parts:
        # Scanned PDF without OCR, or otherwise empty after extraction.
        logger.warning(
            "No extractable text in PDF: %s (scanned/image-only PDF? consider OCR)",
            path,
        )
    return "\n\n".join(parts)


def read_spec_file(path: str) -> str:
    """Read a single spec file and return its text content."""
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        return _read_pdf_file(path)
    if ext in TEXT_EXTS:
        return _read_text_file(path)
    raise SpecLoadError(f"Unsupported file type: {path}")


def load_spec_content(
    paths: Iterable[str],
    base_dir: str | None = None,
) -> Dict:
    """Collect, read, and combine spec files.

    Returns a dict:
        {
            "files":    [(display_name, text), ...],
            "combined": "--- FILE: a.md ---\n\n<a>\n\n--- FILE: b.md ---\n\n<b>",
            "total_chars": <int>,
        }

    `display_name` is the file's path relative to `base_dir` if provided and
    the file lives under it; otherwise it is the basename. Used only for the
    file-separator header the AI sees.
    """
    files = collect_spec_files(paths)
    if not files:
        raise SpecLoadError(
            "No supported spec files found "
            f"(looked for: {', '.join(sorted(SUPPORTED_EXTS))})"
        )

    base_abs = os.path.abspath(base_dir) if base_dir else None
    entries: List[Tuple[str, str]] = []
    parts: List[str] = []
    non_empty = 0

    for path in files:
        text = read_spec_file(path)
        if not text.strip():
            text = ""
            logger.warning("Spec file produced no text: %s", path)
        else:
            non_empty += 1

        if base_abs and path.startswith(base_abs + os.sep):
            display = os.path.relpath(path, base_abs).replace(os.sep, "/")
        else:
            display = os.path.basename(path)

        entries.append((display, text))
        parts.append(f"--- FILE: {display} ---\n\n{text}")

    if non_empty == 0:
        raise SpecLoadError(
            f"All {len(files)} spec file(s) produced no extractable text "
            "(scanned PDFs without OCR, or empty files?). Aborting so the "
            "AI isn't asked to generate questions from nothing."
        )

    combined = "\n\n".join(parts)
    return {
        "files": entries,
        "combined": combined,
        "total_chars": len(combined),
    }
