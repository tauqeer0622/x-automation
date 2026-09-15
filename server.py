import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from config import config
from database import (
    get_stats, get_recent_posts, get_recent_comments,
    get_recent_logs, add_log
)
from engine import engine
from comment_generator import generator
from browser_controller import browser_controller

app = FastAPI(title="X Automation Dashboard")

# Static assets directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return JSONResponse({"message": "Dashboard UI is initializing..."}, status_code=200)
    return FileResponse(index_path)

@app.get("/api/status")
def get_system_status():
    stats = get_stats()
    engine_status = engine.get_status()
    return {
        "engine": engine_status,
        "stats": stats,
        "config": {
            "company_name": config.company_name,
            "company_one_liner": config.company_one_liner,
            "company_cta": config.company_cta,
            "company_url": config.company_url,
            "target_keywords": config.target_keywords_raw,
            "negative_keywords": config.negative_keywords_raw,
            "dry_run": config.dry_run,
            "min_delay_seconds": config.min_delay_seconds,
            "max_delay_seconds": config.max_delay_seconds,
            "daily_comment_limit": config.daily_comment_limit,
            "has_openai_key": bool(config.openai_api_key and config.openai_api_key.strip()),
            "headless": config.headless
        }
    }

@app.post("/api/control/start")
def start_automation():
    if engine.state == "running":
        return {"status": "already_running"}
    engine.start()
    return {"status": "started"}

@app.post("/api/control/stop")
def stop_automation():
    engine.stop()
    return {"status": "stopped"}

@app.post("/api/browser/open-login")
def open_browser_for_login():
    """Opens browser in visible mode via independent process so the user can complete X login manually."""
    import subprocess
    import sys

    if engine.state == "running":
        engine.stop()

    login_script = os.path.join(os.path.dirname(__file__), "login.py")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                f'start cmd /k "{sys.executable}" "{login_script}"',
                shell=True
            )
        else:
            subprocess.Popen([sys.executable, login_script])

        add_log("INFO", "Launched login helper window.")
        return {"status": "opened", "message": "Login window opened! Complete login in the browser and press Enter in the terminal."}
    except Exception as e:
        add_log("ERROR", f"Failed to launch login process: {str(e)}")
        return {"status": "error", "message": str(e)}

class ConfigUpdateRequest(BaseModel):
    company_name: Optional[str] = None
    company_one_liner: Optional[str] = None
    company_cta: Optional[str] = None
    company_url: Optional[str] = None
    target_keywords: Optional[str] = None
    negative_keywords: Optional[str] = None
    dry_run: Optional[bool] = None
    min_delay_seconds: Optional[int] = None
    max_delay_seconds: Optional[int] = None
    daily_comment_limit: Optional[int] = None
    openai_api_key: Optional[str] = None
    headless: Optional[bool] = None

@app.post("/api/config")
def update_config(data: ConfigUpdateRequest):
    updates = data.model_dump(exclude_unset=True)
    
    # Map request keys to AppConfig fields
    field_map = {
        "target_keywords": "target_keywords_raw",
        "negative_keywords": "negative_keywords_raw",
    }
    
    for key, val in updates.items():
        attr_name = field_map.get(key, key)
        if hasattr(config, attr_name):
            setattr(config, attr_name, val)
    
    add_log("INFO", "System configuration updated from dashboard")
    return {"status": "updated", "config": config.model_dump()}

@app.get("/api/posts")
def get_posts():
    return {"posts": get_recent_posts(60)}

@app.get("/api/comments")
def get_comments():
    return {"comments": get_recent_comments(60)}

@app.get("/api/logs")
def get_logs():
    return {"logs": get_recent_logs(60)}

class TestGenerateRequest(BaseModel):
    tweet_text: str
    author: Optional[str] = "crypto_user"
    keyword: Optional[str] = "crypto"

@app.post("/api/test/generate")
def test_generate_comment(req: TestGenerateRequest):
    comment = generator.generate(req.tweet_text, req.author, req.keyword)
    return {
        "reply": comment,
        "length": len(comment),
        "author": req.author,
        "mode": "ai" if (config.openai_api_key and config.openai_api_key.strip()) else "template"
    }
