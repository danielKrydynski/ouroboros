"""Model routing: local Ollama first, OpenRouter fallback on failure.

The loop is designed to run almost entirely on local hardware. The cloud is
a fallback for hard tasks, not the default — local-first keeps every cycle
free and private.
"""
from __future__ import annotations

import os

import requests

DEFAULT_CTX = 32768

# Shown to OpenRouter as the requesting app. Change to your repo URL.
APP_REFERER = "https://github.com/danielKrydynski/ouroboros"
APP_TITLE = "ouroboros-dev-loop"


def _messages(system: str, user: str) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def ollama_chat(base_url: str, model: str, system: str, user: str,
                timeout: int = 900) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": _messages(system, user),
            "stream": False,
            "options": {"num_ctx": DEFAULT_CTX},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def openrouter_chat(base_url: str, api_key: str, model: str, system: str,
                    user: str, timeout: int = 900) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": APP_REFERER,
            "X-Title": APP_TITLE,
        },
        json={"model": model, "messages": _messages(system, user)},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def complete(cfg: dict, role: str, system: str, user: str) -> tuple[str, str]:
    """Run one chat completion. Returns (text, which_model).

    Tries the role's local Ollama model first; on any failure, falls back to
    the configured OpenRouter model if an API key is available.
    """
    models = cfg["models"]
    local = models["local"]
    model_name = local.get(role) or local.get("default")
    try:
        return ollama_chat(local["base_url"], model_name, system, user), \
            f"local:{model_name}"
    except Exception as exc:  # noqa: BLE001 - fallback is the whole point
        cloud = models.get("cloud_fallback", {})
        api_key = os.environ.get(cloud.get("api_key_env", "OPENROUTER_API_KEY"), "")
        if not api_key:
            raise RuntimeError(
                f"Local model '{model_name}' failed ({exc}) and no "
                f"{cloud.get('api_key_env', 'OPENROUTER_API_KEY')} is set "
                "for cloud fallback."
            ) from exc
        text = openrouter_chat(cloud["base_url"], api_key, cloud["model"],
                               system, user)
        return text, f"cloud:{cloud['model']}"
