from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from dotenv import load_dotenv

# Load local .env once so CLI runs pick up API config.
load_dotenv()


@dataclass
class LLMConfig:
    provider: str
    api_key: Optional[str]
    base_url: Optional[str]
    model: str


def _env(name: str) -> Optional[str]:
    value = os.getenv(name, "").strip()
    return value or None


def _provider_default_model(provider: str) -> str:
    if provider == "siliconflow":
        return "Pro/deepseek-ai/DeepSeek-V3.2"
    if provider == "deepseek":
        return "deepseek-chat"
    if provider == "bolatu":
        return "claude-haiku-4-5-20251001"
    return "deepseek-chat"


def resolve_llm_config(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMConfig:
    """
    Resolve LLM provider config with priority:
    SILICONFLOW > DEEPSEEK > BOLATU
    """
    if model is not None:
        chosen_model = model
    else:
        chosen_model = _env("LLM_MODEL")

    if api_key is not None or base_url is not None:
        return LLMConfig(
            provider="custom",
            api_key=api_key,
            base_url=base_url,
            model=chosen_model or _provider_default_model("custom"),
        )

    siliconflow_key = _env("SILICONFLOW_API_KEY")
    if siliconflow_key:
        return LLMConfig(
            provider="siliconflow",
            api_key=siliconflow_key,
            base_url=_env("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1",
            model=chosen_model
            or _env("SILICONFLOW_MODEL")
            or _provider_default_model("siliconflow"),
        )

    deepseek_key = _env("DEEPSEEK_API_KEY")
    deepseek_base_url = _env("DEEPSEEK_BASE_URL")
    if deepseek_key:
        return LLMConfig(
            provider="deepseek",
            api_key=deepseek_key,
            base_url=deepseek_base_url or "https://api.deepseek.com/v1",
            model=chosen_model
            or _env("DEEPSEEK_MODEL")
            or _provider_default_model("deepseek"),
        )

    bolatu_base_url = _env("BOLATU_BASE_URL")
    bolatu_key = _env("BOLATU_API_KEY")
    if bolatu_base_url:
        return LLMConfig(
            provider="bolatu",
            api_key=bolatu_key,
            base_url=bolatu_base_url,
            model=chosen_model
            or _env("BOLATU_MODEL")
            or _provider_default_model("bolatu"),
        )

    if bolatu_key:
        return LLMConfig(
            provider="bolatu",
            api_key=bolatu_key,
            base_url="https://api.bltcy.ai",
            model=chosen_model
            or _env("BOLATU_MODEL")
            or _provider_default_model("bolatu"),
        )

    return LLMConfig(
        provider="default",
        api_key=_env("OPENAI_API_KEY"),
        base_url=_env("LLM_BASE_URL") or _env("OPENAI_BASE_URL"),
        model=chosen_model or _env("OPENAI_MODEL") or _provider_default_model("default"),
    )


def build_llamaindex_llm(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
) -> Tuple[LLMConfig, Optional[Any]]:
    """
    Build a LlamaIndex-compatible chat LLM from env/provider config.
    Returns (resolved_config, llm_instance_or_none).
    """
    config = resolve_llm_config(model=model, base_url=base_url, api_key=api_key)
    if not config.api_key:
        return config, None

    try:
        from llama_index.llms.openai_like import OpenAILike
    except Exception:
        return config, None

    # Force deterministic extraction to avoid JSON hallucination.
    llm = OpenAILike(
        model=config.model,
        api_key=config.api_key,
        api_base=config.base_url,
        temperature=0.0,
        is_chat_model=True,
    )
    return config, llm
