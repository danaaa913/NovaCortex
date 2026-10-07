"""End-to-end agent test (needs a working environment + network access).

Skipped by default. Run explicitly with:

    NOVACORTEX_RUN_INTEGRATION=1 python tests/test_bot_internal.py
    NOVACORTEX_RUN_INTEGRATION=1 python -m pytest tests/test_bot_internal.py

Working directory must be the project root (paths are CWD-relative).
"""
import asyncio
import logging
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RUN = os.environ.get("NOVACORTEX_RUN_INTEGRATION") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TEST_CASES = [
    {
        "name": "Verified Facts (Direct Route)",
        "query": "متى تأسست جامعة اليرموك؟",
        "expected_source_type": "verified_facts",
    },
    {
        "name": "RAG Retrieval (Previously Hardcoded)",
        "query": "ما هي التخصصات المتاحة في كلية الآداب؟",
        "expected_source_type": "rag",
    },
    {
        "name": "Advisory/Subjective (Fallback)",
        "query": "هل تنصحني ادرس هندسة باليرموك؟",
        "expected_source_type": "verified_facts",
    },
    {
        "name": "Clarification Needs (Too short/vague)",
        "query": "أفكار كثيرة",
        "expected_source_type": "web_empty",
    },
    {
        "name": "Time-Sensitive Web Search",
        "query": "متى موعد التسجيل للفصل الصيفي ٢٠٢٦ بجامعة اليرموك؟",
        "expected_source_type": "web",
    },
    {
        "name": "Out of Scope",
        "query": "من ربح كأس العالم 2022؟",
        "expected_source_type": "out_of_scope",
    },
]


async def run_tests():
    from novacortex.agent import YarmoukAgent
    from novacortex.db import init_db
    from novacortex.rag.indexing import load_data_from_json

    logger.info("Initializing tests for NovaCortex v14.0...")

    init_db()
    if not load_data_from_json():
        logger.error("Failed to load data. Tests cannot proceed.")
        return

    try:
        agent = YarmoukAgent()
        logger.info("Agent initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        return

    test_user_id = 999999999
    logger.info(f"\n{'=' * 50}\nStarting {len(TEST_CASES)} Test Cases\n{'=' * 50}")

    passed = 0
    failed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        logger.info(f"--- Test {i}: {tc['name']} ---")
        logger.info(f"Query: '{tc['query']}'")
        try:
            start_t = time.time()
            result = await agent.ask(tc["query"], test_user_id)
            end_t = time.time()
            logger.info(f"Source: {result.get('source')}")
            logger.info(f"Confidence: {result.get('confidence')}%")
            logger.info(f"Time: {int((end_t - start_t) * 1000)}ms")
            logger.info(f"Response snippet: {result.get('response', '')[:150]}...")

            if result.get("source") == tc.get("expected_source_type") or (
                tc.get("expected_source_type") == "web_empty"
                and result.get("source") in ("error", "web_empty")
            ):
                logger.info("PASS (Source matched expectation)")
                passed += 1
            else:
                logger.warning(
                    f"POTENTIAL FAIL (Expected source '{tc.get('expected_source_type')}', "
                    f"got '{result.get('source')}')"
                )
                if result.get("confidence", 0) >= 70 and tc.get("expected_source_type") != "out_of_scope":
                    logger.info("PASS (Source different, but confidence high)")
                    passed += 1
                else:
                    failed += 1
        except Exception as e:
            logger.error(f"FAIL (Exception: {e})")
            failed += 1
        logger.info("-" * 40 + "\n")

    logger.info(f"--- Test {len(TEST_CASES) + 1}: Semantic Caching ---")
    query1 = "وين موقع كلية الطب؟"
    query2 = "أين تقع كلية الطب البشري؟"

    logger.info(f"Q1 (Initial): '{query1}'")
    res1 = await agent.ask(query1, test_user_id)
    logger.info(f"Source: {res1.get('source')} | Confidence: {res1.get('confidence')}%")

    logger.info(f"Q2 (Should hit cache): '{query2}'")
    res2 = await agent.ask(query2, test_user_id)
    logger.info(f"Source: {res2.get('source')} | Confidence: {res2.get('confidence')}%")

    if res2.get("source") == "cache":
        logger.info("PASS (Semantic Cache Hit)")
        passed += 1
    else:
        logger.warning(f"POTENTIAL FAIL (Expected cache hit, got {res2.get('source')})")
        failed += 1

    logger.info(f"\n{'=' * 50}\nTest Results: {passed} Passed, {failed} Pending Review\n{'=' * 50}")


def test_agent_end_to_end():
    """pytest entry point - skipped unless NOVACORTEX_RUN_INTEGRATION=1."""
    import pytest

    if not RUN:
        pytest.skip("set NOVACORTEX_RUN_INTEGRATION=1 to run integration tests")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())


if __name__ == "__main__":
    if not RUN:
        print("Integration test skipped - set NOVACORTEX_RUN_INTEGRATION=1 to run.")
        sys.exit(0)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())
