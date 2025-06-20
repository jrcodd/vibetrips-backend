from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.core.supabase import supabase
from app.core.security import get_current_user
from app.schemas.social import FollowCreate, Follow, FollowRequestCreate
from app.schemas.user import User
import uuid
from datetime import datetime

router = APIRouter()

@router.post("/request", response_model=Follow)
async def create_follow_request(
    follow_request_data: FollowRequestCreate, 
    current_user: dict = Depends(get_current_user)
) -> Follow:
    """
    Create a follow request

    Args:
        follow_request_data (FollowRequestCreate): The data required to request following a user.
        current_user (dict): The current authenticated user.

    Returns:
        Follow: The created follow request.
    """
    if current_user["id"] == follow_request_data.following_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself"
        )
    
    # Check if already following or requested
    check_response = supabase.table("follow_requests").select("*").eq(
        "requester_id", current_user["id"]
    ).eq("following_id", follow_request_data.following_id).execute()
    
    if check_response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already requested to follow this user"
        )

    # Check if already following
    follow_check = supabase.table("follows").select("*").eq(
        "follower_id", current_user["id"]
    ).eq("following_id", follow_request_data.following_id).execute()

    if follow_check.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already following this user"
        )
    
    follow_request_id = str(uuid.uuid4())
    follow_request_data_dict = {
        "id": follow_request_id,
        "requester_id": current_user["id"],
        "following_id": follow_request_data.following_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    
    response = supabase.table("follow_requests").insert(follow_request_data_dict).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create follow request"
        )
    
    # Create activity for the notification
    activity_data = {
        "user_id": follow_request_data.following_id,
        "actor_id": current_user["id"],
        "activity_type": "follow_request"
    }
    
    supabase.table("activities").insert(activity_data).execute()
    
    return Follow(**response.data[0])

@router.delete("/request/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_follow_request(
    user_id: str, 
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Cancel a follow request

    Args:
        user_id (str): The ID of the user to cancel the follow request to.
        current_user (dict): The current authenticated user.
        
    Returns:
        dict: A message indicating the success of the cancellation.
    """
    
    response = supabase.table("follow_requests").delete().eq(
        "requester_id", current_user["id"]
    ).eq("following_id", user_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow request not found"
        )
    
    return {"message": "Follow request cancelled"}

@router.post("/request/{user_id}/accept", status_code=status.HTTP_200_OK)
async def accept_follow_request(
    user_id: str, 
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Accept a follow request

    Args:
        user_id (str): The ID of the user whose follow request to accept.
        current_user (dict): The current authenticated user.
        
    Returns:
        dict: A message indicating the success of the acceptance.
    """
    
    # Find the specific follow request
    request_response = supabase.table("follow_requests").select("*").eq(
        "requester_id", user_id
    ).eq("following_id", current_user["id"]).eq("status", "pending").execute()
    
    if not request_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow request not found"
        )
    
    # Create follow relationship
    follow_id = str(uuid.uuid4())
    follow_data_dict = {
        "id": follow_id,
        "follower_id": user_id,
        "following_id": current_user["id"],
        "created_at": datetime.utcnow().isoformat()
    }
    
    follow_response = supabase.table("follows").insert(follow_data_dict).execute()
    
    if not follow_response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to accept follow request"
        )
    
    # Update follow request status
    supabase.table("follow_requests").update({
        "status": "accepted"
    }).eq(
        "requester_id", user_id
    ).eq("following_id", current_user["id"]).execute()
    
    # Create activity for the notification
    activity_data = {
        "user_id": user_id,
        "actor_id": current_user["id"],
        "activity_type": "follow_request_accepted"
    }
    
    supabase.table("activities").insert(activity_data).execute()
    
    return {"message": "Follow request accepted"}

@router.post("/request/{user_id}/ignore", status_code=status.HTTP_200_OK)
async def ignore_follow_request(
    user_id: str, 
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Ignore a follow request

    Args:
        user_id (str): The ID of the user whose follow request to ignore.
        current_user (dict): The current authenticated user.
        
    Returns:
        dict: A message indicating the success of the ignore action.
    """
    
    # Find and delete the specific follow request
    response = supabase.table("follow_requests").delete().eq(
        "requester_id", user_id
    ).eq("following_id", current_user["id"]).eq("status", "pending").execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow request not found"
        )
    
    return {"message": "Follow request ignored"}

@router.get("/requests", response_model=List[User])
async def get_follow_requests(
    current_user: dict = Depends(get_current_user)
) -> List[User]:
    """
    Get incoming follow requests for the current user

    Args:
        current_user (dict): The current authenticated user.
        
    Returns:
        List[User]: A list of users who have requested to follow the current user.
    """
    
    response = supabase.table("follow_requests").select(
        "profiles!requester_id(*)"
    ).eq("following_id", current_user["id"]).eq("status", "pending").execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    requests = [item["profiles"] for item in response.data]
    return requests

@router.get("/recommended", response_model=List[User])
async def get_recommended_users(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50)
) -> List[User]:
    """
    Get recommended users to follow

    Args:
        current_user (dict): The current authenticated user.
        limit (int): Maximum number of recommended users to return.
        
    Returns:
        List[User]: A list of recommended users to follow.
    """
    
    # Fetch users who are active (e.g., have made posts recently)
    # This is a simplified recommendation logic. In a real-world scenario, 
    # you'd use more sophisticated recommendation algorithms
    recommended_query = supabase.from_("profiles").select("*").neq(
        "id", current_user["id"]
    ).order("posts_count", ascending=False).limit(limit).execute()
    
    if recommended_query.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(recommended_query.error)
        )
    
    # Filter out users already following or requested
    following_query = supabase.table("follows").select("following_id").eq(
        "follower_id", current_user["id"]
    ).execute()
    
    requested_query = supabase.table("follow_requests").select("following_id").eq(
        "requester_id", current_user["id"]
    ).execute()
    
    following_ids = set(item["following_id"] for item in following_query.data or [])
    requested_ids = set(item["following_id"] for item in requested_query.data or [])
    
    recommended_users = [
        user for user in recommended_query.data 
        if user["id"] not in following_ids and user["id"] not in requested_ids
    ]
    
    return recommended_users

@router.get("/status/{user_id}", response_model=str)
async def get_follow_status(
    user_id: str,
    current_user: dict = Depends(get_current_user)
) -> str:
    """
    Get the follow status between the current user and another user

    Args:
        user_id (str): The ID of the user to check follow status with.
        current_user (dict): The current authenticated user.
        
    Returns:
        str: The follow status ('following', 'requested', or 'not_following').
    """
    
    # Check if already following
    follow_query = supabase.table("follows").select("*").eq(
        "follower_id", current_user["id"]
    ).eq("following_id", user_id).execute()
    
    if follow_query.data:
        return "following"
    
    # Check if a follow request exists
    request_query = supabase.table("follow_requests").select("*").eq(
        "requester_id", current_user["id"]
    ).eq("following_id", user_id).eq("status", "pending").execute()
    
    if request_query.data:
        return "requested"
    
    return "not_following"