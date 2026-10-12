"""Run the golden answer set against a fully configured NovaCortex instance."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(ROOT), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

from novacortex.agent import YarmoukAgent  # noqa: E402
from novacortex.config import require_secrets  # noqa: E402
from novacortex.db import init_db  # noqa: E402
from novacortex.rag.indexing import load_data_from_json  # noqa: E402


def _contains(text, needle):
    return needle.casefold() in text.casefold()


def assess(case, result):
    response = result.get("response", "")
    source = result.get("source", "")
    failures = []
    allowed = case.get("allowed_sources")
    if allowed and source not in allowed:
        failures.append(f"source={source!r}, allowed={allowed}")
    if source in case.get("forbidden_sources", []):
        failures.append(f"forbidden source={source!r}")
    required_all = case.get("must_include_all", [])
    missing = [item for item in required_all if not _contains(response, item)]
    if missing:
        failures.append(f"missing required terms={missing}")
    required_any = case.get("must_include_any", [])
    if required_any and not any(_contains(response, item) for item in required_any):
        failures.append(f"none of required alternatives found={required_any}")
    forbidden = [item for item in case.get("must_not_include", []) if _contains(response, item)]
    if forbidden:
        failures.append(f"forbidden terms found={forbidden}")
    return failures


async def main():
    require_secrets()
    init_db()
    if not load_data_from_json():
        raise SystemExit("Knowledge base could not be loaded")
    cases = json.loads((ROOT / "tests" / "golden_questions.json").read_text(encoding="utf-8"))
    agent = await asyncio.to_thread(YarmoukAgent)
    user_id = 987654321
    passed = 0
    failures = []
    for case in cases:
        result = await agent.ask(case["question"], user_id)
        problems = assess(case, result)
        if problems:
            failures.append({
                "id": case["id"],
                "question": case["question"],
                "source": result.get("source"),
                "confidence": result.get("confidence"),
                "problems": problems,
                "response": result.get("response", "")[:500],
            })
            print(f"FAIL {case['id']}: {'; '.join(problems)}")
        else:
            passed += 1
            print(f"PASS {case['id']} [{result.get('source')}, {result.get('confidence')}]" )
    print(f"\nResult: {passed}/{len(cases)} passed")
    if failures:
        report = ROOT / "evaluation_failures.json"
        report.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Details: {report}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
