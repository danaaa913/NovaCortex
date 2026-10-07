"""Backwards-compatible entry point for the NovaCortex bot.

The implementation moved to the ``novacortex`` package (see ``src/``).
This module keeps the old import surface working, e.g.::

    from NovaCortexbot import YarmoukAgent, load_data_from_json

and ``python NovaCortexbot.py`` still starts the bot.
"""
import logging

from novacortex.logging_setup import configure_logging

configure_logging()

from novacortex.agent import YarmoukAgent, logger  # noqa: F401
from novacortex.bot.handlers import cancel, clear_memory_command, handle_message, id_provided, level_chosen, logger, main, start  # noqa: F401
from novacortex.cache import SemanticResponseCache, _is_incompatible_cache, compute_dynamic_threshold, logger  # noqa: F401
from novacortex.config import CACHE_DIR, CHROMA_PATH, CURRENT_MONTH, CURRENT_YEAR, DATA_DIR, DATA_FILE, DB_PATH, GROQ_API_KEY, LOG_FILE, OFFICIAL_PDFS, RAG_CONFIDENCE_THRESHOLD, SERPER_API_KEY, SYNTHETIC_FROZEN, SYNTHETIC_QUESTIONS_FILE, TELEGRAM_TOKEN, UNIVERSITY_NAME, logger, missing_secrets, require_secrets  # noqa: F401
from novacortex.db import get_user, init_db, log_question, logger, save_user, update_daily_stats, update_user_activity  # noqa: F401
from novacortex.formatting import NO_RESULT_MESSAGE_AR, NO_RESULT_MESSAGE_EN, TelegramResponseFormatter, formatter  # noqa: F401
from novacortex.intents import SemanticIntentParser, SmartFactsRouter, expand_colloquial_terms, facts_router, logger, semantic_parser  # noqa: F401
from novacortex.knowledge.careers import CV_TEMPLATES, SKILL_GAP_DATA  # noqa: F401
from novacortex.knowledge.facts import VERIFIED_FACTS  # noqa: F401
from novacortex.knowledge.faculty import COLLOQUIAL_FACULTY_TERMS, COUNSELING_CONTACTS, FACULTY_DB, FMD_BASE_URL, FMD_SEARCH_URL, GRADUATION_HOURS, HARD_COURSES_BY_MAJOR  # noqa: F401
from novacortex.knowledge.keywords import ACADEMIC_SOS_KEYWORDS, COST_SPECIFIC_KEYWORDS, CRISIS_KEYWORDS, CV_BUILDER_KEYWORDS, FEES_KEYWORDS, GRADUATION_SIMULATOR_KEYWORDS, LINKEDIN_GUIDE_KEYWORDS, SCHOLARSHIP_KEYWORDS, SKILL_GAP_KEYWORDS, UNIVERSITY_CONTEXT_KEYWORDS  # noqa: F401
from novacortex.knowledge.localization import INTERNATIONAL_DATA, LANGUAGE_BRIDGE  # noqa: F401
from novacortex.llm import grok_client, llm_client  # noqa: F401
from novacortex.logging_setup import configure_logging  # noqa: F401
from novacortex.memory import SmartMemorySystem, logger, memory_system  # noqa: F401
from novacortex.pipeline import EnhancedHybridPipeline, logger  # noqa: F401
from novacortex.rag.generation import ImprovedLLMAnswerGenerator, apply_proxy_prompt, llm_generator, logger  # noqa: F401
from novacortex.rag.indexing import DATA_HASH_FILE, EXTERNAL_PLANS_TITLE_MAP, _compute_file_hash, _data_has_changed, _fix_reversed_arabic, _is_garbled_content, _save_data_hash, load_data_from_json, logger  # noqa: F401
from novacortex.rag.pdf import PDFExtractor, logger  # noqa: F401
from novacortex.rag.reranking import LLMReranker, logger, reranker  # noqa: F401
from novacortex.rag.retriever import ImprovedHybridRetriever, logger, synthetic_retriever  # noqa: F401
from novacortex.rag.web_search import EnhancedWebSearcher, extract_raw_contact_data, generate_deep_faculty_query, logger, web_searcher  # noqa: F401
from novacortex.safety import INJECTION_PATTERNS, SmartOutOfScopeDetector, _check_false_premise_fallback, check_false_premise, check_false_premise_llm, detect_injection, detect_response_depth, handle_greeting, is_comparison_question, is_general_oos, logger, scope_detector  # noqa: F401
from novacortex.text import ArabicProcessor, arabic_processor  # noqa: F401

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    from novacortex.bot.handlers import main

    main()
