from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="VibeTrip API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not all([supabase_url, supabase_key]):
    raise ValueError("Missing Supabase configuration")

supabase: Client = create_client(supabase_url, supabase_key)
supabase_admin: Client = create_client(supabase_url, supabase_service_key)

# Security
security = HTTPBearer()

# Pydantic models
class UserProfile(BaseModel):
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    travel_style: Optional[str] = None
    interests: Optional[List[str]] = []

class PostCreate(BaseModel):
    content: str
    image_url: Optional[str] = None
    place_id: Optional[str] = None
    post_type: str = "story"

class PostResponse(BaseModel):
    id: str
    content: str
    image_url: Optional[str]
    post_type: str
    likes_count: int
    saves_count: int
    created_at: datetime
    user: Dict[str, Any]
    place: Optional[Dict[str, Any]] = None

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    event_date: datetime
    location: str
    category: str
    price: Optional[str] = None
    max_attendees: Optional[int] = None

class PlaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[str] = None
    is_hidden: bool = False

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        if not user.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return {"user": user.user, "token": token}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "VibeTrip API"}

# User Profile endpoints
@app.post("/api/profile")
async def create_profile(profile: UserProfile, current_user = Depends(get_current_user)):
    try:
        user = current_user["user"]
        
        # Check if profile already exists using admin client
        existing = supabase_admin.table("profiles").select("*").eq("id", user.id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Profile already exists")
        
        profile_data = {
            "id": user.id,
            **profile.dict()
        }
        
        result = supabase_admin.table("profiles").insert(profile_data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create profile")
        return {"message": "Profile created successfully", "profile": result.data[0]}
    except HTTPException:
        # Re-raise HTTPExceptions to preserve status codes
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")

@app.get("/api/profile")
async def get_profile(current_user = Depends(get_current_user)):
    try:
        user = current_user["user"]
        
        # Use admin client to query profiles directly, bypassing RLS for this specific case
        result = supabase_admin.table("profiles").select("*").eq("id", user.id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return result.data[0]
    except HTTPException:
        # Re-raise HTTPExceptions to preserve status codes
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/profile")
async def update_profile(profile: UserProfile, current_user = Depends(get_current_user)):
    try:
        user = current_user["user"]
        
        result = supabase_admin.table("profiles").update(profile.dict(exclude_unset=True)).eq("id", user.id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"message": "Profile updated successfully", "profile": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/profiles/{user_id}")
async def get_user_profile(user_id: str, current_user = Depends(get_current_user)):
    try:
        # Use admin client for profile lookups
        result = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Posts endpoints
@app.post("/api/posts")
async def create_post(post: PostCreate, current_user = Depends(get_current_user)):
    try:
        user = current_user["user"]
        post_data = {
            "user_id": user.id,
            **post.dict()
        }
        
        result = supabase.table("posts").insert(post_data).execute()
        return {"message": "Post created successfully", "post": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/posts")
async def get_posts(limit: int = 20, offset: int = 0, current_user = Depends(get_current_user)):
    try:
        result = supabase.table("posts").select("""
            *,
            profiles:user_id (
                id,
                username,
                full_name,
                avatar_url
            ),
            places:place_id (
                id,
                name,
                location,
                category
            )
        """).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {"posts": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/posts/{post_id}")
async def get_post(post_id: str, current_user = Depends(get_current_user)):
    try:
        result = supabase.table("posts").select("""
            *,
            profiles:user_id (
                id,
                username,
                full_name,
                avatar_url
            ),
            places:place_id (
                id,
                name,
                location,
                category
            )
        """).eq("id", post_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Post not found")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/posts/{post_id}/like")
async def like_post(post_id: str, current_user = Depends(get_current_user)):
    try:
        # Check if already liked
        existing = supabase.table("post_likes").select("*").eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
        
        if existing.data:
            # Unlike
            supabase.table("post_likes").delete().eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
            return {"message": "Post unliked", "liked": False}
        else:
            # Like
            supabase.table("post_likes").insert({"user_id": current_user["user"].id, "post_id": post_id}).execute()
            return {"message": "Post liked", "liked": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/posts/{post_id}/save")
async def save_post(post_id: str, current_user = Depends(get_current_user)):
    try:
        # Check if already saved
        existing = supabase.table("post_saves").select("*").eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
        
        if existing.data:
            # Unsave
            supabase.table("post_saves").delete().eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
            return {"message": "Post unsaved", "saved": False}
        else:
            # Save
            supabase.table("post_saves").insert({"user_id": current_user["user"].id, "post_id": post_id}).execute()
            return {"message": "Post saved", "saved": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Places endpoints
@app.post("/api/places")
async def create_place(place: PlaceCreate, current_user = Depends(get_current_user)):
    try:
        place_data = {
            "created_by": current_user["user"].id,
            **place.dict()
        }
        
        result = supabase.table("places").insert(place_data).execute()
        return {"message": "Place created successfully", "place": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/places")
async def get_places(category: Optional[str] = None, hidden: Optional[bool] = None, current_user = Depends(get_current_user)):
    try:
        query = supabase.table("places").select("*")
        
        if category:
            query = query.eq("category", category)
        if hidden is not None:
            query = query.eq("is_hidden", hidden)
            
        result = query.order("created_at", desc=True).execute()
        return {"places": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Events endpoints
@app.post("/api/events")
async def create_event(event: EventCreate, current_user = Depends(get_current_user)):
    try:
        # Get the current user's username from the profile
        user_profile = supabase_admin.table("profiles").select("username").eq("id", current_user["user"].id).execute()
        
        if not user_profile.data:
            raise HTTPException(status_code=400, detail="User profile not found")
        
        organizer_username = user_profile.data[0]["username"]
        
        event_data = {
            "organizer_id": current_user["user"].id,  # Keep for backward compatibility
            "organizer_username": organizer_username,
            **event.dict()
        }
        
        result = supabase_admin.table("events").insert(event_data).execute()
        return {"message": "Event created successfully", "event": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/events")
async def get_events(category: Optional[str] = None, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["user"].id
        
        # Use admin client to bypass RLS for events (events should be publicly viewable)
        events_result = supabase_admin.table("events").select("*")
        
        if category:
            events_result = events_result.eq("category", category)
            
        events_result = events_result.order("event_date", desc=False).execute()
        
        # Get organizer profiles separately
        if events_result.data:
            # Get unique organizer usernames
            organizer_usernames = list(set([event.get("organizer_username") for event in events_result.data if event.get("organizer_username")]))
            
            # Fetch organizer profiles
            profiles_result = supabase_admin.table("profiles").select("username, full_name, avatar_url").in_("username", organizer_usernames).execute()
            
            # Create a mapping of username to profile
            profile_map = {profile["username"]: profile for profile in profiles_result.data}
            
            # Add profile data to events
            for event in events_result.data:
                organizer_username = event.get("organizer_username")
                if organizer_username and organizer_username in profile_map:
                    event["profiles"] = profile_map[organizer_username]
                else:
                    event["profiles"] = None
            
            # Get user's RSVP status for each event
            event_ids = [event["id"] for event in events_result.data]
            rsvps_result = supabase_admin.table("event_rsvps").select("event_id, status").eq("user_id", user_id).in_("event_id", event_ids).execute()
            
            # Create a mapping of event_id to RSVP status
            rsvp_map = {rsvp["event_id"]: rsvp["status"] for rsvp in rsvps_result.data}
            
            # Add RSVP status to each event
            for event in events_result.data:
                event_id = event["id"]
                rsvp_status = rsvp_map.get(event_id, "not_going")
                event["user_rsvp_status"] = rsvp_status
        
        print(f"Events query result: {events_result.data}")  # Debugging line to check the result
        return {"events": events_result.data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_events: {str(e)}")  # More detailed error logging
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

class RSVPRequest(BaseModel):
    status: str

@app.post("/api/events/{event_id}/rsvp/test")
async def test_rsvp_event(event_id: str, rsvp_data: RSVPRequest, current_user = Depends(get_current_user)):
    """Simplified RSVP endpoint for testing"""
    try:
        return {
            "message": f"Test RSVP received",
            "event_id": event_id,
            "status": rsvp_data.status,
            "user_id": current_user["user"].id
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/events/{event_id}/rsvp")
async def rsvp_event(event_id: str, rsvp_data: RSVPRequest, current_user = Depends(get_current_user)):
    try:
        print(f"RSVP request received: event_id={event_id}, status={rsvp_data.status}")
        
        status = rsvp_data.status
        if status not in ["going", "interested", "not_going"]:
            raise HTTPException(status_code=400, detail="Invalid RSVP status")
        
        user_id = current_user["user"].id
        print(f"User ID: {user_id}")
        
        # Simple upsert operation - delete existing and insert new
        print("Deleting any existing RSVP...")
        delete_result = supabase_admin.table("event_rsvps").delete().eq("user_id", user_id).eq("event_id", event_id).execute()
        print(f"Delete result: {delete_result}")
        
        # Insert new RSVP
        print(f"Inserting new RSVP with status: {status}")
        insert_data = {
            "user_id": user_id,
            "event_id": event_id,
            "status": status
        }
        print(f"Insert data: {insert_data}")
        
        result = supabase_admin.table("event_rsvps").insert(insert_data).execute()
        print(f"Insert result: {result}")
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create RSVP")
        
        return {"message": f"RSVP updated to {status}", "rsvp": result.data[0] if result.data else {}}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in rsvp_event: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RSVP operation failed: {str(e)}")

# Connections endpoints
@app.post("/api/connections/{user_id}/follow")
async def follow_user(user_id: str, current_user = Depends(get_current_user)):
    try:
        if user_id == current_user["user"].id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
        # Check if already following
        existing = supabase.table("connections").select("*").eq("follower_id", current_user["user"].id).eq("following_id", user_id).execute()
        
        if existing.data:
            # Unfollow
            supabase.table("connections").delete().eq("follower_id", current_user["user"].id).eq("following_id", user_id).execute()
            return {"message": "User unfollowed", "following": False}
        else:
            # Follow
            supabase.table("connections").insert({
                "follower_id": current_user["user"].id,
                "following_id": user_id
            }).execute()
            return {"message": "User followed", "following": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/connections/followers")
async def get_followers(current_user = Depends(get_current_user)):
    try:
        result = supabase.table("connections").select("""
            *,
            profiles:follower_id (
                id,
                username,
                full_name,
                avatar_url,
                location
            )
        """).eq("following_id", current_user["user"].id).execute()
        
        return {"followers": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/connections/following")
async def get_following(current_user = Depends(get_current_user)):
    try:
        result = supabase.table("connections").select("""
            *,
            profiles:following_id (
                id,
                username,
                full_name,
                avatar_url,
                location
            )
        """).eq("follower_id", current_user["user"].id).execute()
        
        return {"following": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Badges endpoints
@app.get("/api/badges")
async def get_badges(current_user = Depends(get_current_user)):
    try:
        result = supabase.table("badges").select("*").execute()
        return {"badges": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/user-badges")
async def get_user_badges(current_user = Depends(get_current_user)):
    try:
        result = supabase.table("user_badges").select("""
            *,
            badges (
                id,
                name,
                description,
                icon,
                category
            )
        """).eq("user_id", current_user["user"].id).execute()
        
        return {"user_badges": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Feed endpoint
@app.get("/api/feed")
async def get_feed(limit: int = 20, offset: int = 0, current_user = Depends(get_current_user)):
    try:
        # Get posts from followed users and own posts
        following_result = supabase.table("connections").select("following_id").eq("follower_id", current_user["user"].id).execute()
        following_ids = [conn["following_id"] for conn in following_result.data]
        following_ids.append(current_user["user"].id)  # Include own posts
        
        result = supabase.table("posts").select("""
            *,
            profiles:user_id (
                id,
                username,
                full_name,
                avatar_url
            ),
            places:place_id (
                id,
                name,
                location,
                category
            )
        """).in_("user_id", following_ids).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {"feed": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)