"""Dependency-free tests for the reusable hackathon core."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackathon_rag.chunking import build_chunks  # noqa: E402
from hackathon_rag.cleaning import clean_text, remove_repeated_page_lines  # noqa: E402
from hackathon_rag.config import HackathonConfig  # noqa: E402
from hackathon_rag.loaders import load_documents  # noqa: E402
from hackathon_rag.answering import GroundedAnswerer  # noqa: E402
from hackathon_rag.models import Chunk, ParentSection, RetrievedChunk, SourceUnit  # noqa: E402
from hackathon_rag.retrieval import HybridRetriever, LightweightBM25, tokenize  # noqa: E402
from hackathon_rag.pipeline import HackathonRAG  # noqa: E402


def test_cleaning_removes_web_noise_and_preserves_lines():
    value = clean_text("عنوان\nيجب عليك تفعيل JavaScript لرؤيته.\nسطر مهم\n\nفقرة ثانية")
    assert "JavaScript" not in value
    assert "عنوان\nسطر مهم\n\nفقرة ثانية" == value


def test_repeated_pdf_headers_are_removed():
    units = [
        SourceUnit(f"اسم المؤسسة\nمحتوى الصفحة {page}\nصفحة {page}", "guide.pdf", page=page, document_type="pdf")
        for page in range(1, 5)
    ]
    cleaned = remove_repeated_page_lines(units)
    assert all("اسم المؤسسة" not in unit.text for unit in cleaned)
    assert all("محتوى الصفحة" in unit.text for unit in cleaned)


def test_context_is_present_in_every_chunk_and_tiny_tail_is_merged():
    paragraph = "هذه جملة واضحة تحتوي معلومات مهمة عن سياسة التسجيل. " * 50
    parents, chunks = build_chunks(
        [SourceUnit(paragraph, "rules.pdf", page=4, section="التسجيل", document_type="pdf")],
        parent_size=1600,
        child_size=500,
        overlap=80,
        minimum=180,
    )
    assert parents and len(chunks) > 1
    assert all(chunk.text.startswith("[Source: rules.pdf | Page: 4 | Section: التسجيل") for chunk in chunks)
    assert all(len(chunk.body) >= 180 for chunk in chunks)
    assert len({chunk.id for chunk in chunks}) == len(chunks)


def test_course_boundaries_become_sections():
    text = "CS 101: Introduction\nFirst course description.\nCS 202: Algorithms\nSecond course description."
    _, chunks = build_chunks([SourceUnit(text, "catalog.txt")], child_size=500)
    assert len(chunks) == 2
    assert chunks[0].section.startswith("CS 101")
    assert chunks[1].section.startswith("CS 202")


def test_document_title_is_inherited_instead_of_becoming_an_empty_chunk():
    text = "# Employee Handbook\n\n## Leave Policy\nEmployees receive annual leave.\n\n## Attendance\nAttendance is required."
    _, chunks = build_chunks([SourceUnit(text, "handbook.md")], child_size=500)
    assert len(chunks) == 2
    assert all("Employee Handbook >" in chunk.section for chunk in chunks)
    assert all(chunk.body.strip() != "# Employee Handbook" for chunk in chunks)


def test_bm25_supports_arabic_and_exact_numbers():
    documents = ["شروط التسجيل للعام الجامعي", "المادة CS 253 تتطلب CS 101", "خدمات المكتبة"]
    scores = LightweightBM25(documents).scores("ما متطلب CS 253؟")
    assert scores.index(max(scores)) == 1
    assert "التسجيل" in tokenize("شُروط التسجيل")


class _FakeOllama:
    def embed(self, model, texts, batch_size=32):
        return [[1.0, 0.0] for _ in texts]

    def chat_json(self, model, messages, schema):
        return {
            "answer": "المعلومة موجودة في اللائحة.",
            "supported": True,
            "citations": [
                {"evidence_id": "E1", "reason": "النص يذكر الشرط."},
                {"evidence_id": "E99", "reason": "مرجع غير موجود."},
            ],
        }


class _FakeStore:
    def __init__(self, chunks):
        self._chunks = chunks

    def load_chunks(self):
        return self._chunks

    def vector_ids(self, query_vector, n_results):
        return [chunk.id for chunk in self._chunks[:n_results]]


def test_hybrid_retrieval_uses_keywords_and_source_diversity():
    chunks = [
        Chunk("a", "pa", "[Source: a] شروط التسجيل", "شروط التسجيل", "a.pdf"),
        Chunk("b", "pb", "[Source: a] تفاصيل أخرى", "تفاصيل أخرى", "a.pdf"),
        Chunk("c", "pc", "[Source: b] المادة CS 253", "المادة CS 253", "b.pdf"),
    ]
    retriever = HybridRetriever(_FakeStore(chunks), _FakeOllama(), "fake", candidates=3, final_k=3, max_per_source=1)
    results = retriever.retrieve("ما هي المادة CS 253؟")
    assert results[0].chunk.id == "c"
    assert len({result.chunk.source for result in results[:2]}) == 2
    assert len(results) == 3


def test_answerer_drops_hallucinated_citation_ids():
    chunk = Chunk("a", "pa", "context", "context", "rules.pdf", page=2)
    retrieved = [RetrievedChunk(chunk, score=0.1)]
    parents = {"pa": ParentSection("pa", "النص يذكر الشرط.", "rules.pdf", page=2)}
    result = GroundedAnswerer(_FakeOllama(), "fake").answer("ما الشرط؟", retrieved, parents)
    assert result.supported
    assert len(result.citations) == 1
    assert result.citations[0]["evidence_id"] == "E1"


def test_answerer_abstains_in_question_language_without_evidence():
    result = GroundedAnswerer(_FakeOllama(), "fake").answer("ما هي الشروط؟", [], {})
    assert not result.supported
    assert "لم أجد" in result.answer


def test_preview_runs_without_ollama_or_vector_database():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        documents = root / "documents"
        documents.mkdir()
        (documents / "guide.txt").write_text(
            "# Registration\n\n" + "Registration requires an identity document. " * 40,
            encoding="utf-8",
        )
        output = root / "preview.json"
        config = HackathonConfig(documents_dir=documents, index_dir=root / "index", child_size=500)
        report = HackathonRAG(config).preview(output, sample_count=10)
        assert report["chunks"] >= 2
        assert report["chunk_lengths"]["below_configured_minimum"] == 0
        assert output.exists()


def test_dependency_free_document_loaders():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "notes.txt").write_text("Important plain text.", encoding="utf-8")
        (root / "page.html").write_text("<h1>Title</h1><script>bad()</script><p>Visible text</p>", encoding="utf-8")
        (root / "data.json").write_text('{"policy": {"days": 14}}', encoding="utf-8")
        (root / "rows.csv").write_text("name,value\nalpha,10\n", encoding="utf-8")
        units = load_documents(root)
        combined = "\n".join(unit.text for unit in units)
        assert "Important plain text" in combined
        assert "Visible text" in combined and "bad()" not in combined
        assert "policy.days: 14" in combined
        assert "name: alpha" in combined


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    failures = 0
    for name, test in tests:
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
