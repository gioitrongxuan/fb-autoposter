import os
import json
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fb_client import post_to_page
from ai_client import generate_post
import post_store
import post_engine
import ai_client as _ai

DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.environ.get("DASHBOARD_PASS", "")

security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), DASHBOARD_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), DASHBOARD_PASS.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})


async def _run_due_posts():
    due = post_store.get_due_posts()
    for post in due:
        try:
            result = await post_to_page(post["content"], post.get("link"))
            post_store.mark_published(post["id"], result.get("id"))
            logging.info(f"Published post {post['id']} → FB {result.get('id')}")
        except Exception as e:
            post_store.mark_failed(post["id"], str(e))
            logging.error(f"Failed to publish post {post['id']}: {e}")


async def _scheduler_loop():
    while True:
        try:
            await _run_due_posts()
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_scheduler_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/dashboard")
async def dashboard(_: None = Depends(require_auth)):
    return FileResponse("static/dashboard.html")


@app.get("/privacy")
async def privacy():
    return FileResponse("static/privacy.html")


@app.get("/api/stats")
async def api_stats(_: None = Depends(require_auth)):
    return post_store.stats()


@app.get("/api/posts")
async def api_posts(_: None = Depends(require_auth)):
    return post_store.list_pending()


@app.get("/api/posts/history")
async def api_history(_: None = Depends(require_auth)):
    return post_store.list_history()


@app.post("/api/posts")
async def create_post(request: Request, _: None = Depends(require_auth)):
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")

    scheduled_at = body.get("scheduled_at")
    link = body.get("link", "").strip() or None
    topic = body.get("topic", "").strip() or None
    is_ai = body.get("is_ai_generated", False)
    publish_now = body.get("publish_now", False)

    post = post_store.add_post(content, scheduled_at, link, topic, is_ai)

    if publish_now:
        try:
            result = await post_to_page(post["content"], post.get("link"))
            post_store.mark_published(post["id"], result.get("id"))
            post["status"] = "published"
            post["fb_post_id"] = result.get("id")
        except Exception as e:
            post_store.mark_failed(post["id"], str(e))
            post["status"] = "failed"
            post["error"] = str(e)
            raise HTTPException(status_code=502, detail=str(e))

    return post


@app.post("/api/posts/generate")
async def api_generate(request: Request, _: None = Depends(require_auth)):
    body = await request.json()
    topic = body.get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")
    content = await generate_post(topic)
    return {"content": content}


@app.post("/api/posts/{post_id}/publish")
async def api_publish_now(post_id: str, _: None = Depends(require_auth)):
    post = post_store.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="post not found")
    if post["status"] != "pending":
        raise HTTPException(status_code=400, detail="post is not pending")
    try:
        result = await post_to_page(post["content"], post.get("link"))
        post_store.mark_published(post_id, result.get("id"))
        return {"status": "published", "fb_post_id": result.get("id")}
    except Exception as e:
        post_store.mark_failed(post_id, str(e))
        raise HTTPException(status_code=502, detail=str(e))


@app.delete("/api/posts/{post_id}")
async def api_delete_post(post_id: str, _: None = Depends(require_auth)):
    if not post_store.delete_post(post_id):
        raise HTTPException(status_code=404, detail="post not found or not pending")
    return {"status": "deleted"}


@app.get("/api/profile")
async def get_profile(_: None = Depends(require_auth)):
    path = Path("post_profile.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


@app.post("/api/profile")
async def save_profile(request: Request, _: None = Depends(require_auth)):
    body = await request.json()
    path = Path("post_profile.json")
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    post_engine.load_profile.cache_clear()
    _ai.reload_model()
    return {"status": "ok"}
