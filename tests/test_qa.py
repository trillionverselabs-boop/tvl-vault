"""Cited question-answering (`src/vault/qa.py`).

The model sees ONLY the retrieved sections. Every rule that makes the answer
auditable is asserted here: the no-invention rule is in the prompt, a citation
that does not exist is dropped rather than passed through, and a question the
corpus cannot answer gets the fixed refusal — never a guess.
"""

from __future__ import annotations

from vault import qa


class FakeLlm:
    """Stands in for `ctx.llm`. Records what it was sent."""

    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, messages, **kw):
        self.calls.append({"messages": messages, "kw": kw})

        class R:
            pass

        r = R()
        r.text = self.text
        return r


def test_prompt_contains_the_citations_and_the_no_invention_rule():
    chunks = [{"title": "A", "section_title": "S", "body": "sabotage lowers output",
               "doc_title": "D", "path": "/x"}]
    prompt = qa.build_prompt("what does the doctrine say?", chunks)
    assert "sabotage lowers output" in prompt
    assert "do not invent" in prompt.lower()
    assert "[1]" in prompt, "the passages must be numbered so a citation resolves"


def test_retrieve_tries_each_significant_word_before_filling_up(tmp_path):
    """An OR of the question's words matches everything and ranks the generic
    sections first ('doctrine', 'document' appear everywhere). The section that
    answers is the one matching the *distinctive* word, so each word is tried
    on its own before the OR result is used to fill the remaining slots."""
    from vault import index

    (tmp_path / "doctrine.md").write_text(
        "# Doctrine\n\nChunking must happen at the section header level.\n")
    (tmp_path / "noise.md").write_text(
        "# Noise\n\nThe doctrine says a document is a unit of governance.\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    got = qa.retrieve(db, "what did the doctrine say about how to chunk a document?", 6)
    assert got, "retrieval found nothing"
    assert any("chunk" in (c["body"] or "").lower() for c in got), \
        [(c["doc_title"], c["section_title"]) for c in got]
    assert got[0]["doc_title"] == "Doctrine"


def test_the_result_does_not_depend_on_the_callers_k(tmp_path):
    """A ladder rung capped at k drops the answering section when k is small.

    The rungs must reach a fixed depth and only the final selection is capped,
    or `retrieve(db, q, 2)` and `retrieve(db, q, 6)` return different corpora.
    """
    from vault import index

    (tmp_path / "doctrine.md").write_text(
        "# Doctrine\n\nChunking must happen at the section header level.\n")
    for i in range(8):
        (tmp_path / f"n{i}.md").write_text(
            f"# Note {i}\n\nthe doctrine says a document is a unit of governance.\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    q = "what did the doctrine say about how to chunk a document?"
    got = qa.retrieve(db, q, 2)
    assert any("chunk" in (c["body"] or "").lower() for c in got), \
        [(c["doc_title"], c["section_title"]) for c in got]


def test_a_question_the_corpus_cannot_answer_gets_the_fixed_refusal():
    assert qa.build_refusal() == "Not answered by the corpus."
    llm = FakeLlm("anything")
    assert qa.answer(None, "what is the capital of France?", llm, k=6) == {
        "answer": "Not answered by the corpus.", "citations": [], "sources": []}
    assert llm.calls == [], "an empty retrieval must not call the model at all"


def test_an_empty_question_is_refused_before_any_search():
    llm = FakeLlm("anything")
    assert qa.answer(None, "   ", llm)["answer"] == "Not answered by the corpus."
    assert llm.calls == []


def test_citations_are_parsed_from_a_model_answer():
    text = "See [1] and [2]."
    cites = qa.parse_citations(text, [
        {"section_title": "A", "doc_title": "DA", "doc_path": "/a"},
        {"section_title": "B", "doc_title": "DB", "doc_path": "/b"},
    ])
    assert [c["title"] for c in cites] == ["A", "B"]
    assert [c["n"] for c in cites] == [1, 2]
    assert cites[0]["doc"] == "DA" and cites[0]["path"] == "/a"


def test_an_out_of_range_citation_is_dropped_not_invented():
    """A model that cites [9] must not produce a ninth source."""
    cites = qa.parse_citations("only [9]", [{"section_title": "A", "doc_title": "D", "doc_path": "/a"}])
    assert cites == []


def test_the_answer_carries_its_citations_and_the_sources_it_used(tmp_path):
    from vault import index

    (tmp_path / "a.md").write_text("# Alpha\n\nthe sabotage contest logic\n")
    (tmp_path / "b.md").write_text("# Beta\n\nunrelated gardening text\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    llm = FakeLlm("The doctrine says sabotage lowers output. [1]")
    out = qa.answer(db, "what does the doctrine say about sabotage?", llm, k=6)
    assert "sabotage lowers output" in out["answer"]
    assert [c["title"] for c in out["citations"]] == ["Alpha"]
    assert out["sources"][0]["doc_path"].endswith("a.md")
    assert len(llm.calls) == 1


def test_the_model_is_called_on_the_session_model_with_no_override(tmp_path):
    """Rule: the session model, no provider/model override. An override needs a
    consent-gated capability this plugin does not declare."""
    from vault import index

    (tmp_path / "a.md").write_text("# Alpha\n\nbody\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    llm = FakeLlm("answer [1]")
    qa.answer(db, "alpha", llm)
    kw = llm.calls[0]["kw"]
    assert kw.get("model") in (None, "")
    assert kw.get("provider") in (None, "")


def test_temperature_is_zero_so_the_answer_is_reproducible(tmp_path):
    from vault import index

    (tmp_path / "a.md").write_text("# Alpha\n\nbody\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    llm = FakeLlm("answer [1]")
    qa.answer(db, "alpha", llm)
    assert llm.calls[0]["kw"].get("temperature") == 0


def test_a_model_failure_is_reported_not_swallowed(tmp_path):
    """A free model times out. The user must see that, not a silent empty answer."""

    class Boom:
        def complete(self, messages, **kw):
            raise RuntimeError("the model call timed out")

    from vault import index

    (tmp_path / "a.md").write_text("# Alpha\n\nbody\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    out = qa.answer(db, "alpha", Boom())
    assert "error" in out
    assert "timed out" in out["error"]
    assert out["answer"] == ""


def test_the_prompt_never_puts_the_whole_corpus_in_front_of_the_model(tmp_path):
    """The corpus is ~2.7 MB. Each passage is capped, and so is the count."""
    from vault import index

    (tmp_path / "a.md").write_text("# Alpha\n\n" + ("word " * 5000) + "\n")
    db = index.rebuild(tmp_path, tmp_path / "vault.db")
    llm = FakeLlm("answer [1]")
    qa.answer(db, "alpha", llm, k=6)
    prompt = llm.calls[0]["messages"][0]["content"]
    assert len(prompt) < 12000, f"prompt is {len(prompt)} chars — passages are not capped"
