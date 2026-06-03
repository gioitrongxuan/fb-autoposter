import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STORE_FILE = Path("posts.json")
_lock = threading.Lock()


def _load() -> dict:
    if STORE_FILE.exists():
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    return {"posts": []}


def _save(data: dict):
    STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_post(content: str, scheduled_at: str | None, link: str | None, topic: str | None, is_ai: bool) -> dict:
    now = _now_iso()
    post = {
        "id": str(uuid.uuid4()),
        "content": content,
        "link": link,
        "status": "pending",
        "created_at": now,
        "scheduled_at": scheduled_at or now,
        "published_at": None,
        "fb_post_id": None,
        "error": None,
        "topic": topic,
        "is_ai_generated": is_ai,
    }
    with _lock:
        data = _load()
        data["posts"].append(post)
        _save(data)
    return post


def get_post(post_id: str) -> dict | None:
    with _lock:
        data = _load()
    return next((p for p in data["posts"] if p["id"] == post_id), None)


def get_due_posts() -> list:
    now = _now_iso()
    with _lock:
        data = _load()
    return [p for p in data["posts"] if p["status"] == "pending" and p["scheduled_at"] <= now]


def mark_published(post_id: str, fb_post_id: str | None):
    with _lock:
        data = _load()
        for p in data["posts"]:
            if p["id"] == post_id:
                p["status"] = "published"
                p["published_at"] = _now_iso()
                p["fb_post_id"] = fb_post_id
                break
        _save(data)


def mark_failed(post_id: str, error: str):
    with _lock:
        data = _load()
        for p in data["posts"]:
            if p["id"] == post_id:
                p["status"] = "failed"
                p["error"] = error[:500]
                break
        _save(data)


def delete_post(post_id: str) -> bool:
    with _lock:
        data = _load()
        before = len(data["posts"])
        data["posts"] = [p for p in data["posts"] if not (p["id"] == post_id and p["status"] == "pending")]
        if len(data["posts"]) == before:
            return False
        _save(data)
    return True


def list_pending() -> list:
    with _lock:
        data = _load()
    return sorted(
        [p for p in data["posts"] if p["status"] == "pending"],
        key=lambda p: p["scheduled_at"],
    )


def list_history(limit: int = 50) -> list:
    with _lock:
        data = _load()
    done = [p for p in data["posts"] if p["status"] in ("published", "failed")]
    return sorted(done, key=lambda p: p.get("published_at") or p["created_at"], reverse=True)[:limit]


def stats() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        data = _load()
    posts = data["posts"]
    return {
        "scheduled": sum(1 for p in posts if p["status"] == "pending"),
        "published_today": sum(
            1 for p in posts
            if p["status"] == "published" and (p.get("published_at") or "")[:10] == today
        ),
        "failed": sum(1 for p in posts if p["status"] == "failed"),
        "total_published": sum(1 for p in posts if p["status"] == "published"),
    }
