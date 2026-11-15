"""Images: dimensions, captions, and the wall.

No OCR is installed on this host, so an image becomes text in exactly one way:
the vision model describes it (`images.caption`). Dimensions come from the
file's own header, with no third-party library.

The rule these tests pin is the one Lisa set: the ~130 plugin-test screenshots
are *indexed as artifacts and kept out of the human review queue*, while the
portraits and renders are the "pretty visual items" the wall exists for.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from vault import images, index, review, sources


def _png(width: int, height: int, tag: bytes = b"\x11") -> bytes:
    """A real, decodable PNG — written by hand, so the test needs no Pillow.

    The header is the only thing `dimensions()` reads, but the IDAT chunk and
    the CRCs are real, so the fixture is a file a decoder would accept rather
    than a bag of bytes. *tag* makes each file's bytes unique, so two fixtures
    are not collapsed as duplicates by the sha256 pass.
    """
    raw = b"".join(b"\x00" + tag * width for _ in range(height))

    def chunk(tag_bytes: bytes, data: bytes) -> bytes:
        body = tag_bytes + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _jpeg(width: int, height: int, tag: int = 1) -> bytes:
    """A real JPEG header carrying *width* × *height* in its SOF0 marker."""
    sof = (b"\xff\xc0" + struct.pack(">H", 16) + b"\x08"
           + struct.pack(">HH", height, width) + b"\x03" + b"\x01\x11\x00" * 3)
    return (b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + bytes([tag]) + sof + b"\xff\xd9")


@pytest.fixture(autouse=True)
def _keep_the_real_data_root(tmp_path, monkeypatch):
    """Never read the real corpus or write the profile's data root."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_VAULT_DB", raising=False)
    monkeypatch.setenv("HERMES_VAULT_ROOTS", str(tmp_path / "corpus"))


# ── dimensions: the file header, not a library ──────────────────────────────

def test_dimensions_reads_the_png_header(tmp_path):
    p = tmp_path / "calvin.png"
    p.write_bytes(_png(320, 200))
    assert images.dimensions(p) == (320, 200)


def test_dimensions_reads_jpeg_soi_markers(tmp_path):
    """A JPEG has no fixed header; the size sits in a SOFn marker."""
    # SOF0: length 16, precision 8, height 64, width 48, 3 components.
    sof = (b"\xff\xc0" + struct.pack(">H", 16) + b"\x08"
           + struct.pack(">HH", 64, 48) + b"\x03" + b"\x01\x11\x00" * 3)
    p = tmp_path / "portrait.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                  + sof + b"\xff\xd9")
    assert images.dimensions(p) == (48, 64)


def test_dimensions_is_never_fatal(tmp_path):
    p = tmp_path / "broken.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nnot really a png")
    assert images.dimensions(p) is None


def test_dimensions_of_a_missing_file_is_none(tmp_path):
    assert images.dimensions(tmp_path / "absent.png") is None


def _webp_lossy(width: int, height: int) -> bytes:
    """A RIFF/WEBP container with a `VP8 ` chunk — the lossy form.

    Padded to a realistic size: `dimensions()` reads the header with one 64 KB
    read, and a 27-byte file is a truncated fixture rather than a picture.
    """
    frame = b"\x9d\x01\x2a" + struct.pack("<HH", width, height) + b"\x00" * 64
    chunk = b"VP8 " + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk + b"\x00" * 4096


def _webp_shifted(width: int, height: int) -> bytes:
    """The layout actually on disk for four files in ~/Projects: the VP8 payload
    begins with three bytes that are not the start code."""
    frame = b"\xf0\x05\x04" + b"\x9d\x01\x2a" + struct.pack("<HH", width, height) + b"\x00" * 64
    chunk = b"VP8 " + struct.pack("<I", len(frame)) + frame
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk + b"\x00" * 4096


@pytest.mark.parametrize("builder", [_webp_lossy, _webp_shifted])
def test_a_webp_named_jpg_is_still_measured(tmp_path, builder):
    """Four real files in ~/Projects are WebP bytes with a `.jpg` extension.
    The extension is not evidence; the header is."""
    p = tmp_path / "thumb.jpg"
    p.write_bytes(builder(1280, 720))
    assert images.dimensions(p) == (1280, 720)
    assert images.mime_of(p) == "image/webp", "the model would be sent image/jpeg"


def test_mime_is_decided_by_content_not_extension(tmp_path):
    p = tmp_path / "really_png.jpg"
    p.write_bytes(_png(8, 8))
    assert images.mime_of(p) == "image/png"
    assert images.mime_of(tmp_path / "absent.png") == "image/png"


# ── captions: only the non-junk images, never during a rebuild ─────────────

class _FakeLlm:
    """Stands in for `ctx.llm`; records every image it was handed."""

    def __init__(self, text="a hand-drawn portrait of a woman"):
        self.text = text
        self.images = []

    def complete_structured(self, *, instructions, input, **kw):
        self.images.extend(getattr(b, "data", b"") for b in input)
        return type("R", (), {"text": self.text})()


