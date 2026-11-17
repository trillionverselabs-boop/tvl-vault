from pathlib import Path

import pytest

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


# `popup` is one family of plugin-test screenshot (the plan's junk list:
# "~130 `plugintest*` / `plugin*` / `popup*` / `readme*` screenshots"). The old
# pattern `^popup[a-z0-9_]*$` matched `popupd3.jpg` but not the browser's
# re-download `popupd1-2.jpg`, so ten real screenshots were shown on the wall
# and offered to the caption model. The family is `popup` followed by its
# serial — digits, `_small`, or a download counter — and nothing else.
@pytest.mark.parametrize("name", [
    "popupd1-2.jpg", "popupc-2.jpg", "popupd_small.png", "popupd14-2.jpg",
])
def test_a_popup_screenshot_is_junk_whatever_the_browser_appended(name):
    assert sources.is_junk_name(name) is True, name


@pytest.mark.parametrize("name", [
    "popupshire.png",      # a real picture that merely starts with "popup"
    "calvin.png", "orgchart.jpg", "validizea.jpg",
])
def test_a_real_image_is_not_junk(name):
    assert sources.is_junk_name(name) is False, name


def test_excluded_directories_are_skipped(tmp_path):
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    _touch(nested, "index.js", b"x")
    _touch(tmp_path, "real.md", b"# real\n")
    names = [d.path.name for d in sources.scan(tmp_path)]
    assert "real.md" in names
    assert "index.js" not in names


# The name-key rule exists for one case: a browser's second download of the same
# file (`doc (1).pdf`), whose bytes differ because PDF metadata changes. It must
# not fold two different documents that merely share a common filename — the
# corpus has 13 `README.md` files and they are 13 different documents.
def test_same_named_files_in_different_folders_are_not_duplicates(tmp_path):
    a = tmp_path / "one"
    b = tmp_path / "two"
    a.mkdir()
    b.mkdir()
    _touch(a, "README.md", b"# One\n")
    _touch(b, "README.md", b"# Two, entirely different\n")
    mds = [d for d in sources.scan(tmp_path) if d.kind == "markdown"]
    assert len(mds) == 2
    assert all(d.duplicates == [] for d in mds)


def test_a_browser_redownload_folds_onto_the_plain_name(tmp_path):
    _touch(tmp_path, "doc.pdf", b"%PDF-1.4 first save")
    _touch(tmp_path, "doc (1).pdf", b"%PDF-1.4 second save, same document")
    pdfs = [d for d in sources.scan(tmp_path) if d.kind == "pdf"]
    assert len(pdfs) == 1
    assert pdfs[0].path.name == "doc.pdf"
    assert [p.name for p in pdfs[0].duplicates] == ["doc (1).pdf"]
