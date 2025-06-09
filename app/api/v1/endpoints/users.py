from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from app.schemas.user import User
from app.core.security import get_current_user
from app.core.supabase import supabase

router = APIRouter()

@router.get("/me", response_model=User)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile information"""
    try:
        # Fetch profile data from Supabase
        response = supabase.table("profiles").select("*").eq("id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        profile_data = response.data[0]
        
        return User(
            id=profile_data["id"],
            username=profile_data["username"],
            full_name=profile_data.get("full_name"),
            bio=profile_data.get("bio"),
            avatar_url=profile_data.get("avatar_url"),
            location=profile_data.get("location"),
            travel_style=profile_data.get("travel_style"),
            interests=profile_data.get("interests", []),
            places_visited=profile_data.get("places_visited", 0),
            events_attended=profile_data.get("events_attended", 0),
            badges_earned=profile_data.get("badges_earned", 0),
            created_at=profile_data["created_at"],
            updated_at=profile_data["updated_at"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )

@router.get("/{user_id}", response_model=User)
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get specific user's profile information"""
    try:
        # Fetch profile data from Supabase
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        profile_data = response.data[0]
        
        return User(
            id=profile_data["id"],
            username=profile_data["username"],
            full_name=profile_data.get("full_name"),
            bio=profile_data.get("bio"),
            avatar_url=profile_data.get("avatar_url"),
            location=profile_data.get("location"),
            travel_style=profile_data.get("travel_style"),
            interests=profile_data.get("interests", []),
            places_visited=profile_data.get("places_visited", 0),
            events_attended=profile_data.get("events_attended", 0),
            badges_earned=profile_data.get("badges_earned", 0),
            created_at=profile_data["created_at"],
            updated_at=profile_data["updated_at"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )