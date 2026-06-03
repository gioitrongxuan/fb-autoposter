import asyncio
import logging
import random
import httpx
import os
from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")


async def make_image_keywords(content: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=(
                "Extract 2-3 English keywords for a stock photo search that matches this post. "
                "Output only the keywords separated by spaces, nothing else.\n\n"
                f"{content[:400]}"
            ),
            config=types.GenerateContentConfig(max_output_tokens=20),
        ),
    )
    return response.text.strip().strip('"')


async def _search_pexels(query: str) -> bytes | None:
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
            logging.warning(f"Pexels: no photos for query '{query}'")
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
        logging.warning("Pexels returned no result, trying broader keyword")
        # Retry với keyword đầu tiên thôi
        first_keyword = keywords.split()[0] if keywords else "lifestyle"
        return await _search_pexels(first_keyword)
    except Exception as e:
        logging.warning(f"Image fetch failed: {e}")
    return None


async def get_preview_url(content: str) -> tuple[str, str]:
    """Return (image_url, keywords) for dashboard preview — no download."""
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
    return "", keywords
