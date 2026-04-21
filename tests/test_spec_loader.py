import os

import pytest

from spec_loader import (
    SpecLoadError,
    collect_spec_files,
    load_spec_content,
    read_spec_file,
)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestCollectSpecFiles:
    def test_single_file_included(self, tmp_path):
        p = tmp_path / "a.md"
        _write(str(p), "hello")
        assert collect_spec_files([str(p)]) == [str(p)]

    def test_unsupported_file_raises(self, tmp_path):
        p = tmp_path / "data.csv"
        _write(str(p), "a,b")
        with pytest.raises(SpecLoadError):
            collect_spec_files([str(p)])

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(SpecLoadError):
            collect_spec_files([str(tmp_path / "nope.md")])

    def test_directory_scanned_recursively(self, tmp_path):
        _write(str(tmp_path / "root.md"), "root")
        _write(str(tmp_path / "sub" / "a.md"), "a")
        _write(str(tmp_path / "sub" / "deeper" / "b.txt"), "b")
        _write(str(tmp_path / "ignore.csv"), "nope")

        result = collect_spec_files([str(tmp_path)])
        names = {os.path.basename(p) for p in result}
        assert names == {"root.md", "a.md", "b.txt"}
        # Result must be sorted (by full path) for deterministic combined output.
        assert result == sorted(result)

    def test_skip_dirs_ignored(self, tmp_path):
        _write(str(tmp_path / "keep.md"), "x")
        _write(str(tmp_path / ".git" / "config.md"), "no")
        _write(str(tmp_path / "__pycache__" / "cached.md"), "no")

        result = collect_spec_files([str(tmp_path)])
        assert len(result) == 1
        assert result[0].endswith("keep.md")

    def test_mixed_inputs_deduplicated(self, tmp_path):
        f1 = tmp_path / "a.md"
        _write(str(f1), "a")
        f2 = tmp_path / "sub" / "b.md"
        _write(str(f2), "b")

        # Pass the folder AND one of its files; should not duplicate.
        result = collect_spec_files([str(tmp_path), str(f1)])
        assert result.count(str(f1)) == 1
        assert str(f2) in result

    def test_empty_dir_returns_empty(self, tmp_path):
        result = collect_spec_files([str(tmp_path)])
        assert result == []


class TestReadSpecFile:
    def test_read_markdown(self, tmp_path):
        p = tmp_path / "a.md"
        _write(str(p), "# hi\n")
        assert read_spec_file(str(p)) == "# hi\n"

    def test_read_txt(self, tmp_path):
        p = tmp_path / "a.txt"
        _write(str(p), "plain")
        assert read_spec_file(str(p)) == "plain"

    def test_unsupported_extension_raises(self, tmp_path):
        p = tmp_path / "x.xml"
        _write(str(p), "<x/>")
        with pytest.raises(SpecLoadError):
            read_spec_file(str(p))

    def test_latin1_fallback(self, tmp_path):
        p = tmp_path / "weird.log"
        # 0xE9 is 'é' in latin-1 but invalid UTF-8 start byte in this position.
        with open(p, "wb") as f:
            f.write(b"caf\xe9")
        assert read_spec_file(str(p)) == "café"

    def test_pdf_with_no_extractable_text_returns_empty(self, tmp_path):
        # A blank-page PDF has no extractable text — the loader should return
        # an empty string (and log a warning, not raise).
        from pypdf import PdfWriter
        p = tmp_path / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        with open(p, "wb") as f:
            writer.write(f)
        assert read_spec_file(str(p)) == ""


class TestLoadSpecContent:
    def test_combines_multiple_files_with_headers(self, tmp_path):
        _write(str(tmp_path / "a.md"), "AAA")
        _write(str(tmp_path / "b.md"), "BBB")

        result = load_spec_content([str(tmp_path)], base_dir=str(tmp_path))
        assert len(result["files"]) == 2
        assert "--- FILE: a.md ---" in result["combined"]
        assert "--- FILE: b.md ---" in result["combined"]
        assert "AAA" in result["combined"]
        assert "BBB" in result["combined"]
        assert result["total_chars"] == len(result["combined"])

    def test_empty_inputs_raise(self, tmp_path):
        with pytest.raises(SpecLoadError):
            load_spec_content([str(tmp_path)])

    def test_display_name_uses_relative_path_under_base(self, tmp_path):
        _write(str(tmp_path / "sub" / "chapters" / "c.md"), "content")
        result = load_spec_content([str(tmp_path)], base_dir=str(tmp_path))
        display, _ = result["files"][0]
        assert display == "sub/chapters/c.md"

    def test_display_name_falls_back_to_basename_without_base(self, tmp_path):
        p = tmp_path / "only.md"
        _write(str(p), "x")
        result = load_spec_content([str(p)])
        display, _ = result["files"][0]
        assert display == "only.md"

    def test_mixed_file_and_folder_inputs(self, tmp_path):
        # User passes BOTH a standalone file AND a folder — a core advertised
        # feature of the new --generate interface.
        lone = tmp_path / "appendix.md"
        _write(str(lone), "APPENDIX")
        folder = tmp_path / "chapters"
        _write(str(folder / "intro.md"), "INTRO")
        _write(str(folder / "body.txt"), "BODY")

        result = load_spec_content([str(lone), str(folder)], base_dir=str(tmp_path))
        displays = {d for d, _ in result["files"]}
        assert displays == {"appendix.md", "chapters/intro.md", "chapters/body.txt"}
        assert "APPENDIX" in result["combined"]
        assert "INTRO" in result["combined"]
        assert "BODY" in result["combined"]

    def test_all_empty_files_raise(self, tmp_path):
        # Covers the safety net: every file came back empty -> refuse to send
        # an empty prompt to the AI.
        _write(str(tmp_path / "empty1.md"), "")
        _write(str(tmp_path / "empty2.txt"), "   \n")
        with pytest.raises(SpecLoadError):
            load_spec_content([str(tmp_path)])


class TestSkipDirsBoundary:
    def test_skip_dirs_applies_to_descendants_not_input_root(self, tmp_path):
        # Documents the intentional contract: _SKIP_DIRS prunes nested dirs
        # during a walk, but if the user EXPLICITLY passes e.g. `.git` as the
        # input root, its contents are still scanned (user knows what they want).
        git_root = tmp_path / ".git"
        _write(str(git_root / "config.md"), "explicit")

        result = collect_spec_files([str(git_root)])
        assert len(result) == 1
        assert result[0].endswith("config.md")

        # But when .git is a *child* of the input, it IS skipped.
        _write(str(tmp_path / "keep.md"), "keep")
        result2 = collect_spec_files([str(tmp_path)])
        names = {os.path.basename(p) for p in result2}
        assert "keep.md" in names
        assert "config.md" not in names
