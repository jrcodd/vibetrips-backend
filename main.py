from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

load_dotenv()
app = FastAPI(title="VibeTrip API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not all([supabase_url, supabase_key]):
    raise ValueError("Missing Supabase configuration")

supabase: Client = create_client(supabase_url, supabase_key)
supabase_admin: Client = create_client(supabase_url, supabase_service_key)

security = HTTPBearer()

class UserProfile(BaseModel):
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    travel_style: Optional[str] = None
    interests: Optional[List[str]] = []

class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    travel_style: Optional[str] = None
    interests: Optional[List[str]] = None

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
    event_date: str  # Accept ISO string and convert to datetime
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get the current user from the Supabase auth token.

    Args:
        credentials (HTTPAuthorizationCredentials): The HTTP authorization credentials from the request.

    Returns:
        Dict[str, Any]: The current user information and token.
    """
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

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify the API is running.

    Returns:
        Dict[str, str]: The health status of the API.
    """
    return {"status": "healthy", "service": "VibeTrip API"}

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...), bucket_name: str = Form(...), current_user = Depends(get_current_user)) -> Dict[str, str]:
    """
    Upload an image file to a specified Supabase storage bucket.
    
    Args:
        file: The image file to upload
        bucket_name: The bucket name ('avatars', 'event-images', etc.)
        current_user: Current authenticated user
        
    Returns:
        Dict with message and URL
    """
    try:
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file received")
        
        # Avatars should be smaller pictures so the limit is 5MB instead of 10MB
        max_size = 5 * 1024 * 1024 if bucket_name == 'avatars' else 10 * 1024 * 1024
        if len(file_content) > max_size:
            max_mb = max_size // (1024 * 1024)
            raise HTTPException(status_code=400, detail=f"File too large. Max size: {max_mb}MB")
        
        file_extension = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'jpg'
        
        if bucket_name == 'avatars':
            unique_filename = f"avatars/{current_user['user'].id}/{uuid.uuid4()}.{file_extension}"
        else:
            unique_filename = f"{bucket_name}/{uuid.uuid4()}.{file_extension}"
        
        try:
            supabase_admin.storage.create_bucket(bucket_name, {"public": True})
        except:
            pass  # Bucket already exists
        
        result = supabase_admin.storage.from_(bucket_name).upload(
            unique_filename, 
            file_content,
            {"content-type": file.content_type, "upsert": "true"}
        )
        
        if hasattr(result, 'error') and result.error:
            raise HTTPException(status_code=500, detail=f"Upload failed: {result.error}")
        
        public_url = supabase_admin.storage.from_(bucket_name).get_public_url(unique_filename)
        
        if isinstance(public_url, str):
            url = public_url
        else:
            url = getattr(public_url, 'signed_url', None) or getattr(public_url, 'url', None) or str(public_url)
        
        return {"message": "Image uploaded successfully", "url": url}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")

