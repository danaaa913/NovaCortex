"""Structural checks for the content-level evaluation set."""

import json
from pathlib import Path


DATASET = Path(__file__).with_name("golden_questions.json")


def test_golden_dataset_has_broad_unique_cases():
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    assert len(cases) >= 20
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert all(case.get("question") for case in cases)
    assert all(
        case.get("allowed_sources") or case.get("forbidden_sources")
        for case in cases
    )
    assert any("must_include_all" in case for case in cases)
    assert any("must_not_include" in case for case in cases)


if __name__ == "__main__":
    test_golden_dataset_has_broad_unique_cases()
    print("golden dataset: PASS")
