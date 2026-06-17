import os
import shutil
from datetime import datetime
from typing import List

from config import ROOT_DIR
from status import error, info, success, warning

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
CACHE_DIR_NAME = "image_cache"


def get_image_cache_dir() -> str:
    """Return the persistent image cache directory inside .mp."""
    cache_dir = os.path.join(ROOT_DIR, ".mp", CACHE_DIR_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _is_image_file(path: str) -> bool:
    return os.path.isfile(path) and path.lower().endswith(IMAGE_EXTENSIONS)


def get_cached_images(limit: int = 30) -> List[str]:
    """Return cached image paths, newest first."""
    cache_dir = get_image_cache_dir()
    images = [
        os.path.join(cache_dir, name)
        for name in os.listdir(cache_dir)
        if _is_image_file(os.path.join(cache_dir, name))
    ]
    images.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return images[:limit]


def preserve_generated_images(image_paths: List[str] | None = None) -> List[str]:
    """Copy generated images into a persistent cache for later reuse."""
    cache_dir = get_image_cache_dir()
    source_paths = []

    if image_paths:
        source_paths.extend(image_paths)

    mp_dir = os.path.join(ROOT_DIR, ".mp")
    if os.path.isdir(mp_dir):
        source_paths.extend(
            os.path.join(mp_dir, name)
            for name in os.listdir(mp_dir)
            if _is_image_file(os.path.join(mp_dir, name))
        )

    preserved = []
    seen = set()
    for source_path in source_paths:
        if not _is_image_file(source_path):
            continue
        absolute_source = os.path.abspath(source_path)
        if absolute_source in seen:
            continue
        seen.add(absolute_source)

        basename = os.path.basename(source_path)
        target_path = os.path.join(cache_dir, basename)
        if os.path.abspath(target_path) == absolute_source:
            preserved.append(target_path)
            continue

        if os.path.exists(target_path):
            name, ext = os.path.splitext(basename)
            target_path = os.path.join(cache_dir, f"{name}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}")

        shutil.copy2(source_path, target_path)
        preserved.append(target_path)

    if preserved:
        success(f"Preserved {len(preserved)} generated image(s) in cache.")

    return preserved


def generate_video_with_image_preservation(youtube, tts_instance, **generate_kwargs) -> str:
    """Generate a video normally and preserve generated images for reuse."""
    try:
        path = youtube.generate_video(tts_instance, **generate_kwargs)
        preserve_generated_images(getattr(youtube, "images", []))
        return path
    except Exception:
        preserve_generated_images(getattr(youtube, "images", []))
        raise


def generate_video_reusing_cached_images(youtube, tts_instance, limit: int = 20) -> str:
    """Generate a new short while reusing cached images instead of calling the image API."""
    cached_images = get_cached_images(limit=limit)
    if not cached_images:
        error("No cached images found. Generate a normal short first or add images to .mp/image_cache.")
        return None

    info(f" => Reusing {len(cached_images)} cached image(s).")

    if hasattr(youtube, "_reset_generation_state"):
        youtube._reset_generation_state()

    youtube.generate_topic()
    youtube.generate_script()
    youtube.generate_metadata()
    youtube.images = list(cached_images)
    youtube.generate_script_to_speech(tts_instance)

    path = youtube.combine()
    youtube.video_path = os.path.abspath(path)
    if hasattr(youtube, "_save_generation_manifest"):
        youtube._save_generation_manifest()

    if hasattr(youtube, "metadata"):
        youtube.add_video(
            {
                "title": youtube.metadata.get("title", "Cached image short"),
                "description": youtube.metadata.get("description", ""),
                "url": path,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    success(f'Generated video with cached images: "{path}"')
    exported_video_path = getattr(youtube, "exported_video_path", None)
    exported_video_dir = getattr(youtube, "exported_video_dir", None)
    if exported_video_path:
        success(f'Persistent exported copy: "{exported_video_path}"')
    if exported_video_dir:
        success(f'Video project folder: "{exported_video_dir}"')
    return path
