import zipfile
from pathlib import Path

from vault import extract

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _minimal_docx_bytes() -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/document.xml",
                   '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   '<w:body><w:p><w:r><w:t>docx body</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def test_pdf_text_is_extracted_from_a_real_file():
    pdf = FIXTURES / "one-page.pdf"
    assert pdf.exists(), "fixture missing: tests/fixtures/one-page.pdf"
    assert "HELLOVAULT" in extract.pdf_text(pdf).replace(" ", "").upper()


def test_docx_text_is_extracted_without_python_docx(tmp_path):
    p = tmp_path / "t.docx"
    p.write_bytes(_minimal_docx_bytes())
    assert "docx body" in extract.docx_text(p)


def test_markdown_sections_split_on_headings():
    md = "# Title\n\nintro\n\n# **SECTION 1 — ALPHA**\n\nbody a\n\n## **1.1 Sub**\n\nbody b\n"
    secs = extract.split_markdown(md)
    assert [s.title for s in secs][:3] == ["Title", "SECTION 1 — ALPHA", "1.1 Sub"]
    assert "body a" in secs[1].body


def test_pdf_section_style_is_recognised():
    txt = ("TVL — YouTube — Platform Governance (v1.1)\n\n"
           "SECTION 0 — RAG Document Purpose\n\nhello\n\n"
           "SECTION 1 — Document Authority\n\nworld\n")
    secs = extract.split_pdf_text(txt)
    assert [s.title for s in secs] == ["RAG Document Purpose", "Document Authority"]


def test_numeric_heading_style_is_recognised():
    txt = "1. RAG System Definition\n\nalpha\n\n2. The Canonical Section Map\n\nbeta\n"
    secs = extract.split_pdf_text(txt)
    assert [s.title for s in secs] == ["RAG System Definition", "The Canonical Section Map"]


def test_header_block_metadata_is_parsed():
    txt = ("[SYSTEM AUTHORITY HEADER — DO NOT BYPASS] ENTITY: TrillionVerse Labs (TVL) "
           "STATUS: Canonical Doctrine / Root Authority\nDocument Title:\nTVL — X\n"
           "Version:\nv1.2 — January 2026 Document\n")
    meta = extract.parse_header(txt)
    assert meta["title"] == "TVL — X"
    assert meta["version"] == "v1.2 — January 2026 Document"
    assert "Canonical Doctrine" in meta["status"]


def test_rag_tag_block_is_parsed():
    txt = ("RAG TAG BLOCK\nENTITY: n8n, Equalizer Technology\nINTENT: Orchestration Doctrine\n"
           "DEPENDENCY: TVL — Structure (v1.0)\nVALIDITY: Active (v1.0)\n"
           "AU2I_INDEX: Workflow Composition\n")
    tag = extract.parse_rag_tag(txt)
    assert tag["entity"] == ["n8n", "Equalizer Technology"]
    assert tag["validity"] == "Active (v1.0)"
    assert tag["dependency"] == ["TVL — Structure (v1.0)"]


def test_html_title_and_text_are_extracted(tmp_path):
    p = tmp_path / "page.html"
    p.write_text("<html><head><title>Arete-27B</title></head>"
                 "<body><script>ignore()</script><p>body text</p></body></html>")
    ex = extract.extract_document(p, "html")
    assert ex.title == "Arete-27B"
    assert "body text" in ex.text
    assert "ignore()" not in ex.text
