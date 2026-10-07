"""Telegram response formatting."""

NO_RESULT_MESSAGE_AR = "لم أتمكن من إيجاد معلومات كافية. هل يمكنك إعادة صياغة سؤالك أو توضيحه أكثر؟ 🤔"
NO_RESULT_MESSAGE_EN = "I couldn't find enough information. Could you rephrase or clarify your question? 🤔"
# ==================== TELEGRAM RESPONSE FORMATTER ====================
class TelegramResponseFormatter:
    SOURCE_ICONS = {
        "verified_facts": "✅",
        "rag": "📚",
        "web": "🌐",
        "cache": "⚡",
        "llm_fallback": "💡",
        "greeting": "👋",
        "out_of_scope": "🚫",
        "error": "⚠️",
        "injection_blocked": "🚫",
        "comparison_rejected": "⚠️",
        "false_premise_corrected": "❌",
        "multi_query": "📑",
        # ✅ ميزات جديدة
        "graduation_simulator":  "🎓",
        "skill_gap_detector":    "🔍",
        "academic_sos":          "🆘",
        "mental_health_support": "💙",
        "faculty_lookup":        "👤",
        "cv_builder":            "📄",
        "linkedin_github_guide": "🔗",
    }
    @staticmethod
    def format(response: str, source: str, language: str = "ar") -> str:
        icon = TelegramResponseFormatter.SOURCE_ICONS.get(source, "🎓")
        no_icon_sources = {"greeting", "out_of_scope", "injection_blocked", "comparison_rejected",
                           "false_premise_corrected", "multi_query",
                           "graduation_simulator", "skill_gap_detector", "academic_sos",
                           "mental_health_support", "faculty_lookup", "cv_builder", "linkedin_github_guide"}
        if source in no_icon_sources:
            return response
        return f"{icon} {response}"
formatter = TelegramResponseFormatter()
