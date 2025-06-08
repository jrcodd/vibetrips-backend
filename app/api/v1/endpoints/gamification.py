from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Dict, Any
from app.core.security import get_current_user
from app.services.gamification_service import (
    get_user_badges, 
    get_leaderboard,
    award_points,
    ActionType
)

router = APIRouter()

@router.get("/badges", response_model=List[Dict[str, Any]])
async def get_badges(
    user_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get badges for a user"""
    target_id = user_id or current_user["id"]
    badges = await get_user_badges(target_id)
    return badges

@router.get("/leaderboard", response_model=List[Dict[str, Any]])
async def get_points_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get points leaderboard"""
    leaderboard = await get_leaderboard(limit)
    return leaderboard

@router.post("/check-in", response_model=Dict[str, Any])
async def daily_check_in(
    current_user: dict = Depends(get_current_user)
):
    """Daily check-in to earn points"""
    result = await award_points(
        user_id=current_user["id"],
        action_type=ActionType.DAILY_LOGIN
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

