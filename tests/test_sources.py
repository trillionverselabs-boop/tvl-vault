from pathlib import Path

from vault import sources


def _touch(d: Path, name: str, data: bytes) -> Path:
    p = d / name
    p.write_bytes(data)
    return p


def test_kind_is_decided_by_extension():
    assert sources.kind_of(Path("a.pdf")) == "pdf"
    assert sources.kind_of(Path("a.docx")) == "docx"
    assert sources.kind_of(Path("a.md")) == "markdown"
    assert sources.kind_of(Path("a.html")) == "html"
    assert sources.kind_of(Path("a.csv")) == "csv"
    assert sources.kind_of(Path("a.jpg")) == "image"
    assert sources.kind_of(Path("a.xyz")) == "other"


def test_identical_files_collapse_to_one_document(tmp_path):
    data = b"%PDF-1.4 same bytes"
    _touch(tmp_path, "a.pdf", data)
    _touch(tmp_path, "b.pdf", data)
    pdfs = [d for d in sources.scan(tmp_path) if d.kind == "pdf"]
    assert len(pdfs) == 1
    assert len(pdfs[0].duplicates) == 1


def test_markdown_files_are_all_kept(tmp_path):
    _touch(tmp_path, "a.md", b"# A\n")
    _touch(tmp_path, "b.md", b"# B\n")
    assert len([d for d in sources.scan(tmp_path) if d.kind == "markdown"]) == 2


def test_junk_screenshots_are_flagged_not_dropped(tmp_path):
    _touch(tmp_path, "plugintest5a.jpg", b"\xff\xd8\xff")
    _touch(tmp_path, "calvin.png", b"\x89PNG\r\n\x1a\n")
    docs = {d.path.name: d for d in sources.scan(tmp_path)}
    assert docs["plugintest5a.jpg"].is_junk is True
    assert docs["calvin.png"].is_junk is False


def test_excluded_directories_are_skipped(tmp_path):
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    _touch(nested, "index.js", b"x")
    _touch(tmp_path, "real.md", b"# real\n")
    names = [d.path.name for d in sources.scan(tmp_path)]
    assert "real.md" in names
    assert "index.js" not in names
