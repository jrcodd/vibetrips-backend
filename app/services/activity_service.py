from app.core.supabase import supabase
from typing import List, Optional, Dict, Any

async def get_user_activity_feed(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    include_own_activity: bool = True
) -> List[Dict[str, Any]]:
    """
    Get activity feed for a user including:
    - Activities from users they follow
    - Optional: Their own activities
    """
    query = supabase.table("activities").select(
        "*, actor:profiles!activities_actor_id_fkey(*), posts(*)"
    ).order("created_at", desc=True).range(offset, offset + limit - 1)
    
    # Build query for activity feed
    if include_own_activity:
        # Include activities where the user is either the recipient or the actor
        query = query.or_(f"user_id.eq.{user_id},actor_id.eq.{user_id}")
    else:
        # Only include activities where the user is the recipient
        query = query.eq("user_id", user_id)
    
    # Execute query
    response = query.execute()
    
    if response.error:
        return []
    
    # Process and enrich activities
    enriched_activities = []
    for activity in response.data:
        # Enrich with additional data based on activity type
        if activity.get("post_id") and activity.get("posts"):
            activity["post_data"] = activity.pop("posts")
        
        # Add to result list
        enriched_activities.append(activity)
    
    return enriched_activities

async def create_activity(
    user_id: str,
    actor_id: str,
    activity_type: str,
    post_id: Optional[str] = None,
    comment_id: Optional[str] = None,
    event_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new activity"""
    activity_data = {
        "user_id": user_id,
        "actor_id": actor_id,
        "activity_type": activity_type
    }
    
    if post_id:
        activity_data["post_id"] = post_id
        
    if comment_id:
        activity_data["comment_id"] = comment_id
        
    if event_id:
        activity_data["event_id"] = event_id
    
    response = supabase.table("activities").insert(activity_data).execute()
    
    if response.error:
        return {}
    
    return response.data[0] if response.data else {}
