from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from app.core.supabase import supabase
from app.core.security import get_current_user
from app.schemas.social import FollowCreate, Follow
from app.schemas.user import User
import uuid

router = APIRouter()

@router.post("/", response_model=Follow)
async def follow_user(follow_data: FollowCreate, current_user: dict = Depends(get_current_user)) -> Follow:
    """
    Follow a user

    Args:
        follow_data (FollowCreate): The data required to follow a user, including the ID of the user to follow.
        current_user (dict): The current authenticated user.

    Returns:
        Follow: The created follow relationship.
    """

    if current_user["id"] == follow_data.following_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself"
        )
    
    check_response = supabase.table("follows").select("*").eq(
        "follower_id", current_user["id"]
    ).eq("following_id", follow_data.following_id).execute()
    
    if check_response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already following this user"
        )
    
    follow_id = str(uuid.uuid4())
    follow_data_dict = {
        "id": follow_id,
        "follower_id": current_user["id"],
        "following_id": follow_data.following_id
    }
    
    response = supabase.table("follows").insert(follow_data_dict).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to follow user"
        )
    
    activity_data = {
        "user_id": follow_data.following_id,
        "actor_id": current_user["id"],
        "activity_type": "follow"
    }
    
    supabase.table("activities").insert(activity_data).execute()
    
    return Follow(**response.data[0])

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def unfollow_user(user_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """
    Unfollow a user
    
    Args:
        user_id (str): The ID of the user to unfollow.
        current_user (dict): The current authenticated user.
        
    Returns:
        dict: A message indicating the success of the unfollow action.
    """
    
    response = supabase.table("follows").delete().eq(
        "follower_id", current_user["id"]
    ).eq("following_id", user_id).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow relationship not found"
        )

@router.get("/followers", response_model=List[User])
async def get_followers(user_id: Optional[str] = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), current_user: dict = Depends(get_current_user)):
    """
    Get user followers
    
    Args:
        user_id (Optional[str]): The ID of the user whose followers to retrieve. If not provided, uses the current user's ID.
        limit (int): The maximum number of followers to return. Defaults to 20, max 100.
        offset (int): The number of followers to skip before starting to collect the result set. Defaults to 0.
        current_user (dict): The current authenticated user.
        
    Returns:
        List[User]: A list of users who are following the specified user.
    """
    target_id = user_id or current_user["id"]
    
    response = supabase.from_("follows").select(
        "profiles!follower_id(*)"
    ).eq("following_id", target_id).range(offset, offset + limit - 1).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    followers = [item["profiles"] for item in response.data]
    return followers

@router.get("/following", response_model=List[User])
async def get_following(
    user_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get users that a user is following"""
    target_id = user_id or current_user["id"]
    
    response = supabase.from_("follows").select(
        "profiles!following_id(*)"
    ).eq("follower_id", target_id).range(offset, offset + limit - 1).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    following = [item["profiles"] for item in response.data]
    return following
