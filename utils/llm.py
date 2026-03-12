from utils.config import (
    LLM_PROVIDER,
    LLM_MODEL,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    OLLAMA_BASE_URL,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def build_llm():
    """
    Returns an LLM instance based on LLM_PROVIDER in .env.
    Use anywhere in the project:

        from utils.llm import build_llm
        llm = build_llm()
    """
    provider = LLM_PROVIDER.lower()
    logger.info(f"[LLM] LLM_PROVIDER={provider} | LLM_MODEL={LLM_MODEL}")

    if provider == "groq":
        from langchain_groq import ChatGroq
        if not GROQ_API_KEY:
            raise EnvironmentError("GROQ_API_KEY not set in .env")
        return ChatGroq(
            model=LLM_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0.5,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        if not OPENAI_API_KEY:
            raise EnvironmentError("OPENAI_API_KEY not set in .env")
        return ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0.5,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.5,
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use groq | openai | ollama")