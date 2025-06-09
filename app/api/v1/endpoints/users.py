from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from app.schemas.user import User
from app.core.security import get_current_user
from app.core.supabase import supabase
from pydantic import BaseModel

class ProfileCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    travel_style: Optional[str] = None
    interests: list[str] = []

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
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )

@router.post("/profile", response_model=User)
async def create_user_profile(profile_data: ProfileCreate, current_user: dict = Depends(get_current_user)):
    """Create user profile"""
    try:
        # Check if profile already exists
        existing_response = supabase.table("profiles").select("id").eq("id", current_user["id"]).execute()
        
        if existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already exists"
            )
        
        # Check if username is already taken
        username_response = supabase.table("profiles").select("id").eq("username", profile_data.username).execute()
        
        if username_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create profile
        new_profile = {
            "id": current_user["id"],
            "username": profile_data.username,
            "full_name": profile_data.full_name,
            "bio": profile_data.bio,
            "avatar_url": profile_data.avatar_url,
            "location": profile_data.location,
            "travel_style": profile_data.travel_style,
            "interests": profile_data.interests,
            "places_visited": 0,
            "events_attended": 0,
            "badges_earned": 0
        }
        
        response = supabase.table("profiles").insert(new_profile).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create profile"
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
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