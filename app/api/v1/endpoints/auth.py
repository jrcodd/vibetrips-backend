from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from app.schemas.user import UserCreate, UserLogin, Token, User
from app.core.security import create_access_token, get_current_user
from app.core.config import settings
from app.core.supabase import supabase
from gotrue.errors import AuthApiError

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    """Register a new user"""
    try:
        # Create user in Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {
                    "username": user.username,
                    "full_name": user.full_name or ""
                }
            }
        })
        
        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )
        
        # Get created profile
        profile_response = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
        
        if not profile_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile creation failed"
            )
        
        profile = profile_response.data[0]
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(auth_response.user.id)},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": User(**profile)
        }
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Login user"""
    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if auth_response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Get user profile
        profile_response = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
        
        if not profile_response.data:
            # Create profile if it doesn't exist
            user_metadata = auth_response.user.user_metadata or {}
            base_username = user_metadata.get("username", auth_response.user.email.split("@")[0])
            full_name = user_metadata.get("full_name", "")
            
            # Ensure username is unique
            username = base_username
            counter = 1
            while True:
                existing_user = supabase.table("profiles").select("id").eq("username", username).execute()
                if not existing_user.data:
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            profile_data = {
                "id": str(auth_response.user.id),
                "username": username,
                "full_name": full_name,
                "bio": None,
                "avatar_url": None,
                "location": None,
                "travel_style": None,
                "interests": [],
                "places_visited": 0,
                "events_attended": 0,
                "badges_earned": 0
            }
            
            create_response = supabase.table("profiles").insert(profile_data).execute()
            
            if not create_response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
            
            profile = create_response.data[0]
        else:
            profile = profile_response.data[0]
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": str(auth_response.user.id)},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": User(**profile)
        }
        
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    # Fetch the actual profile data
    response = supabase.table("profiles").select("*").eq("id", current_user["id"]).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    profile_data = response.data[0]
    return User(**profile_data)
