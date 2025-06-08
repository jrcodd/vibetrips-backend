from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.core.supabase import supabase
from app.schemas.event import EventCreate, EventUpdate, Event, EventParticipant, ParticipantStatus
import uuid
import json

router = APIRouter()

@router.post("/", response_model=Event)
async def create_event(
    event_data: EventCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new event"""
    # Create PostGIS point from latitude and longitude
    point = f"POINT({event_data.location.longitude} {event_data.location.latitude})"
    
    # Prepare event data
    event_dict = event_data.dict(exclude={"location"})
    event_dict["creator_id"] = current_user["id"]
    event_dict["location"] = point  # PostGIS point
    
    # Create event
    response = supabase.table("events").insert(event_dict).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    # Create activity
    activity_data = {
        "user_id": current_user["id"],
        "actor_id": current_user["id"],
        "activity_type": "event_create",
        "event_id": response.data[0]["id"]
    }
    supabase.table("activities").insert(activity_data).execute()
    
    # Add creator as participant
    participant_data = {
        "event_id": response.data[0]["id"],
        "user_id": current_user["id"],
        "status": ParticipantStatus.GOING
    }
    supabase.table("event_participants").insert(participant_data).execute()
    
    return response.data[0]

@router.get("/", response_model=List[Event])
async def get_events(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    distance_km: Optional[float] = Query(10, ge=0.1, le=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get events with optional location filtering"""
    query = supabase.table("events").select(
        "*, creator:profiles!events_creator_id_fkey(*), participants_count:event_participants(count)"
    ).order("start_time", desc=False).range(offset, offset + limit - 1)
    
    # Apply location filtering if coordinates provided
    if latitude is not None and longitude is not None:
        # Using PostGIS to find events within the specified distance
        point = f"POINT({longitude} {latitude})"
        distance = distance_km * 1000  # Convert km to meters
        
        # ST_DWithin checks if points are within specified distance
        query = query.filter(
            "location",
            "st_dwithin",
            f"ST_SetSRID(ST_MakePoint({longitude}, {latitude}), 4326), {distance}"
        )
    
    response = query.execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    # Process response to extract participant count and check if user is participating
    events = []
    for event in response.data:
        # Extract participant count
        if event.get("participants_count") and len(event["participants_count"]) > 0:
            event["participants_count"] = event["participants_count"][0]["count"]
        else:
            event["participants_count"] = 0
        
        # Check if current user is participating
        participant_check = supabase.table("event_participants").select(
            "id"
        ).eq("event_id", event["id"]).eq("user_id", current_user["id"]).execute()
        
        event["is_user_participating"] = len(participant_check.data) > 0
        
        events.append(event)
    
    return events

@router.post("/{event_id}/participants", response_model=EventParticipant)
async def join_event(
    event_id: str,
    status: ParticipantStatus = ParticipantStatus.GOING,
    current_user: dict = Depends(get_current_user)
):
    """Join an event"""
    # Check if user is already a participant
    check = supabase.table("event_participants").select(
        "*"
    ).eq("event_id", event_id).eq("user_id", current_user["id"]).execute()
    
    if check.data:
        # Update status if already a participant
        response = supabase.table("event_participants").update(
            {"status": status}
        ).eq("event_id", event_id).eq("user_id", current_user["id"]).execute()
    else:
        # Add as new participant
        participant_data = {
            "event_id": event_id,
            "user_id": current_user["id"],
            "status": status
        }
        response = supabase.table("event_participants").insert(participant_data).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    # Create activity for joining event
    if status == ParticipantStatus.GOING and not check.data:
        # Get event creator
        event = supabase.table("events").select("creator_id").eq("id", event_id).execute()
        if event.data:
            activity_data = {
                "user_id": event.data[0]["creator_id"],
                "actor_id": current_user["id"],
                "activity_type": "event_join",
                "event_id": event_id
            }
            supabase.table("activities").insert(activity_data).execute()
    
    return response.data[0]
