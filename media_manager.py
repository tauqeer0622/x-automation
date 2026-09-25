import os
import random
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

def get_media_image_to_post(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Resolves the image file to attach alongside a tweet reply.
    Returns the absolute path to an image file, or None if disabled or no images found.
    """
    if not config.attach_image:
        return None

    target = explicit_path or config.media_image_path
    if not target:
        return None

    # Resolve relative path
    if not os.path.isabs(target):
        target = os.path.join(WORKSPACE_DIR, target)

    # 1. Direct file path
    if os.path.isfile(target):
        ext = os.path.splitext(target)[1].lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            return os.path.abspath(target)

    # 2. Directory of images: pick an image from the folder
    if os.path.isdir(target):
        images = [
            os.path.join(target, f)
            for f in os.listdir(target)
            if os.path.splitext(f)[1].lower() in SUPPORTED_IMAGE_EXTS
            and os.path.isfile(os.path.join(target, f))
        ]
        if images:
            selected = random.choice(images)
            return os.path.abspath(selected)

    add_log("WARN", f"Image attachment is enabled, but no valid image was found at '{target}'")
    return None
