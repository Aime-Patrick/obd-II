"""Mobile app OTA release metadata (Android APK, no app store)."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any, BinaryIO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASES_DIR = os.path.join(BASE_DIR, "releases")
MAX_APK_BYTES = 150 * 1024 * 1024
APK_MAGIC = b"PK\x03\x04"

SETTINGS_ID = "app_release_android"
DEFAULT_PLATFORM = "android"


def _defaults() -> dict[str, Any]:
    return {
        "platform": DEFAULT_PLATFORM,
        "latest_version": "1.0.0",
        "min_version": "1.0.0",
        "build_number": 1,
        "apk_url": "",
        "release_notes": "",
        "force_update": False,
        "enabled": False,
        "updated_at": None,
    }


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in (version or "0").strip().split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or (0,))


def compare_versions(left: str, right: str) -> int:
    """Return -1 if left < right, 0 if equal, 1 if left > right."""
    a = _parse_version(left)
    b = _parse_version(right)
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


async def get_release(db, platform: str = DEFAULT_PLATFORM) -> dict[str, Any]:
    doc_id = SETTINGS_ID if platform == DEFAULT_PLATFORM else f"app_release_{platform}"
    doc = await db.system_settings.find_one({"_id": doc_id})
    merged = _defaults()
    if doc:
        merged.update(
            {
                "platform": doc.get("platform", merged["platform"]),
                "latest_version": doc.get("latest_version", merged["latest_version"]),
                "min_version": doc.get("min_version", merged["min_version"]),
                "build_number": int(doc.get("build_number", merged["build_number"])),
                "apk_url": doc.get("apk_url", ""),
                "release_notes": doc.get("release_notes", ""),
                "force_update": bool(doc.get("force_update", False)),
                "enabled": bool(doc.get("enabled", False)),
                "updated_at": doc.get("updated_at"),
            }
        )
    return merged


async def update_release(
    db,
    *,
    latest_version: str,
    min_version: str,
    build_number: int,
    apk_url: str,
    release_notes: str,
    force_update: bool,
    enabled: bool,
    platform: str = DEFAULT_PLATFORM,
    updated_by: str | None = None,
) -> dict[str, Any]:
    if compare_versions(min_version, latest_version) > 0:
        raise ValueError("min_version cannot be greater than latest_version.")

    doc_id = SETTINGS_ID if platform == DEFAULT_PLATFORM else f"app_release_{platform}"
    now = datetime.now(timezone.utc)
    payload = {
        "_id": doc_id,
        "platform": platform,
        "latest_version": latest_version.strip(),
        "min_version": min_version.strip(),
        "build_number": build_number,
        "apk_url": apk_url.strip(),
        "release_notes": release_notes.strip(),
        "force_update": force_update,
        "enabled": enabled,
        "updated_at": now,
        "updated_by": updated_by,
    }
    await db.system_settings.update_one({"_id": doc_id}, {"$set": payload}, upsert=True)
    return await get_release(db, platform)


def evaluate_update(
    release: dict[str, Any],
    *,
    current_version: str,
    current_build: int | None = None,
) -> dict[str, Any]:
    """Build public response including whether the client should update."""
    enabled = bool(release.get("enabled")) and bool(release.get("apk_url"))
    latest = release.get("latest_version", "0.0.0")
    minimum = release.get("min_version", "0.0.0")
    latest_build = int(release.get("build_number") or 0)

    version_behind = compare_versions(current_version, latest) < 0
    build_behind = False
    if current_build is not None and compare_versions(current_version, latest) == 0:
        build_behind = current_build < latest_build

    update_available = enabled and (version_behind or build_behind)
    force_update = enabled and (
        release.get("force_update")
        or compare_versions(current_version, minimum) < 0
    )

    return {
        "platform": release.get("platform", DEFAULT_PLATFORM),
        "latest_version": latest,
        "min_version": minimum,
        "build_number": latest_build,
        "apk_url": release.get("apk_url", "") if enabled else "",
        "release_notes": release.get("release_notes", ""),
        "force_update": bool(force_update),
        "update_available": bool(update_available),
        "current_version": current_version,
        "current_build": current_build,
    }


def releases_dir() -> str:
    os.makedirs(RELEASES_DIR, exist_ok=True)
    return RELEASES_DIR


def safe_apk_filename(version: str, build_number: int) -> str:
    safe_v = re.sub(r"[^0-9a-zA-Z._-]", "", (version or "").strip()) or "0.0.0"
    return f"smartdrivex-{safe_v}-b{int(build_number)}.apk"


def build_public_apk_url(base_url: str, filename: str) -> str:
    return f"{base_url.rstrip('/')}/releases/{filename}"


def is_valid_public_apk_url(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://localhost") or url.startswith(
        "http://127.0.0.1"
    )


def save_uploaded_apk(file_obj: BinaryIO, filename: str) -> dict[str, Any]:
    """Stream APK to releases/ with size limit and SHA-256."""
    if not filename.lower().endswith(".apk"):
        raise ValueError("Only .apk files are allowed.")

    releases_dir()
    dest = os.path.join(RELEASES_DIR, filename)
    tmp = dest + ".uploading"

    sha = hashlib.sha256()
    size = 0
    validated_magic = False

    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                if not validated_magic:
                    if not chunk.startswith(APK_MAGIC):
                        raise ValueError("File is not a valid APK (ZIP archive).")
                    validated_magic = True
                size += len(chunk)
                if size > MAX_APK_BYTES:
                    raise ValueError(
                        f"APK exceeds maximum size of {MAX_APK_BYTES // (1024 * 1024)} MB."
                    )
                sha.update(chunk)
                out.write(chunk)

        if size == 0:
            raise ValueError("Uploaded file is empty.")

        os.replace(tmp, dest)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

    return {
        "filename": filename,
        "size_bytes": size,
        "sha256": sha.hexdigest(),
        "path": dest,
    }


async def ensure_defaults(db) -> None:
    doc_id = SETTINGS_ID
    exists = await db.system_settings.find_one({"_id": doc_id}, {"_id": 1})
    if not exists:
        payload = _defaults()
        payload["_id"] = doc_id
        await db.system_settings.insert_one(payload)
