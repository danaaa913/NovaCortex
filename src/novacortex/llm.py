"""LLM client (Groq, OpenAI-compatible endpoint) used across the bot."""
import httpx
from openai import OpenAI

from novacortex.config import GROQ_API_KEY

# The client is created on first use so that importing the package never fails
# just because the secrets have not been configured yet (e.g. during tests).
class _LazyLLMClient:
    """Proxy that builds the real OpenAI client on first attribute access."""

    _client = None

    def _build(self):
        if _LazyLLMClient._client is None:
            _LazyLLMClient._client = OpenAI(
                api_key=GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                http_client=httpx.Client(follow_redirects=True, timeout=25.0),
            )
        return _LazyLLMClient._client

    def __getattr__(self, name):
        return getattr(self._build(), name)


llm_client = _LazyLLMClient()
grok_client = llm_client  # backwards-compatible alias
