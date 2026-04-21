"""Thin Responses API adapter used by @llm.extract and @llm.outreach."""

from __future__ import annotations

import os
from typing import Any

from property_hunt.config import OpenAIConfig


def response_text(config: OpenAIConfig, *, system: str, user: str) -> str:
    """Call OpenAI Responses and return the best-effort text output."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed") from exc

    client = OpenAI()
    kwargs: dict[str, Any] = {
        "model": config.model,
        "instructions": system,
        "input": user,
    }
    if config.reasoning_effort:
        kwargs["reasoning"] = {"effort": config.reasoning_effort}

    response = client.responses.create(**kwargs)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    return str(response)
