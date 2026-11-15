"""Images: dimensions from the file header, captions from the vision model.

No OCR is installed on this host, so an image becomes text in exactly one way:
the session model describes it (`caption`). Dimensions are read from the file's
own header — PNG's IHDR, JPEG's SOFn marker — which needs no third-party library
and keeps the build $0. A file whose header cannot be read is `None`, never an
error: one corrupt image must not stop a rebuild.

The split that matters is junk vs real. `sources.is_junk_name` marks the ~130
plugin-test screenshots; those are indexed as artifacts with dimensions and no
caption, and they never reach the model. The portraits, the org chart and the
validize renders are the wall.
"""

from __future__ import annotations

import struct
import sqlite3
from pathlib import Path

from .sources import is_junk_name

# The vision pass runs only when the wall asks for it, and only on non-junk
# images. Anything past this is a file so large the model would refuse it, and
# the wall shows it with dimensions and an empty caption rather than a failure.
MAX_CAPTION_BYTES = 8 * 1024 * 1024

_CAPTION_INSTRUCTIONS = (
    "Describe this image in one short line for a search index. Say what it shows "
    "and name any text that is legible. No more than 20 words. Plain language."
)

_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8"
_WEBP_SIG = b"RIFF"          # a RIFF container: WEBP, and WAV/AVI in principle


def mime_of(path: Path) -> str:
    """The type to send to the vision model.

    By *content*, not by extension: four files in the real corpus are WebP
    bytes named `.jpg`, and a model sent `image/jpeg` for them would refuse the
    image or mis-decode it.
    """
    p = Path(path)
    try:
        head = p.open("rb").read(32)
    except OSError:
        head = b""
    if head[:8] == _PNG_SIG:
        return "image/png"
    if head[:2] == _JPEG_SIG:
        return "image/jpeg"
    if head[:4] == _WEBP_SIG and head[8:12] == b"WEBP":
        return "image/webp"
    return _MIME.get(p.suffix.lower(), "image/png")


def sniff_kind(path: Path) -> str:
    """`png` / `jpeg` / `webp` / `""` — from the header, ignoring the extension."""
    try:
        head = Path(path).open("rb").read(32)
    except OSError:
        return ""
    if head[:8] == _PNG_SIG:
        return "png"
    if head[:2] == _JPEG_SIG:
        return "jpeg"
    if head[:4] == _WEBP_SIG and head[8:12] == b"WEBP":
        return "webp"
    return ""


def dimensions(path: Path) -> tuple[int, int] | None:
    """`(width, height)` from the file's own header, or `None`.

    Deliberately no Pillow: the header is 24 bytes for a PNG and one marker scan
    for a JPEG, and a library would be a dependency the plugin cannot declare
    (`pyproject.toml` must keep `dependencies = []`, or the desktop's
    non-interactive install refuses).
    """
    try:
        with Path(path).open("rb") as fh:
            head = fh.read(64 * 1024)
    except OSError:
        return None
    if head[:8] == _PNG_SIG:
        return _png_size(head)
    if head[:2] == _JPEG_SIG:
        return _jpeg_size(path)
    if head[:4] == _WEBP_SIG and head[8:12] == b"WEBP":
        return _webp_size(head)
    return None


def _webp_size(head: bytes) -> tuple[int, int] | None:
    """WebP's size, from the chunk that follows the `WEBP` tag.

    Three containers, one dispatch: `VP8 ` (lossy), `VP8L` (lossless) and
    `VP8X` (extended). The real corpus has WebP bytes under `.jpg` names, so the
    extension is not evidence and the header has to be read.

    Layout: `RIFF` + size + `WEBP` (12 bytes), then chunk tag at 12, chunk length
    at 16, chunk data from 20.

    The lossy `VP8 ` payload is a raw VP8 frame, not a simple header: a 3-byte
    start code, then a 14-bit width and a 14-bit height, each with a 4-bit
    scaling factor in the high bits. Files in `~/Projects/youtube-channel/
    data/research/thumbs` carry three extra bytes before the start code, so the
    start code is *found* rather than assumed at offset 0.
    """
    kind = head[12:16]
    body = head[20:]
    if kind == b"VP8 ":
        at = 0 if body[:3] == b"\x9d\x01\x2a" else body[:64].find(b"\x9d\x01\x2a")
        if at < 0 or len(body) < at + 7:
            return None
        w, h = struct.unpack("<HH", body[at + 3:at + 7])
        width, height = w & 0x3FFF, h & 0x3FFF
        return (width, height) if width and height else None
    if kind == b"VP8L":
        # `2F`, then 14 bits width-1 and 14 bits height-1 in one 32-bit word.
        if len(body) < 5 or body[0] != 0x2F:
            return None
        bits = struct.unpack("<I", body[1:5])[0]
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if kind == b"VP8X":
        # 24-bit dimensions, stored minus one.
        if len(body) < 10:
            return None
        return (int.from_bytes(body[4:7], "little") + 1,
                int.from_bytes(body[7:10], "little") + 1)
    return None


