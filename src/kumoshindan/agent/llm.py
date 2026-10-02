"""OpenAI-compatible model client configured for OpenRouter."""

from langchain_openai import ChatOpenAI

from kumoshindan.config import settings


def get_llm() -> ChatOpenAI:
    if settings.llm_provider.lower() != "openai":
        raise ValueError("Set LLM_PROVIDER=openai for the OpenRouter-compatible client.")
    if settings.llm_model == "SET_LATER":
        raise ValueError("Set LLM_MODEL in the project .env file.")
    if not settings.llm_base_url:
        raise ValueError("Set LLM_BASE_URL in the project .env file.")

    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        timeout=60,
        max_retries=1,
    )
