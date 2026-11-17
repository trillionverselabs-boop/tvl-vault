"""Enumerate the corpus: what exists, what kind it is, which copies are duplicates."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import is_excluded_dir

EXT_KIND = {
    ".pdf": "pdf", ".docx": "docx", ".md": "markdown", ".markdown": "markdown",
    ".html": "html", ".htm": "html", ".csv": "csv", ".txt": "text",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
}

# Plugin-test screenshots and build screenshots: index them as artifacts so the
# graph does not silently drop them, but never treat them as doctrine.
#
# The serial part is bounded (`[a-z0-9_]*`, not `.*`) so a real picture whose
# name merely starts with a family word — `popupshire.png` — stays content.
# The browser's re-download counter (`popupd1-2`, `popupd (1)`) is part of the
# serial, which is why the old `$`-anchored `popup` pattern missed ten files.
JUNK_PATTERNS = [
    r"^plugintest", r"^plugin\d", r"^pluginblogtest",
    # `popup` + one letter (a–d on disk) + an optional serial: `popupd`,
    # `popupd1`, `popupd_small`, `popupd1-2`. The letter is a single character
    # and the tail is only digits/`_small`/a download counter, so a real picture
    # named `popupshire` (letter `s` + letters) is not caught.
    r"^popup[a-z](?:_small|\d{0,3}(?:[-_ ]\d{1,3})?)$",
    r"^readme\d", r"^b\d_part\d", r"^s\d+$",
]


@dataclass
class Document:
    path: Path
    kind: str
    sha256: str
    size: int
    title: str = ""
    is_junk: bool = False
    duplicates: list[Path] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (self.title or self.path.stem).lower()).strip("-")


def kind_of(path: Path) -> str:
    return EXT_KIND.get(path.suffix.lower(), "other")


def is_junk_name(name: str) -> bool:
    stem = Path(name).stem
    return any(re.match(p, stem, re.I) for p in JUNK_PATTERNS)


def scan(root: Path) -> list[Document]:
    """Every supported file under *root*, duplicates collapsed.

    Two passes. Byte-identical files collapse by sha256. Then a browser's
    download suffix — `doc (1).pdf`, `doc-2.pdf` — collapses onto the plain
    name: those copies are the same document saved twice, but their bytes
    differ (PDF metadata), so sha256 alone keeps them apart and the same
    doctrine ends up indexed three times.
    """
    by_hash: dict[str, list[Path]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or kind_of(p) == "other":
            continue
        if any(is_excluded_dir(part) for part in p.relative_to(root).parts):
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(p)

    # name key -> canonical path. A browser's second download (`doc (1).pdf`)
    # has different bytes, so it never shares a hash group with `doc.pdf`;
    # this second pass folds it onto the plain name. A file whose name carries
    # no download counter is never folded — 13 different `README.md` files are
    # 13 documents, not one.
    by_name: dict[tuple[str, str], Path] = {}
    docs: list[Document] = []
    prepared = []
    for h, paths in by_hash.items():
        canonical = _plainest(paths)
        prepared.append((h, canonical, [p for p in paths if p != canonical]))
    # plain names first, so `doc.pdf` claims the key before `doc (1).pdf` arrives
    prepared.sort(key=lambda t: (0 if _DOWNLOAD_SUFFIX_RE.match(t[1].stem) is None else 1, t[1].name))
    for h, canonical, rest in prepared:
        key = (kind_of(canonical), _name_key(canonical.name))
        if _DOWNLOAD_SUFFIX_RE.match(canonical.stem) and key in by_name:
            existing = next(d for d in docs if d.path == by_name[key])
            existing.duplicates.extend([canonical] + rest)
            continue
        by_name[key] = canonical
        docs.append(Document(
            path=canonical, kind=kind_of(canonical), sha256=h, size=canonical.stat().st_size,
            is_junk=is_junk_name(canonical.name), duplicates=rest,
        ))
    return docs


def _plainest(paths: list[Path]) -> Path:
    """The path with no download counter in its name; the first sorted if none."""
    for p in paths:
        if _DOWNLOAD_SUFFIX_RE.match(p.stem) is None:
            return p
    return paths[0]


# `name (1)`, `name-2`, `name 1` — a browser's second download of the same file.
_DOWNLOAD_SUFFIX_RE = re.compile(r"^(.*?)\s*(?:\(\d+\)|[-_ ]\d+)$")


def _name_key(name: str) -> str:
    """The filename with any download counter removed, for duplicate matching."""
    stem = Path(name).stem
    m = _DOWNLOAD_SUFFIX_RE.match(stem)
    base = m.group(1).strip() if m else stem
    return re.sub(r"\s+", " ", base).strip().lower()
