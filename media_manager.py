import os
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from config import config
from database import add_log

WORKSPACE_DIR = os.path.abspath(os.path.dirname(__file__))
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def get_media_dir() -> str:
    media_path = config.media_image_path
    if not os.path.isabs(media_path):
        media_path = os.path.join(WORKSPACE_DIR, media_path)
    return os.path.abspath(media_path)

def list_available_media() -> List[Dict[str, Any]]:
    """Returns a list of image files present in the configured media directory."""
    media_dir = get_media_dir()
    if not os.path.exists(media_dir) or not os.path.isdir(media_dir):
        return []

    results = []
    try:
        for fname in sorted(os.listdir(media_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_IMAGE_EXTS:
                full_path = os.path.join(media_dir, fname)
                if os.path.isfile(full_path):
                    results.append({
                        "filename": fname,
                        "size_bytes": os.path.getsize(full_path),
                        "path": full_path,
                        "rel_path": os.path.relpath(full_path, WORKSPACE_DIR)
                    })
    except Exception as e:
        add_log("WARN", f"Failed to list media files: {str(e)}")
    return results

def get_daily_image_info(explicit_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Returns metadata about the active single daily image for today.
    Every comment on a given day shares this same image.
    """
    target = explicit_path or config.media_image_path
    if not target:
        return None

    if not os.path.isabs(target):
        target = os.path.join(WORKSPACE_DIR, target)

    # 1. Direct file path
    if os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            return {
                "filename": os.path.basename(target),
                "path": os.path.abspath(target),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "reason": "explicit_file"
            }

    # 2. Directory: select today's single daily image
    if os.path.isdir(target):
        images = [
            f for f in sorted(os.listdir(target))
            if os.path.splitext(f)[1].lower() in SUPPORTED_IMAGE_EXTS
            and os.path.isfile(os.path.join(target, f))
        ]
        if not images:
            return None

        today_str = datetime.now().strftime("%Y-%m-%d")

        # Check if an image is specifically named with today's date (e.g. 2026-09-25.jpg or today.png)
        for img in images:
            name_no_ext = os.path.splitext(img)[0].lower()
            if name_no_ext == today_str or name_no_ext == "today" or name_no_ext == "daily":
                return {
                    "filename": img,
                    "path": os.path.abspath(os.path.join(target, img)),
                    "date": today_str,
                    "reason": "date_match"
                }

        # Otherwise, deterministically select 1 image for today using calendar day
        # Guarantees that ALL comments throughout the day share this exact image!
        day_index = date.today().toordinal() % len(images)
        selected_file = images[day_index]
        return {
            "filename": selected_file,
            "path": os.path.abspath(os.path.join(target, selected_file)),
            "date": today_str,
            "day_index": day_index,
            "total_images": len(images),
            "reason": "daily_rotation"
        }

    return None

def get_media_image_to_post(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Resolves the single daily image file to attach alongside all tweet replies for today.
    Guarantees that 1 consistent image is used for all comments on any given day.
    """
    if not config.attach_image:
        return None

    info = get_daily_image_info(explicit_path)
    if info and "path" in info:
        return info["path"]

    add_log("WARN", "Image attachment is enabled, but no valid daily image was found.")
    return None
