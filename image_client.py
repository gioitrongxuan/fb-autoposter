import asyncio
import logging
import urllib.parse
import httpx
import os
from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


async def make_image_prompt(content: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=(
                "Write a short image generation prompt in English (max 12 words) "
                "for a professional, eye-catching photo that matches this Facebook post. "
                "Output only the prompt, nothing else.\n\n"
                f"{content[:600]}"
            ),
            config=types.GenerateContentConfig(max_output_tokens=40),
        ),
    )
    return response.text.strip().strip('"').strip("'")


def get_image_url(prompt: str) -> str:
    return (
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        "?width=1200&height=630&nologo=true"
    )


async def generate_image_for_post(content: str) -> bytes | None:
    try:
        prompt = await make_image_prompt(content)
        logging.info(f"Image prompt: {prompt!r}")
        url = get_image_url(prompt)
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.is_success and "image" in resp.headers.get("content-type", ""):
                return resp.content
            logging.warning(f"Pollinations returned {resp.status_code}")
    except Exception as e:
        logging.warning(f"Image generation failed: {e}")
    return None
