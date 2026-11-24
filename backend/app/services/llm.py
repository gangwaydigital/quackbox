"""Shared chat-completion helper for the configured chat LLM (Ollama or OpenAI-compatible)."""
import requests
from app.config import CHAT_API_URL, CHAT_API_KEY, CHAT_API_TYPE, CHAT_EXTRA_BODY


def complete(model: str, messages: list, temperature: float, max_tokens: int, timeout: int):
    """POST a chat completion to the configured API. Returns (status_code, content, raw_text)."""
    if CHAT_API_TYPE == "openai":
        headers = {"Content-Type": "application/json"}
        if CHAT_API_KEY:
            headers["Authorization"] = f"Bearer {CHAT_API_KEY}"
        resp = requests.post(
            f"{CHAT_API_URL}/v1/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
                  **CHAT_EXTRA_BODY},
            timeout=timeout,
        )
        # .get: thinking models can return reasoning only, with no content.
        content = (resp.json()["choices"][0]["message"].get("content") or "") if resp.status_code == 200 else ""
    else:
        resp = requests.post(
            f"{CHAT_API_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": temperature, "num_predict": max_tokens}},
            timeout=timeout,
        )
        content = resp.json().get("message", {}).get("content", "") if resp.status_code == 200 else ""
    return resp.status_code, content, resp.text
