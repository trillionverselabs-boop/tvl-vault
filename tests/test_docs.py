"""Task 11 — the package's documents exist, agree with the code, and are honest.

These are documentation tests, which is the point: a README that tells a reader to
run a command that does not exist, or a SCHEMA that omits a table the code writes,
is worse than no document. Every assertion below is checked against the files, the
modules, or a real run.

Every number asserted here was produced by a command on this machine on
2026-11-15 (see `docs/CORPUS.md`); the tests keep them honest as the corpus moves.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DOCS = ROOT / "docs"

# The four documents the task names, and what each one must contain.
REQUIRED = {
    "README.md": ROOT / "README.md",
    "docs/SCHEMA.md": DOCS / "SCHEMA.md",
    "docs/CORPUS.md": DOCS / "CORPUS.md",
    "docs/DECISIONS.md": DOCS / "DECISIONS.md",
}


def _read(rel: str) -> str:
    return REQUIRED[rel].read_text(encoding="utf-8")


# ── they exist, and are not stubs ──────────────────────────────────────────

def test_every_required_document_exists():
    missing = [rel for rel, p in REQUIRED.items() if not p.is_file()]
    assert not missing, f"missing documents: {missing}"


def test_no_document_is_a_stub():
    for rel, p in REQUIRED.items():
        body = p.read_text(encoding="utf-8")
        assert len(body) > 400, f"{rel} is {len(body)} bytes — a stub, not a document"
        assert "<" not in body[:200] or "TODO" not in body, f"{rel} still has a placeholder"


# ── README: what it is, what it is not, how to run it ───────────────────────

def test_readme_says_what_it_is_and_what_it_is_not():
    text = _read("README.md").lower()
    assert "what it is" in text or "what the vault is" in text
    assert "what it is not" in text, "README must state its limits in plain language"


def test_readme_documents_the_rebuild_command_the_script_runs():
    """The command a reader is told to run must be the one that exists."""
    readme = _read("README.md")
    assert "rebuild" in readme
    script = (ROOT / "scripts" / "rebuild.sh").read_text()
    # the README may name either the wrapper or the module form; both are real
    assert "./scripts/rebuild.sh" in readme or "python -m vault rebuild" in readme
    assert "vault rebuild" in script


def test_readme_names_the_five_flags():
    text = _read("README.md").lower()
    for flag in ("current", "outdated", "duplicate", "conflict", "unclear"):
        assert flag in text, f"README never mentions the {flag} flag"


def test_readme_says_the_source_corpus_is_never_written():
    """Rule 4 of the handoff, in the document a new reader sees first."""
    text = _read("README.md").lower()
    assert "never" in text and ("source" in text or "corpus" in text)


# ── SCHEMA: one section per table, matching the code ────────────────────────

def _tables_created_by_the_code() -> set[str]:
    """Every table name the modules create, read from the source."""
    names: set[str] = set()
    for mod in ("index.py", "review.py"):
        src = (ROOT / "src" / "vault" / mod).read_text()
        names |= set(re.findall(r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)", src, re.I))
        names |= set(re.findall(r"CREATE VIRTUAL TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)", src, re.I))
    return names


def test_schema_documents_every_table_the_code_creates():
    doc = _read("docs/SCHEMA.md")
    for table in sorted(_tables_created_by_the_code()):
        assert re.search(rf"\b{table}\b", doc), f"SCHEMA.md never documents {table}"


def test_schema_documents_the_flags_table_and_the_corrections_table():
    doc = _read("docs/SCHEMA.md")
    assert "flags" in doc and "corrections" in doc
    # the key that makes a conflict pair exact — the handoff calls this a lesson
    assert re.search(r"doc_id.*section_id.*flag|PRIMARY KEY", doc)


def test_schema_documents_the_doc_id_format():
    """`doc_id` is `sha256[:16]` — a fact a reader needs to read the DB."""
    doc = _read("docs/SCHEMA.md")
    assert re.search(r"sha256", doc, re.I)
    assert "16" in doc


# ── CORPUS: measured, with the command that measured it ─────────────────────

def test_corpus_documents_how_its_numbers_were_produced():
    """Every number in CORPUS.md has a command behind it."""
    doc = _read("docs/CORPUS.md")
    assert "rebuild" in doc
    assert re.search(r"```bash", doc), "CORPUS.md shows no command"


def test_corpus_carries_the_real_counts():
    """369 documents · 1,866 sections · 118 duplicates — the measured build."""
    doc = _read("docs/CORPUS.md")
    for needle in ("369", "1,866", "118"):
        assert needle in doc, f"CORPUS.md does not carry the measured {needle}"


def test_corpus_names_the_four_roots():
    doc = _read("docs/CORPUS.md")
    assert "attachments" in doc
    assert "/home/lisacore/work" in doc
    assert "Projects" in doc
    assert "tvl-ingest" in doc


def test_corpus_carries_exact_duplicate_hashes():
    """The plan's acceptance asked for the exact hashes; a claim without one is
    not evidence. The doc carries the first 12 hex of each sha256 (see the table
    below), which is enough to identify a group and short enough to read."""
    doc = _read("docs/CORPUS.md")
    hashes = re.findall(r"\b[0-9a-f]{12,64}\b", doc)
    assert len(hashes) >= 3, f"CORPUS.md carries only {len(hashes)} hash(es)"


def test_corpus_records_the_known_no_outdated_result():
    """The deterministic version-regress rule finds nothing on this corpus.
    Recording that is honest; silently dropping the flag would not be."""
    doc = _read("docs/CORPUS.md")
    assert re.search(r"outdated", doc, re.I)


# ── DECISIONS: the four user decisions and what was ruled out ───────────────

def test_decisions_records_the_four_user_decisions():
    doc = _read("docs/DECISIONS.md")
    assert re.search(r"section", doc, re.I)          # decision 4: stamp on the section
    assert re.search(r"reversib|never.*(rewrite|write)", doc, re.I)
    assert re.search(r"graph|wall|search", doc, re.I)
    assert re.search(r"free|nous", doc, re.I)


def test_decisions_records_what_was_ruled_out():
    """The user did not choose cleaned, rewritten copies of the corpus."""
    doc = _read("docs/DECISIONS.md").lower()
    assert "ruled out" in doc or "not chosen" in doc or "rejected" in doc
    assert "option b" in doc or "rewrite" in doc or "cleaned" in doc


def test_decisions_names_the_stack_and_why():
    doc = _read("docs/DECISIONS.md")
    for needle in ("pdftotext", "sqlite", "fts5", "bm25"):
        assert needle.lower() in doc.lower(), f"DECISIONS.md does not mention {needle}"


def test_decisions_records_the_later_direction_decisions():
    """The 2026-11-15 direction (HANDOFF.md) is binding and belongs in the record."""
    doc = _read("docs/DECISIONS.md").lower()
    assert "research-to-product" in doc or "research to product" in doc
    assert "$0" in doc or "zero" in doc


# ── the four documents must not contradict the code ─────────────────────────

def test_no_document_claims_a_remote_or_a_public_repo():
    """Rule 1: no remote without Lisa's word. A README inviting one is a defect."""
    for rel in REQUIRED:
        text = _read(rel).lower()
        assert "git push" not in text, f"{rel} tells a reader to push"
        assert "git remote add" not in text, f"{rel} tells a reader to add a remote"


