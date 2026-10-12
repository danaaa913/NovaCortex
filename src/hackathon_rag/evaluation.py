"""Small repeatable evaluation runner for retrieval and grounded answers."""

import json
from pathlib import Path
from typing import Any, Dict, List

from .pipeline import HackathonRAG


def load_cases(path: Path) -> List[Dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Evaluation file must contain a JSON list")
    return value


def evaluate(rag: HackathonRAG, cases_path: Path) -> Dict[str, Any]:
    cases = load_cases(cases_path)
    details = []
    passed = 0
    for case in cases:
        result = rag.ask(case["question"]).to_dict()
        problems = []
        expected_supported = case.get("supported")
        if expected_supported is not None and result["supported"] != expected_supported:
            problems.append(f"supported={result['supported']} expected={expected_supported}")
        answer_folded = result["answer"].casefold()
        missing = [term for term in case.get("must_include", []) if term.casefold() not in answer_folded]
        if missing:
            problems.append(f"missing={missing}")
        forbidden = [term for term in case.get("must_not_include", []) if term.casefold() in answer_folded]
        if forbidden:
            problems.append(f"forbidden={forbidden}")
        expected_source = case.get("expected_source")
        sources = {citation["source"] for citation in result["citations"]}
        if expected_source and expected_source not in sources:
            problems.append(f"expected_source={expected_source!r}, got={sorted(sources)}")
        if not problems:
            passed += 1
        details.append({"question": case["question"], "problems": problems, "result": result})
    return {"passed": passed, "total": len(cases), "details": details}
