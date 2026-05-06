import structlog
from functools import lru_cache

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider

logger = structlog.get_logger(__name__)


def get_ai_provider() -> BaseAIProvider:
    """
    Factory function — returns the correct provider based on AI_PROVIDER env var.

    To add a new provider:
    1. Create your provider class in this folder
    2. Import it here
    3. Add one elif line below
    4. Change AI_PROVIDER env var — done.
    """
    provider = settings.AI_PROVIDER.lower().strip()

    logger.info("Loading AI provider", provider=provider)

    if provider == "gemini":
        from app.services.ai_providers.gemini_provider import GeminiProvider
        return GeminiProvider()

    elif provider == "claude":
        from app.services.ai_providers.claude_provider import ClaudeProvider
        return ClaudeProvider()

    elif provider == "openai":
        from app.services.ai_providers.openai_provider import OpenAIProvider
        return OpenAIProvider()

    elif provider == "ollama":
        from app.services.ai_providers.ollama_provider import OllamaProvider
        return OllamaProvider()

    elif provider == "groq":
        from app.services.ai_providers.groq_provider import GroqProvider
        return GroqProvider()

    else:
        raise ValueError(
            f"Unknown AI provider: '{provider}'. "
            f"Valid options: gemini, claude, openai, ollama, groq. "
            f"Set AI_PROVIDER env var to one of these."
        )


# Cache the provider instance — instantiated once per process
# This avoids re-reading config and re-initializing SDK on every request
@lru_cache(maxsize=1)
def get_cached_ai_provider() -> BaseAIProvider:
    return get_ai_provider()