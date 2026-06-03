import os
import asyncio
import logging
from google import genai
from google.genai import types
from post_engine import build_system_prompt
import deepseek_client

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
_system_prompt = build_system_prompt()


def reload_model():
    global _system_prompt
    from post_engine import load_profile
    load_profile.cache_clear()
    _system_prompt = build_system_prompt()
    deepseek_client.reload_model()


async def _gemini_generate(topic: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=topic,
            config=types.GenerateContentConfig(
                system_instruction=_system_prompt,
                max_output_tokens=600,
            ),
        ),
    )
    return response.text


async def generate_post(topic: str) -> str:
    try:
        return await _gemini_generate(topic)
    except Exception as e:
        err = str(e)
        if any(code in err for code in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
            logging.warning(f"Gemini unavailable ({err[:60]}), switching to DeepSeek")
            return await deepseek_client.generate_post(topic)
        raise