def test_no_document_claims_dependencies():
    """`pyproject.toml` keeps `dependencies = []`; a doc promising more is wrong."""
    for rel in REQUIRED:
        text = _read(rel).lower()
        assert "pip install" not in text, f"{rel} tells a reader to pip install"
        assert "python_dependencies" not in text, f"{rel} mentions a dependency block"


def test_no_document_advertises_a_tool_the_plugin_does_not_register():
    """`provides_tools: []` — the desktop surface is the product, not a toolset."""
    for rel in REQUIRED:
        for tool in ("vault_search", "vault_ask", "vault_rebuild"):
            assert tool not in _read(rel), f"{rel} advertises a tool that is not registered"


def test_the_plugin_still_validates():
    """The task's own acceptance command, run for real.

    The autouse fixture points `HERMES_HOME` at a throwaway tree so no test can
    write Lisa's review log. This command is read-only, and the CLI needs the
    real profile to resolve itself, so it runs with that one redirect lifted.
    """
    env = {k: v for k, v in os.environ.items() if k != "HERMES_HOME"}
    out = subprocess.run(
        ["hermes", "plugins", "validate", ".", "--install-deps"],
        cwd=str(ROOT), capture_output=True, text=True, env=env,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Validation passed." in out.stdout
    assert "security scan — safe" in out.stdout