def test_a_caption_is_one_short_line(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(_png(8, 8))
    assert images.caption(_FakeLlm(), p) == "a hand-drawn portrait of a woman"


def test_a_failed_caption_is_empty_never_raised(tmp_path):
    class Boom:
        def complete_structured(self, **kw):
            raise RuntimeError("the free model timed out")

    p = tmp_path / "a.png"
    p.write_bytes(_png(4, 4))
    assert images.caption(Boom(), p) == ""


def test_captioning_is_never_part_of_a_rebuild(tmp_path, monkeypatch):
    """Rebuild is $0 and offline. A model call inside it would make the index
    command spend money and break when the free model is throttled."""
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "calvin.png").write_bytes(_png(16, 16))

    class Boom:
        def complete_structured(self, **kw):
            raise AssertionError("rebuild called the model")

    monkeypatch.setattr(images, "caption", Boom().complete_structured)
    index.rebuild([root], tmp_path / "vault.db")
    assert (tmp_path / "vault.db").exists()


# ── the wall: portraits and renders, junk counted and hidden ────────────────

def _seed(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "calvin.png").write_bytes(_png(640, 480, tag=b"\x11"))
    (root / "orgchart.jpg").write_bytes(_jpeg(1200, 900, tag=7))
    (root / "plugintest5a.png").write_bytes(_png(800, 600, tag=b"\x22"))   # junk
    (root / "popupd3.jpg").write_bytes(_jpeg(1024, 768, tag=9))          # junk


def _wall(db, llm=None):
    return images.wall(db, llm)


def test_the_wall_lists_only_non_junk_images(tmp_path):
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    w = _wall(db)
    assert {Path(i["path"]).name for i in w["images"]} == {"calvin.png", "orgchart.jpg"}


def test_junk_is_counted_not_listed(tmp_path):
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    w = _wall(db)
    assert w["junk_count"] == 2
    assert all("plugintest" not in i["path"] for i in w["images"])


def test_every_wall_image_carries_its_dimensions(tmp_path):
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    w = _wall(db)
    for i in w["images"]:
        assert i["width"] and i["height"], i


def test_the_wall_captions_only_what_it_shows(tmp_path):
    """The plan's risk #4: vision captions cost money. The 130 test screenshots
    must never be sent to the model — only the portraits and renders."""
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    llm = _FakeLlm()
    w = _wall(db, llm)
    assert len(llm.images) == 2, "the model was handed the junk too"
    assert all(i["caption"] for i in w["images"])


def test_a_wall_image_with_no_caption_still_shows(tmp_path):
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")

    class Silent:
        def complete_structured(self, **kw):
            return type("R", (), {"text": ""})()

    w = _wall(db, Silent())
    assert [Path(i["path"]).name for i in w["images"]] == ["calvin.png", "orgchart.jpg"]
    assert all(i["caption"] == "" for i in w["images"])


def test_the_wall_counts_documents_and_sections_too(tmp_path):
    _seed(tmp_path / "corpus")
    (tmp_path / "corpus" / "doctrine.md").write_text("# Doctrine\n\nbody\n")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    w = _wall(db)
    assert w["documents"] == 5          # 4 images + 1 note
    assert w["sections"] == 1


# ── images are indexed as artifacts, not as unclear doctrine ───────────────

def test_images_never_enter_the_review_queue(tmp_path):
    """An image has no text sections, so the deterministic pass would call it
    unclear — 43 of the real corpus's unclear flags were images. A picture is
    not a claim, so it is not a review decision."""
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    image_ids = {r[0] for r in db.execute("SELECT doc_id FROM documents WHERE kind='image'")}
    assert image_ids
    assert all(f["doc_id"] not in image_ids for f in review.compute_flags(db)), \
        "an image was flagged for human review"


def test_a_flagged_image_does_not_count_as_needing_a_decision(tmp_path):
    """The Review tab's count must be the queue, not every document."""
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))
    # the only flag left is the byte-identical pair; no image is on the queue
    assert {f["doc_id"] for f in review.queue(db)} == {
        r[0] for r in db.execute(
            "SELECT d.doc_id FROM documents d JOIN duplicates u ON u.sha256=d.sha256")}


def test_an_image_is_never_captioned_by_the_flag_pass(tmp_path, monkeypatch):
    """Captions are a wall concern. `compute_flags` runs on every rebuild, so a
    model call there would be a silent, repeated cost."""
    _seed(tmp_path / "corpus")
    db = index.rebuild([tmp_path / "corpus"], tmp_path / "vault.db")

    class Boom:
        def complete_structured(self, **kw):
            raise AssertionError("the flag pass called the model")

    monkeypatch.setattr(images, "caption", Boom().complete_structured)
    review.compute_flags(db)


def test_a_byte_identical_image_is_not_put_on_the_review_queue(tmp_path):
    """The fixture above has no duplicate image, so it passed while the real
    corpus put 60 images on the queue as `duplicate`.

    A duplicate *flag* is a fact worth recording — `/stats` counts it — but a
    duplicate *decision* is for a human looking at text. A picture has nothing
    to keep, confirm or edit, so it stays off the queue.
    """
    root = tmp_path / "corpus"
    root.mkdir()
    data = _png(32, 32, tag=b"\x33")
    (root / "calvin.png").write_bytes(data)
    (root / "calvin-copy.png").write_bytes(data)      # byte-identical
    (root / "doctrine.md").write_text("# Alpha\n\nbody\n")
    db = index.rebuild([root], tmp_path / "vault.db")
    review.write_flags(db, review.compute_flags(db))

    assert db.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0] == 1, \
        "the fixture must actually contain a duplicate"
    q = review.queue(db)
    image_ids = {r[0] for r in db.execute("SELECT doc_id FROM documents WHERE kind='image'")}
    assert image_ids, "the fixture must contain an image"
    assert not ({f["doc_id"] for f in q} & image_ids), \
        f"an image is on the review queue: {[f for f in q if f['doc_id'] in image_ids]}"
