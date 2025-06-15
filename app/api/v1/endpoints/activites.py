from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any
from app.core.security import get_current_user
from app.services.activity_service import get_user_activity_feed

router = APIRouter()

@router.get("/feed", response_model=List[Dict[str, Any]])
async def get_activity_feed(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), include_own_activity: bool = Query(True), current_user: dict = Depends(get_current_user)):
    """
    Get the activity feed for the current user.

    Args:
        limit (int): The maximum number of activities to return. Defaults to 20, max 100.
        offset (int): The number of activities to skip before starting to collect the result set. Defaults to 0.
        include_own_activity (bool): Whether to include the user's own activities in the feed. Defaults to True.
        current_user (dict): The current authenticated user.

    Returns:
        List[Dict[str, Any]]: A list of activities in the user's feed.
    """
    activities = await get_user_activity_feed(
        user_id=current_user["id"],
        limit=limit,
        offset=offset,
        include_own_activity=include_own_activity
    )
    
    return activities

