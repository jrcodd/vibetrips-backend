from app.core.supabase import supabase
from enum import Enum
from typing import Dict, List, Any, Optional

class ActionType(str, Enum):
    POST_CREATE = "post_create"
    POST_LIKE = "post_like"
    COMMENT_CREATE = "comment_create"
    FOLLOW = "follow"
    EVENT_CREATE = "event_create"
    EVENT_JOIN = "event_join"
    DAILY_LOGIN = "daily_login"
    PROFILE_COMPLETE = "profile_complete"
    LOCATION_VISIT = "location_visit"

POINTS_MAP = {
    ActionType.POST_CREATE: 10,
    ActionType.POST_LIKE: 2,
    ActionType.COMMENT_CREATE: 5,
    ActionType.FOLLOW: 3,
    ActionType.EVENT_CREATE: 15,
    ActionType.EVENT_JOIN: 7,
    ActionType.DAILY_LOGIN: 1,
    ActionType.PROFILE_COMPLETE: 20,
    ActionType.LOCATION_VISIT: 5
}

async def award_points(user_id: str, action_type: ActionType, reference_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Award points to a user for a specific action
    
    Args:
        user_id (str): The ID of the user to award points to.
        action_type (ActionType): The type of action that triggered the points award.
        reference_id (Optional[str]): An optional reference ID for the action, e.g., post ID, comment ID, etc.
    
    Returns:
        Dict[str, Any]: A dictionary containing the success status, points awarded, total points, and any new badges awarded.
    """

    points = POINTS_MAP.get(action_type, 0)
    
    if points == 0:
        return {"success": False, "message": "Invalid action type"}
    
    transaction_data = {
        "user_id": user_id,
        "amount": points,
        "action_type": action_type,
        "reference_id": reference_id
    }
    
    response = supabase.table("points_transactions").insert(transaction_data).execute()
    
    if response.error:
        return {"success": False, "message": str(response.error)}
    
    user_response = supabase.table("profiles").select("points").eq("id", user_id).execute()
    
    if user_response.error or not user_response.data:
        return {"success": True, "points_awarded": points}
    
    badges_response = supabase.table("user_badges").select(
        "badges(*)"
    ).eq("user_id", user_id).order("awarded_at", desc=True).limit(5).execute()
    
    new_badges = []
    if badges_response.data:
        latest_badge = badges_response.data[0]
        new_badges = [latest_badge["badges"]]
    
    return {
        "success": True,
        "points_awarded": points,
        "total_points": user_response.data[0]["points"],
        "new_badges": new_badges
    }

async def get_user_badges(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all badges for a user
    
    Args:
        user_id (str): The ID of the user to get badges for.

    Returns:
        List[Dict[str, Any]]: A list of badges earned by the user, including when they were awarded.
    """
    
    response = supabase.table("user_badges").select(
        "*, badges(*)"
    ).eq("user_id", user_id).execute()
    
    if response.error:
        return []
    
    badges = []
    for user_badge in response.data:
        badge = user_badge["badges"]
        badge["awarded_at"] = user_badge["awarded_at"]
        badges.append(badge)
    
    return badges

async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get leaderboard of users with highest points

    Args:
        limit (int): The maximum number of users to return in the leaderboard. Defaults to 10, max 100.
    
    Returns:
        List[Dict[str, Any]]: A list of users with their points, ordered by points descending.
    """

    response = supabase.table("profiles").select(
        "id, username, full_name, avatar_url, points"
    ).order("points", desc=True).limit(limit).execute()
    
    if response.error:
        return []
    
    return response.data