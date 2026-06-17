import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from cache import get_accounts
from config import ROOT_DIR

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def get_image_library_dir() -> str:
    library_dir = os.path.join(ROOT_DIR, "outputs", "image_library")
    os.makedirs(library_dir, exist_ok=True)
    return library_dir


def _is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _collect_candidate_images() -> list[Path]:
    candidates = []
    for relative in [Path(".mp"), Path(".mp") / "image_cache"]:
        directory = Path(ROOT_DIR) / relative
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if _is_image_file(path):
                candidates.append(path)
    return sorted(candidates, key=lambda item: item.stat().st_mtime)


def _group_images_by_session(images: list[Path], session_gap_seconds: int = 900) -> list[list[Path]]:
    groups: list[list[Path]] = []
    current_group: list[Path] = []
    previous_mtime = None

    for image in images:
        mtime = image.stat().st_mtime
        if previous_mtime is None or (mtime - previous_mtime) <= session_gap_seconds:
            current_group.append(image)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [image]
        previous_mtime = mtime

    if current_group:
        groups.append(current_group)

    return groups


def _infer_topic() -> str:
    accounts = get_accounts("youtube")
    if len(accounts) == 1:
        return str(accounts[0].get("niche", "recovered-images")).strip() or "recovered-images"
    return "recovered-images"


def recover_image_library() -> dict:
    library_dir = Path(get_image_library_dir())
    images = _collect_candidate_images()
    groups = _group_images_by_session(images)
    known_hashes = set()
    created_projects = []

    for existing_manifest in library_dir.glob("*/manifest.json"):
        try:
            with open(existing_manifest, "r", encoding="utf-8") as file:
                payload = json.load(file) or {}
            for item in payload.get("images", []):
                file_hash = str(item.get("sha1", "")).strip()
                if file_hash:
                    known_hashes.add(file_hash)
        except Exception:
            continue

    topic_slug = "-".join(_infer_topic().lower().split())[:80] or "recovered-images"

    for index, group in enumerate(groups, start=1):
        unique_images = []
        for image in group:
            file_hash = _file_sha1(image)
            if file_hash in known_hashes:
                continue
            known_hashes.add(file_hash)
            unique_images.append((image, file_hash))

        if not unique_images:
            continue

        first_dt = datetime.fromtimestamp(unique_images[0][0].stat().st_mtime)
        folder_name = f"{first_dt.strftime('%Y%m%d-%H%M%S')}-recovered-{index:02d}-{topic_slug}"
        project_dir = library_dir / folder_name
        images_dir = project_dir / "images"
        os.makedirs(images_dir, exist_ok=True)

        manifest_images = []
        for image_path, file_hash in unique_images:
            target_path = images_dir / image_path.name
            if not target_path.exists():
                shutil.copy2(image_path, target_path)
            manifest_images.append(
                {
                    "filename": image_path.name,
                    "source_path": str(image_path),
                    "copied_path": str(target_path),
                    "sha1": file_hash,
                    "modified_at": datetime.fromtimestamp(image_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "prompt": None,
                    "prompt_status": "unknown_recovered",
                }
            )

        manifest = {
            "type": "recovered_image_batch",
            "topic": _infer_topic(),
            "topic_status": "inferred_from_youtube_account_niche",
            "prompt_status": "unknown_recovered",
            "project_dir": str(project_dir),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "images": manifest_images,
            "notes": [
                "Recovered from .mp and .mp/image_cache.",
                "Prompt metadata was not available for these older images.",
                "Future generated video projects store prompts and references automatically.",
            ],
        }

        with open(project_dir / "manifest.json", "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2, ensure_ascii=False)

        with open(project_dir / "references.txt", "w", encoding="utf-8") as file:
            file.write(
                f"topic: {_infer_topic()}\n"
                "topic_status: inferred_from_youtube_account_niche\n"
                "prompt_status: unknown_recovered\n"
                "notes: recovered from older cache without prompt metadata\n"
            )

        created_projects.append({
            "project_dir": str(project_dir),
            "image_count": len(manifest_images),
            "topic": _infer_topic(),
        })

    return {
        "projects_created": len(created_projects),
        "created_projects": created_projects,
        "library_dir": str(library_dir),
    }


def list_image_library_projects() -> list[dict]:
    library_dir = Path(get_image_library_dir())
    projects = []
    for project_dir in sorted([path for path in library_dir.iterdir() if path.is_dir()], reverse=True):
        manifest_path = project_dir / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as file:
                    manifest = json.load(file) or {}
            except Exception:
                manifest = {}
        projects.append(
            {
                "name": project_dir.name,
                "type": manifest.get("type", "unknown"),
                "topic": manifest.get("topic", ""),
                "image_count": len(manifest.get("images", [])),
                "project_dir": str(project_dir),
                "created_at": manifest.get("created_at", ""),
            }
        )
    return projects
