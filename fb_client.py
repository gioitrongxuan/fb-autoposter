import os
import httpx

FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "me")
GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def post_to_page(message: str, link: str = None) -> dict:
    url = f"{GRAPH_API_BASE}/{FB_PAGE_ID}/feed"
    payload = {"message": message, "access_token": FB_PAGE_ACCESS_TOKEN}
    if link:
        payload["link"] = link

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        if not resp.is_success:
            raise RuntimeError(f"Facebook API {resp.status_code}: {resp.text}")
        return resp.json()
