from app.core.supabase import supabase
from typing import List, Optional, Dict, Any

async def get_user_activity_feed(user_id: str, limit: int = 20, offset: int = 0, include_own_activity: bool = True) -> List[Dict[str, Any]]:
    """
    Get activity feed for a user:
    
    Args:
        user_id (str): The ID of the user whose activity feed is being requested.
        limit (int): The maximum number of activities to return. Defaults to 20.
        offset (int): The number of activities to skip before starting to collect the result set. Defaults to 0.
        include_own_activity (bool): Whether to include the user's own activities in the feed. Defaults to True.

    Returns:
        List[Dict[str, Any]]: A list of activities in the user's feed, enriched with additional data.
    """
    query = supabase.table("activities").select(
        "*, actor:profiles!activities_actor_id_fkey(*), posts(*)"
    ).order("created_at", desc=True).range(offset, offset + limit - 1)
    
    if include_own_activity:

        query = query.or_(f"user_id.eq.{user_id},actor_id.eq.{user_id}")
    else:
        query = query.eq("user_id", user_id)
    
    response = query.execute()
    
    if response.error:
        return []
    
    enriched_activities = []
    for activity in response.data:
        if activity.get("post_id") and activity.get("posts"):
            activity["post_data"] = activity.pop("posts")
        
        enriched_activities.append(activity)
    
    return enriched_activities

async def create_activity(user_id: str, actor_id: str, activity_type: str, post_id: Optional[str] = None, comment_id: Optional[str] = None, event_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new activity
    
    Args:
        user_id (str): The ID of the user for whom the activity is being created.
        actor_id (str): The ID of the actor performing the activity.
        activity_type (str): The type of activity being recorded (e.g., "post_create", "comment_create").
        post_id (Optional[str]): The ID of the post associated with the activity, if applicable.
        comment_id (Optional[str]): The ID of the comment associated with the activity, if applicable.
        event_id (Optional[str]): The ID of the event associated with the activity, if applicable.
        
    Returns:
        Dict[str, Any]: The created activity record, or an empty dictionary if the creation failed.
    """
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
