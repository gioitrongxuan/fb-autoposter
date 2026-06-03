import asyncio
import logging
import random
import httpx
import os
from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

_KEYWORD_SYSTEM = (
    "Extract 2-3 English keywords for a Pexels stock photo search "
    "that matches this post. Output ONLY the keywords separated by spaces."
)


async def _gemini_keywords(content: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{_KEYWORD_SYSTEM}\n\n{content[:400]}",
            config=types.GenerateContentConfig(max_output_tokens=20),
        ),
    )
    return response.text.strip().strip('"')


async def _deepseek_keywords(content: str) -> str:
    messages = [
        {"role": "system", "content": _KEYWORD_SYSTEM},
        {"role": "user", "content": content[:400]},
    ]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": messages, "max_tokens": 20},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def make_image_keywords(content: str) -> str:
    # 1. Try Gemini
    try:
        return await _gemini_keywords(content)
    except Exception as e:
        err = str(e)
        if any(c in err for c in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
            logging.warning("Gemini rate-limited for keywords, trying DeepSeek")
        else:
            logging.warning(f"Gemini keyword error: {e}")

    # 2. Try DeepSeek
    if DEEPSEEK_API_KEY:
        try:
            return await _deepseek_keywords(content)
        except Exception as e:
            logging.warning(f"DeepSeek keyword error: {e}")

    # 3. Simple fallback: dùng các từ dài > 3 ký tự đầu tiên
    words = [w.strip(".,!?") for w in content.split() if len(w) > 4][:3]
    return " ".join(words) if words else "lifestyle product"


async def _search_pexels(query: str) -> bytes | None:
    if not PEXELS_API_KEY:
        logging.warning("PEXELS_API_KEY not set")
        return None
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "orientation": "landscape"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.pexels.com/v1/search", headers=headers, params=params
        )
        if not resp.is_success:
            logging.warning(f"Pexels search failed: {resp.status_code}")
            return None
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        photo = random.choice(photos[:5])
        img_url = photo["src"]["large2x"]
        logging.info(f"Pexels image: {img_url}")
        img_resp = await client.get(img_url, timeout=15)
        if img_resp.is_success:
            return img_resp.content
    return None


async def generate_image_for_post(content: str) -> bytes | None:
    try:
        keywords = await make_image_keywords(content)
        logging.info(f"Image keywords: {keywords!r}")
        img = await _search_pexels(keywords)
        if img:
            return img
        # Retry với keyword đầu tiên
        first = keywords.split()[0] if keywords else "lifestyle"
        return await _search_pexels(first)
    except Exception as e:
        logging.warning(f"Image fetch failed: {e}")
    return None


async def get_preview_url(content: str) -> tuple[str, str]:
    """Return (image_url, keywords) for dashboard preview."""
    if not PEXELS_API_KEY:
        return "", "PEXELS_API_KEY chưa được cấu hình"
    try:
        keywords = await make_image_keywords(content)
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": keywords, "per_page": 5, "orientation": "landscape"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.pexels.com/v1/search", headers=headers, params=params
            )
            if resp.is_success:
                photos = resp.json().get("photos", [])
                if photos:
                    photo = random.choice(photos[:5])
                    return photo["src"]["large"], keywords
    except Exception as e:
        logging.warning(f"Preview image error: {e}")
    return "", keywords if "keywords" in dir() else "no results"
