"""Public mobile app version / OTA metadata."""

from fastapi import APIRouter, Depends, HTTPException, Query

from config.database import get_database
from services import app_release_service

router = APIRouter(prefix="/app", tags=["App"])


@router.get("/version")
async def get_app_version(
    platform: str = Query(default="android"),
    current_version: str = Query(default="0.0.0"),
    current_build: int | None = Query(default=None),
    db=Depends(get_database),
):
    """
    Check whether a newer APK is available (no app store).

    Mobile clients send installed version/build; response includes apk_url when
    an update is published and enabled in the admin dashboard.
    """
    if platform not in ("android",):
        raise HTTPException(status_code=400, detail="Unsupported platform.")

    release = await app_release_service.get_release(db, platform)
    return app_release_service.evaluate_update(
        release,
        current_version=current_version,
        current_build=current_build,
    )
