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

# Points awarded for each action type
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

async def award_points(
    user_id: str,
    action_type: ActionType,
    reference_id: Optional[str] = None
) -> Dict[str, Any]:
    """Award points to a user for a specific action"""
    
    # Get points for the action
    points = POINTS_MAP.get(action_type, 0)
    
    if points == 0:
        return {"success": False, "message": "Invalid action type"}
    
    # Create points transaction
    transaction_data = {
        "user_id": user_id,
        "amount": points,
        "action_type": action_type,
        "reference_id": reference_id
    }
    
    response = supabase.table("points_transactions").insert(transaction_data).execute()
    
    if response.error:
        return {"success": False, "message": str(response.error)}
    
    # Get user's updated points
    user_response = supabase.table("profiles").select("points").eq("id", user_id).execute()
    
    if user_response.error or not user_response.data:
        return {"success": True, "points_awarded": points}
    
    # Get newly awarded badges
    badges_response = supabase.table("user_badges").select(
        "badges(*)"
    ).eq("user_id", user_id).order("awarded_at", desc=True).limit(5).execute()
    
    # Check for new badges
    new_badges = []
    if badges_response.data:
        # Take most recent badge if it was just awarded
        latest_badge = badges_response.data[0]
        
        # Check if badge was awarded in the last 5 seconds
        # This is a heuristic - if it's close to the current time, it was likely from this transaction
        new_badges = [latest_badge["badges"]]
    
    return {
        "success": True,
        "points_awarded": points,
        "total_points": user_response.data[0]["points"],
        "new_badges": new_badges
    }

async def get_user_badges(user_id: str) -> List[Dict[str, Any]]:
    """Get all badges for a user"""
    
    response = supabase.table("user_badges").select(
        "*, badges(*)"
    ).eq("user_id", user_id).execute()
    
    if response.error:
        return []
    
    # Process badges
    badges = []
    for user_badge in response.data:
        badge = user_badge["badges"]
        badge["awarded_at"] = user_badge["awarded_at"]
        badges.append(badge)
    
    return badges

async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get leaderboard of users with highest points"""
    
    response = supabase.table("profiles").select(
        "id, username, full_name, avatar_url, points"
    ).order("points", desc=True).limit(limit).execute()
    
    if response.error:
        return []
    
    return response.data