def _png_size(head: bytes) -> tuple[int, int] | None:
    if len(head) < 24 or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return (width, height) if width and height else None


def _jpeg_size(path: Path) -> tuple[int, int] | None:
    """Walk the marker chain to the first SOFn (the frame that carries the size).

    The marker check has to be *exact*: `b"\\xd0" <= marker <= b"\\xd7"` is a
    byte comparison against a bytes object, and `\\xff` sorts above `\\xd7`, so
    that range silently swallowed every marker byte and the scan ran off the end.
    """
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                   0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    try:
        with Path(path).open("rb") as fh:
            fh.read(2)
            while True:
                byte = fh.read(1)
                if not byte:
                    return None
                if byte != b"\xff":
                    continue                      # padding between markers
                marker = fh.read(1)
                while marker == b"\xff":          # fill bytes
                    marker = fh.read(1)
                if not marker:
                    return None
                code = marker[0]
                if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                    continue                      # SOI/EOI/RSTn carry no length
                length = fh.read(2)
                if len(length) < 2:
                    return None
                size = struct.unpack(">H", length)[0]
                if size < 2:
                    return None
                if code in sof_markers:
                    rest = fh.read(size - 2)
                    if len(rest) < 5:
                        return None
                    height, width = struct.unpack(">HH", rest[1:5])
                    return (width, height) if width and height else None
                fh.seek(size - 2, 1)
    except OSError:
        return None


def caption(llm, path: Path) -> str:
    """One short line describing *path*. `""` on any failure — never fatal.

    `llm` is the host's own `ctx.llm` (bound by `register(ctx)`); no provider or
    model override, which would need a capability this plugin does not declare.

    The image block is a plain dict of the shape `PluginLlmImageInput` declares
    (`agent/plugin_llm.py`: `data`, `url`, `mime_type`, `file_name`, `type`).
    Importing the dataclass is preferred — it keeps the two in step — but a test
    or a standalone CLI run has no `agent` package on its path, and refusing to
    caption there would make the function untestable for the one thing it does.
    The dict is accepted by the same `_structured_spec` that accepts the class.
    """
    if llm is None:
        return ""
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        return ""
    if not data:
        return ""
    block = None
    try:
        from agent.plugin_llm import PluginLlmImageInput

        block = PluginLlmImageInput(data=data, mime_type=mime_of(p), file_name=p.name)
    except Exception:
        block = {"type": "image", "data": data, "mime_type": mime_of(p), "file_name": p.name}
    try:
        res = llm.complete_structured(
            instructions=_CAPTION_INSTRUCTIONS,
            input=[block],
            temperature=0,
            purpose="tvl-vault image caption",
        )
        return (getattr(res, "text", "") or "").strip()
    except Exception:
        return ""          # the free model throttles; the wall shows no caption


def _image_documents(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT doc_id, path, title, is_junk, size FROM documents "
        "WHERE kind='image' ORDER BY is_junk, title").fetchall()


def wall(db: sqlite3.Connection, llm=None, caption_junk: bool = False) -> dict:
    """Everything the Wall tab draws.

    Junk is **counted, not listed and not captioned**: it is a build artifact,
    and paying the model to describe 130 screenshots is the cost the plan rules
    out. The listed images are the ones worth looking at — portraits, the org
    chart, the renders — each with its dimensions and, when a model is bound and
    it succeeds, one line of description.

    `db` may be `None` (the desktop's first render, before the index exists);
    the wall then says so through empty lists and a zero count.
    """
    out: dict = {"images": [], "junk_count": 0, "documents": 0, "sections": 0,
                 "junk_omitted": 0, "captions": 0, "errors": 0}
    if db is None:
        return out
    try:
        out["documents"] = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        out["sections"] = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    except sqlite3.Error:
        return out

    junk = [r for r in _image_documents(db) if r["is_junk"]]
    out["junk_count"] = len(junk)
    out["junk_omitted"] = len(junk)

    for r in _image_documents(db):
        if r["is_junk"] and not caption_junk:
            continue
        path = Path(r["path"])
        w, h = dimensions(path) or (None, None)
        cap = ""
        if not r["is_junk"] and llm is not None and r["size"] and r["size"] <= MAX_CAPTION_BYTES:
            try:
                cap = caption(llm, path)
            except Exception:
                cap = ""
                out["errors"] += 1
        if cap:
            out["captions"] += 1
        out["images"].append({
            "doc_id": r["doc_id"], "path": r["path"], "title": r["title"],
            "width": w, "height": h, "caption": cap, "is_junk": bool(r["is_junk"]),
        })
    return out
