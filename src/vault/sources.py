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
JUNK_PATTERNS = [
    r"^plugintest", r"^plugin\d", r"^pluginblogtest", r"^popup[a-z0-9_]*$",
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
    """Every supported file under *root*, with byte-identical duplicates collapsed."""
    by_hash: dict[str, list[Path]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or kind_of(p) == "other":
            continue
        if any(is_excluded_dir(part) for part in p.relative_to(root).parts):
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(p)
    docs: list[Document] = []
    for h, paths in by_hash.items():
        canonical = paths[0]
        docs.append(Document(
            path=canonical, kind=kind_of(canonical), sha256=h, size=canonical.stat().st_size,
            is_junk=is_junk_name(canonical.name), duplicates=paths[1:],
        ))
    return docs
