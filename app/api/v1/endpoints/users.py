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

class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    travel_style: Optional[str] = None
    interests: Optional[list[str]] = None

router = APIRouter()

@router.get("/me", response_model=User)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)) -> User:
    """
    Get current user's profile information
    
    Args:
        current_user (dict): The current authenticated user.
    
    Returns:
        User: The user profile information.
    """
    try:
        print(f"DEBUG: Looking for profile with user ID: {current_user['id']}")
        
        response = supabase.table("profiles").select("*").eq("id", current_user["id"]).execute()
        if not response.data:
            all_profiles = supabase.table("profiles").select("id, username").execute()
            print(f"DEBUG: All profiles in table: {all_profiles.data}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found for user ID: {current_user['id']}"
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
async def create_user_profile(profile_data: ProfileCreate, current_user: dict = Depends(get_current_user)) -> User:
    """
    Create user profile
    
    Args:
        profile_data (ProfileCreate): The profile data to create.
        current_user (dict): The current authenticated user.

    Returns:
        User: The created user profile.
    """
    try:
        existing_response = supabase.table("profiles").select("id").eq("id", current_user["id"]).execute()
        
        if existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already exists"
            )
        
        username_response = supabase.table("profiles").select("id").eq("username", profile_data.username).execute()
        
        if username_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
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

@router.put("/profile", response_model=User)
async def update_user_profile(profile_data: ProfileUpdate, current_user: dict = Depends(get_current_user)) -> User:
    """
    Update current user's profile
    
    Args:
        profile_data (ProfileUpdate): The profile data to update.
        current_user (dict): The current authenticated user.

    Returns:
        User: The updated user profile.
    """
    try:
        existing_response = supabase.table("profiles").select("*").eq("id", current_user["id"]).execute()
        
        if not existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        current_profile = existing_response.data[0]
        
        if profile_data.username and profile_data.username != current_profile["username"]:
            username_response = supabase.table("profiles").select("id").eq("username", profile_data.username).execute()
            
            if username_response.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        update_data = {}
        if profile_data.username is not None:
            update_data["username"] = profile_data.username
        if profile_data.full_name is not None:
            update_data["full_name"] = profile_data.full_name
        if profile_data.bio is not None:
            update_data["bio"] = profile_data.bio
        if profile_data.avatar_url is not None:
            update_data["avatar_url"] = profile_data.avatar_url
        if profile_data.location is not None:
            update_data["location"] = profile_data.location
        if profile_data.travel_style is not None:
            update_data["travel_style"] = profile_data.travel_style
        if profile_data.interests is not None:
            update_data["interests"] = profile_data.interests
        
        if not update_data:
            return User(
                id=current_profile["id"],
                username=current_profile["username"],
                full_name=current_profile.get("full_name"),
                bio=current_profile.get("bio"),
                avatar_url=current_profile.get("avatar_url"),
                location=current_profile.get("location"),
                travel_style=current_profile.get("travel_style"),
                interests=current_profile.get("interests", []),
                places_visited=current_profile.get("places_visited", 0),
                events_attended=current_profile.get("events_attended", 0),
                badges_earned=current_profile.get("badges_earned", 0),
                created_at=current_profile["created_at"],
                updated_at=current_profile["updated_at"]
            )
        
        response = supabase.table("profiles").update(update_data).eq("id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )
        
        updated_profile = response.data[0]
        
        return User(
            id=updated_profile["id"],
            username=updated_profile["username"],
            full_name=updated_profile.get("full_name"),
            bio=updated_profile.get("bio"),
            avatar_url=updated_profile.get("avatar_url"),
            location=updated_profile.get("location"),
            travel_style=updated_profile.get("travel_style"),
            interests=updated_profile.get("interests", []),
            places_visited=updated_profile.get("places_visited", 0),
            events_attended=updated_profile.get("events_attended", 0),
            badges_earned=updated_profile.get("badges_earned", 0),
            created_at=updated_profile["created_at"],
            updated_at=updated_profile["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.get("/{user_id}", response_model=User)
async def get_user_profile(user_id: str) -> User:
    """
    Get specific user's profile information
    
    Args:
        user_id (str): The ID of the user whose profile to fetch.
        
    Returns:
        User: The user profile information.
    """
    try:
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