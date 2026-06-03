import os
import httpx
from post_engine import build_system_prompt

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

_system_prompt = build_system_prompt()


def reload_model():
    global _system_prompt
    _system_prompt = build_system_prompt()


async def generate_post(topic: str) -> str:
    messages = [
        {"role": "system", "content": _system_prompt},
        {"role": "user", "content": topic},
    ]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": messages, "max_tokens": 600},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
