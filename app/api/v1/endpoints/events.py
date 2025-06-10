from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.core.supabase import supabase
from app.schemas.event import EventCreate, EventUpdate, Event, EventParticipant, ParticipantStatus
import uuid
import json
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=Event)
async def create_event(
    event_data: EventCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new event with insertion sort by start_time"""
    # Create PostGIS point from latitude and longitude
    point = f"POINT({event_data.location.longitude} {event_data.location.latitude})"
    
    # Prepare event data - convert datetime to ISO string for JSON serialization
    event_dict = event_data.dict(exclude={"location"})
    
    # Convert datetime fields to ISO string format for Supabase
    if isinstance(event_dict.get("start_time"), datetime):
        event_dict["start_time"] = event_dict["start_time"].isoformat()
    if isinstance(event_dict.get("end_time"), datetime):
        event_dict["end_time"] = event_dict["end_time"].isoformat()
    
    event_dict["creator_id"] = current_user["id"]
    event_dict["location"] = point  # PostGIS point
    
    # Get the new event's start time for sorting
    new_event_time = event_dict["start_time"]
    
    # Get all existing events to determine sort position using insertion sort logic
    existing_events = supabase.table("events").select(
        "id, start_time, sort_order"
    ).order("sort_order", desc=False).execute()
    
    # Calculate the sort_order using insertion sort algorithm
    sort_order = 0
    if existing_events.data:
        # Find the correct position for insertion
        for i, event in enumerate(existing_events.data):
            if new_event_time < event["start_time"]:
                # Insert before this event
                sort_order = i
                break
            else:
                # Insert after this event
                sort_order = i + 1
        
        # Update sort_order for all events that need to be shifted
        for j in range(sort_order, len(existing_events.data)):
            event_to_update = existing_events.data[j]
            supabase.table("events").update({
                "sort_order": event_to_update.get("sort_order", j) + 1
            }).eq("id", event_to_update["id"]).execute()
    
    event_dict["sort_order"] = sort_order
    
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
    """Get events with optional location filtering, ordered by insertion sort"""
    query = supabase.table("events").select(
        "*, creator:profiles!events_creator_id_fkey(*), participants_count:event_participants(count)"
    ).order("sort_order", desc=False).range(offset, offset + limit - 1)
    
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

@router.post("/cleanup-past")
async def cleanup_past_events(
    current_user: dict = Depends(get_current_user)
):
    """Delete all events that have passed their start time"""
    # Get current time
    now = datetime.now().isoformat()
    
    # Find past events
    past_events = supabase.table("events").select(
        "id, title, start_time"
    ).lt("start_time", now).execute()
    
    if not past_events.data:
        return {"message": "No past events found", "deleted_count": 0}
    
    deleted_count = 0
    
    for event in past_events.data:
        try:
            event_id = event["id"]
            
            # Delete related data first
            supabase.table("event_participants").delete().eq("event_id", event_id).execute()
            supabase.table("activities").delete().eq("event_id", event_id).execute()
            
            # Delete the event
            delete_response = supabase.table("events").delete().eq("id", event_id).execute()
            
            if not delete_response.error:
                deleted_count += 1
                
        except Exception as e:
            print(f"Error deleting past event {event_id}: {e}")
            continue
    
    return {"message": f"Deleted {deleted_count} past events", "deleted_count": deleted_count}

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

@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an event"""
    # Check if the event exists and if the user is the creator
    event_check = supabase.table("events").select(
        "id, creator_id"
    ).eq("id", event_id).execute()
    
    if not event_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    event = event_check.data[0]
    
    # Only allow creator to delete the event
    if event["creator_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the event creator can delete this event"
        )
    
    # Delete related data first (due to foreign key constraints)
    # Delete event participants
    supabase.table("event_participants").delete().eq("event_id", event_id).execute()
    
    # Delete related activities
    supabase.table("activities").delete().eq("event_id", event_id).execute()
    
    # Delete the event
    response = supabase.table("events").delete().eq("id", event_id).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    return {"message": "Event deleted successfully"}
