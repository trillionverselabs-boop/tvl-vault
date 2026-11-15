"""Extract text and sections from every source kind. No third-party packages.

PDF   -> poppler `pdftotext -layout` (already installed, no pip).
DOCX  -> zipfile + ElementTree (a .docx is a zip).
HTML  -> html.parser (strip script/style).
CSV   -> csv.reader.
Image -> no text layer; captions come from the vision pass (Task 9).
"""

from __future__ import annotations

import csv
import html
import io
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .sources import kind_of


@dataclass
class Section:
    title: str
    level: int
    body: str
    line: int = 0

    @property
    def plain(self) -> str:
        return f"{self.title}\n{self.body}".strip()


@dataclass
class Extracted:
    path: Path
    kind: str
    title: str
    text: str
    sections: list[Section]
    meta: dict = field(default_factory=dict)
    rag: dict = field(default_factory=dict)
    error: str = ""


def pdf_text(path: Path) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True, timeout=180,
    )
    if out.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {path.name}: {out.stderr.strip()}")
    return out.stdout


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines: list[str] = []
    for p in root.iter(f"{ns}p"):
        txt = "".join(t.text or "" for t in p.iter(f"{ns}t"))
        if txt.strip():
            lines.append(txt.strip())
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "h1", "h2", "h3", "li", "br", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(path: Path) -> str:
    p = _TextExtractor()
    p.feed(path.read_text("utf-8", "ignore"))
    return html.unescape("".join(p.parts))


# ── section splitters ────────────────────────────────────────────────
# The TVL doctrine PDFs use three conventions, so all three are recognised.
_SECTION_RE = re.compile(r"^SECTION\s+(\d+)\s+—\s+(.+?)\s*$", re.M)
_NUM_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z][A-Za-z].*?)\s*$", re.M)
_MD_H_RE = re.compile(r"^(#{1,3})\s+\*?\*?(.+?)\*?\*?\s*$", re.M)


def _sections_from_marks(text: str, marks: list[tuple[int, int, str]]) -> list[Section]:
    marks = sorted(marks)
    secs: list[Section] = []
    prev = -1
    for pos, level, title in marks:
        if prev >= 0 and pos - prev < 4:
            continue
        prev = pos
        end = len(text)
        for p2, _, _ in marks:
            if p2 > pos:
                end = p2
                break
        body = text[pos:end]
        body = body[body.find("\n") + 1:] if "\n" in body else ""
        secs.append(Section(title=title, level=level, body=body.strip(),
                            line=text[:pos].count("\n")))
    return secs


def split_pdf_text(text: str) -> list[Section]:
    marks: list[tuple[int, int, str]] = []
    for m in _SECTION_RE.finditer(text):
        marks.append((m.start(), 1, m.group(2).strip()))
    for m in _NUM_RE.finditer(text):
        marks.append((m.start(), 2, m.group(2).strip()))
    for m in re.finditer(r"^#\s+(.+?)\s*$", text, re.M):
        marks.append((m.start(), 1, m.group(1).strip().strip("*")))
    return _sections_from_marks(text, marks)


def split_markdown(text: str) -> list[Section]:
    marks: list[tuple[int, int, str]] = []
    for m in _MD_H_RE.finditer(text):
        marks.append((m.start(), len(m.group(1)), m.group(2).strip().strip("*")))
    return _sections_from_marks(text, marks)


_HEADER_KEYS = {
    "Document Title:": "title", "Version:": "version", "Owner:": "owner",
    "System / Layer:": "layer", "Status:": "status", "Mission:": "mission",
    "Purpose:": "purpose",
}


def parse_header(text: str) -> dict:
    meta: dict[str, str] = {}
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines[:200]):
        for key, field_name in _HEADER_KEYS.items():
            if line == key and i + 1 < len(lines):
                meta[field_name] = lines[i + 1]
    m = re.search(r"STATUS:\s*(Canonical Doctrine[^\n]*)", text)
    if m:
        meta["status"] = m.group(1).strip()
    return meta


def parse_rag_tag(text: str) -> dict:
    """The RAG TAG BLOCK is the dependency graph in plain text."""
    tag: dict = {}
    m = re.search(r"RAG TAG BLOCK(.*?)(?:\n\s*\n|\Z)", text, re.S)
    if not m:
        return tag
    block = m.group(1)
    for key, field_name in (("ENTITY:", "entity"), ("INTENT:", "intent"),
                            ("DEPENDENCY:", "dependency"), ("AU2I_INDEX:", "au2i")):
        mm = re.search(rf"{re.escape(key)}\s*(.+)", block)
        if mm:
            tag[field_name] = [x.strip() for x in mm.group(1).split(",") if x.strip()]
    mv = re.search(r"VALIDITY:\s*(.+)", block)
    if mv:
        tag["validity"] = mv.group(1).strip()
    return tag


def extract_document(path: Path, kind: str) -> Extracted:
    if kind == "pdf":
        text = pdf_text(path)
        return Extracted(path, kind, path.stem, text, split_pdf_text(text),
                         parse_header(text), parse_rag_tag(text))
    if kind == "docx":
        text = docx_text(path)
        return Extracted(path, kind, path.stem, text, split_pdf_text(text),
                         parse_header(text), parse_rag_tag(text))
    if kind == "markdown":
        text = path.read_text("utf-8", "ignore")
        secs = split_markdown(text)
        # the first H1 is the document's own title; the filename is only a fallback
        title = next((s.title for s in secs if s.level == 1), path.stem)
        return Extracted(path, kind, title, text, secs, parse_header(text), {})
    if kind == "html":
        raw = path.read_text("utf-8", "ignore")
        title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
        return Extracted(path, kind, html.unescape(title.group(1).strip()) if title else path.stem,
                         html_text(path), [], {}, {})
    if kind == "csv":
        rows = list(csv.reader(io.StringIO(path.read_text("utf-8", "ignore"))))
        body = "\n".join(" | ".join(r) for r in rows if any(c.strip() for c in r))
        return Extracted(path, kind, path.stem, body, [Section("rows", 1, body)], {}, {})
    return Extracted(path, kind, path.stem, "", [], {}, {})