@app.post("/api/profile")
async def create_profile(profile: UserProfile, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Create a user profile.
    
    Args:
        profile: The user profile data
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The created profile data
    """
    try:
        user = current_user["user"]
        
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
async def get_profile(current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get the current user's profile.

    Args:
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The user's profile data
    """
    try:
        user = current_user["user"]
        
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
async def update_profile(profile: ProfileUpdate, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Update the current user's profile.

    Args:
        profile: The updated profile data
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The updated profile data
    """
    try:
        user = current_user["user"]
        
        # Check if username is being changed and if it's already taken
        update_data = profile.model_dump(exclude_unset=True)
        if 'username' in update_data:
            existing_username = supabase_admin.table("profiles").select("id").eq("username", update_data['username']).neq("id", user.id).execute()
            if existing_username.data:
                raise HTTPException(status_code=400, detail="Username already taken")
        
        result = supabase_admin.table("profiles").update(update_data).eq("id", user.id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/profiles/{user_id}")
async def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Get a user profile by user ID.

    Args:
        user_id: The ID of the user whose profile is to be retrieved

    Returns:
        Dict[str, Any]: The user's profile data
    """
    try:
        result = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/posts")
async def create_post(post: PostCreate, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Create a new post.

    Args:
        post: The post data
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The created post data
    """
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
async def get_posts(limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    Get a list of posts with pagination.

    Args:
        limit: The maximum number of posts to return (default 20)
        offset: The number of posts to skip (default 0)

    Returns:
        Dict[str, Any]: A dictionary containing the list of posts and pagination info
    """
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
async def get_post(post_id: str) -> Dict[str, Any]:
    """
    Get a specific post by ID.

    Args:
        post_id: The ID of the post to retrieve

    Returns:
        Dict[str, Any]: The post data
    """
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
async def like_post(post_id: str, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Like or unlike a post.

    Args:
        post_id: The ID of the post to like/unlike
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A message indicating the like status
    """
    try:
        existing = supabase.table("post_likes").select("*").eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
        
        if existing.data:
            supabase.table("post_likes").delete().eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
            return {"message": "Post unliked", "liked": False}
        else:
            supabase.table("post_likes").insert({"user_id": current_user["user"].id, "post_id": post_id}).execute()
            return {"message": "Post liked", "liked": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/posts/{post_id}/save")
async def save_post(post_id: str, current_user = Depends(get_current_user)):
    """
    Save or unsave a post.

    Args:
        post_id: The ID of the post to save/unsave
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A message indicating the save status
    """
    try:
        existing = supabase.table("post_saves").select("*").eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
        
        if existing.data:
            supabase.table("post_saves").delete().eq("user_id", current_user["user"].id).eq("post_id", post_id).execute()
            return {"message": "Post unsaved", "saved": False}
        else:
            supabase.table("post_saves").insert({"user_id": current_user["user"].id, "post_id": post_id}).execute()
            return {"message": "Post saved", "saved": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/places")
async def create_place(place: PlaceCreate, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Create a new place.

    Args:
        place: The place data
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The created place data
    """
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
async def get_places(category: Optional[str] = None, hidden: Optional[bool] = None) -> Dict[str, Any]:
    """
    Get a list of places with optional filters.

    Args:
        category: The category to filter places by (optional)
        hidden: Whether to include hidden places (optional)

    Returns:
        Dict[str, Any]: A dictionary containing the list of places and pagination info
    """
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

@app.post("/api/events")
async def create_event(event: EventCreate, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Create a new event.

    Args:
        event: The event data
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: The created event data
    """
    try:
        user_profile = supabase_admin.table("profiles").select("username").eq("id", current_user["user"].id).execute()
        
        if not user_profile.data:
            raise HTTPException(status_code=400, detail="User profile not found")
        
        organizer_username = user_profile.data[0]["username"]
        
        try:
            event_datetime = datetime.fromisoformat(event.event_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event_date format. Use ISO format.")
        
        # Convert datetime to ISO string for Supabase insertion
        event_datetime_str = event_datetime.isoformat()
        
        event_data = {
            "organizer_id": current_user["user"].id,  # Keep for backward compatibility
            "organizer_username": organizer_username,
            "title": event.title,
            "description": event.description,
            "image_url": event.image_url,
            "event_date": event_datetime_str,  # Pass as ISO string for JSON serialization
            "location": event.location,
            "category": event.category,
            "price": event.price,
            "max_attendees": event.max_attendees
        }
        
        result = supabase_admin.table("events").insert(event_data).execute()
        
        # Convert datetime in response to string for JSON serialization
        if result.data and len(result.data) > 0:
            event_response = result.data[0].copy()
            if 'event_date' in event_response and event_response['event_date']:
                event_response['event_date'] = event_response['event_date'].isoformat() if hasattr(event_response['event_date'], 'isoformat') else str(event_response['event_date'])
            if 'created_at' in event_response and event_response['created_at']:
                event_response['created_at'] = event_response['created_at'].isoformat() if hasattr(event_response['created_at'], 'isoformat') else str(event_response['created_at'])
        else:
            event_response = {}
            
        return {"message": "Event created successfully", "event": event_response}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/events")
async def get_events(category: Optional[str] = None, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get a list of events with optional filters.

    Args:
        category: The category to filter events by (optional)
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A dictionary containing the list of events and pagination info
    """
    try:
        user_id = current_user["user"].id
        
        # Use admin client to bypass RLS for events (events should be publicly viewable)
        events_result = supabase_admin.table("events").select("*")
        
        if category:
            events_result = events_result.eq("category", category)
            
        events_result = events_result.order("event_date", desc=False).execute()
        
        if events_result.data:
            organizer_usernames = list(set([event.get("organizer_username") for event in events_result.data if event.get("organizer_username")]))
            
            profiles_result = supabase_admin.table("profiles").select("username, full_name, avatar_url").in_("username", organizer_usernames).execute()
            
            profile_map = {profile["username"]: profile for profile in profiles_result.data}
            
            for event in events_result.data:
                organizer_username = event.get("organizer_username")
                if organizer_username and organizer_username in profile_map:
                    event["profiles"] = profile_map[organizer_username]
                else:
                    event["profiles"] = None
            
            event_ids = [event["id"] for event in events_result.data]
            rsvps_result = supabase_admin.table("event_rsvps").select("event_id, status").eq("user_id", user_id).in_("event_id", event_ids).execute()
            
            rsvp_map = {rsvp["event_id"]: rsvp["status"] for rsvp in rsvps_result.data}
            
            for event in events_result.data:
                event_id = event["id"]
                rsvp_status = rsvp_map.get(event_id, "not_going")
                event["user_rsvp_status"] = rsvp_status
        
        return {"events": events_result.data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_events: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

class RSVPRequest(BaseModel):
    status: str

@app.post("/api/events/{event_id}/rsvp/test")
async def test_rsvp_event(event_id: str, rsvp_data: RSVPRequest, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Simplified RSVP endpoint for testing

    Args:
        event_id: The ID of the event to RSVP to
        rsvp_data: The RSVP data containing status
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A message indicating the RSVP status
    """
    try:
        return {
            "message": f"Test RSVP received",
            "event_id": event_id,
            "status": rsvp_data.status,
            "user_id": current_user["user"].id
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/events/cleanup-past")
async def cleanup_past_events() -> Dict[str, Any]:
    """
    Delete all events that have passed their start time
    
    Returns:
        Dict[str, Any]: A message indicating the number of deleted events
    """
    try:
        now = datetime.now().isoformat()
        
        past_events = supabase_admin.table("events").select(
            "id, title, event_date"
        ).lt("event_date", now).execute()
        
        if not past_events.data:
            return {"message": "No past events found", "deleted_count": 0}
        
        deleted_count = 0
        
        for event in past_events.data:
            try:
                event_id = event["id"]
                
                supabase_admin.table("event_rsvps").delete().eq("event_id", event_id).execute()
                
                delete_response = supabase_admin.table("events").delete().eq("id", event_id).execute()
                
                if not delete_response.error:
                    deleted_count += 1
                    print(f"Deleted past event: {event['title']}")
                    
            except Exception as e:
                print(f"Error deleting past event {event_id}: {e}")
                continue
        
        return {"message": f"Deleted {deleted_count} past events", "deleted_count": deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in cleanup_past_events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup operation failed: {str(e)}")

@app.post("/api/events/{event_id}/rsvp")
async def rsvp_event(event_id: str, rsvp_data: RSVPRequest, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    RSVP to an event.

    Args:
        event_id: The ID of the event to RSVP to
        rsvp_data: The RSVP data containing status
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A message indicating the RSVP status
    """

    try:
        print(f"RSVP request received: event_id={event_id}, status={rsvp_data.status}")
        
        status = rsvp_data.status
        if status not in ["going", "interested", "not_going"]:
            raise HTTPException(status_code=400, detail="Invalid RSVP status")
        
        user_id = current_user["user"].id
        print(f"User ID: {user_id}")
        
        print("Deleting any existing RSVP...")
        delete_result = supabase_admin.table("event_rsvps").delete().eq("user_id", user_id).eq("event_id", event_id).execute()
        print(f"Delete result: {delete_result}")
        
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

@app.post("/api/connections/{user_id}/follow")
async def follow_user(user_id: str, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Follow or unfollow a user.

    Args:
        user_id: The ID of the user to follow/unfollow
        current_user: The currently authenticated user

    Returns:
        Dict[str, Any]: A message indicating the follow/unfollow status
    """
    try:
        if user_id == current_user["user"].id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
        
        existing = supabase.table("connections").select("*").eq("follower_id", current_user["user"].id).eq("following_id", user_id).execute()
        
        if existing.data:
            supabase.table("connections").delete().eq("follower_id", current_user["user"].id).eq("following_id", user_id).execute()
            return {"message": "User unfollowed", "following": False}
        else:
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

@app.get("/api/badges")
async def get_badges():
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

@app.get("/api/feed")
async def get_feed(limit: int = 20, offset: int = 0, current_user = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        following_result = supabase.table("connections").select("following_id").eq("follower_id", current_user["user"].id).execute()
        following_ids = [conn["following_id"] for conn in following_result.data]
        following_ids.append(current_user["user"].id)  
        
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