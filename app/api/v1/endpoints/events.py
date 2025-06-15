from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.core.supabase import supabase
from app.schemas.event import EventCreate, Event, EventParticipant, ParticipantStatus
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=Event)
async def create_event(event_data: EventCreate, current_user: dict = Depends(get_current_user)) -> Event:
    """
    Create a new event with insertion sort by start_time
    
    Args:
        event_data (EventCreate): The event data including title, description, start_time, end_time, and location.
        current_user (dict): The current authenticated user.
        
    Returns:
        Event: The created event with all details including creator and participants count.
    """
    point = f"POINT({event_data.location.longitude} {event_data.location.latitude})"
    
    event_dict = event_data.model_dump(exclude={"location"})
    
    if isinstance(event_dict.get("start_time"), datetime):
        event_dict["start_time"] = event_dict["start_time"].isoformat()
    if isinstance(event_dict.get("end_time"), datetime):
        event_dict["end_time"] = event_dict["end_time"].isoformat()
    
    event_dict["creator_id"] = current_user["id"]
    event_dict["location"] = point  
    new_event_time = event_dict["start_time"]
    
    existing_events = supabase.table("events").select(
        "id, start_time, sort_order"
    ).order("sort_order", desc=False).execute()
    
    sort_order = 0
    if existing_events.data:
        for i, event in enumerate(existing_events.data):
            if new_event_time < event["start_time"]:
                sort_order = i
                break
            else:
                sort_order = i + 1
        
        for j in range(sort_order, len(existing_events.data)):
            event_to_update = existing_events.data[j]
            supabase.table("events").update({
                "sort_order": event_to_update.get("sort_order", j) + 1
            }).eq("id", event_to_update["id"]).execute()
    
    event_dict["sort_order"] = sort_order
    
    response = supabase.table("events").insert(event_dict).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    activity_data = {
        "user_id": current_user["id"],
        "actor_id": current_user["id"],
        "activity_type": "event_create",
        "event_id": response.data[0]["id"]
    }
    supabase.table("activities").insert(activity_data).execute()
    
    participant_data = {
        "event_id": response.data[0]["id"],
        "user_id": current_user["id"],
        "status": ParticipantStatus.GOING
    }
    supabase.table("event_participants").insert(participant_data).execute()
    
    return response.data[0]

@router.get("/", response_model=List[Event])
async def get_events(latitude: Optional[float] = None, longitude: Optional[float] = None, distance_km: Optional[float] = Query(10, ge=0.1, le=100), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), current_user: dict = Depends(get_current_user)) -> List[Event]:
    """
    Get events with optional location filtering, ordered by insertion sort
    
    Args:
        latitude (Optional[float]): Latitude for location filtering.
        longitude (Optional[float]): Longitude for location filtering.
        distance_km (Optional[float]): Distance in kilometers to filter events by location. Defaults to 10 km.
        limit (int): Maximum number of events to return. Defaults to 20, max 100.
        offset (int): Number of events to skip for pagination. Defaults to 0.

    Returns:
        List[Event]: A list of events with details including creator and participants count.
    """
    query = supabase.table("events").select(
        "*, creator:profiles!events_creator_id_fkey(*), participants_count:event_participants(count)"
    ).order("sort_order", desc=False).range(offset, offset + limit - 1)
    
    if latitude is not None and longitude is not None:
        distance = distance_km * 1000  
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
    events = []
    for event in response.data:
        if event.get("participants_count") and len(event["participants_count"]) > 0:
            event["participants_count"] = event["participants_count"][0]["count"]
        else:
            event["participants_count"] = 0
        
        participant_check = supabase.table("event_participants").select(
            "id"
        ).eq("event_id", event["id"]).eq("user_id", current_user["id"]).execute()
        
        event["is_user_participating"] = len(participant_check.data) > 0
        
        events.append(event)
    
    return events

@router.post("/cleanup-past")
async def cleanup_past_events() -> dict:
    """
    Delete all events that have passed their start time

    Returns:
        dict: A message indicating the number of deleted events.
    """
    now = datetime.now().isoformat()
    
    past_events = supabase.table("events").select(
        "id, title, start_time"
    ).lt("start_time", now).execute()
    
    if not past_events.data:
        return {"message": "No past events found", "deleted_count": 0}
    
    deleted_count = 0
    
    for event in past_events.data:
        try:
            event_id = event["id"]
            
            supabase.table("event_participants").delete().eq("event_id", event_id).execute()
            supabase.table("activities").delete().eq("event_id", event_id).execute()
            
            delete_response = supabase.table("events").delete().eq("id", event_id).execute()
            
            if not delete_response.error:
                deleted_count += 1
                
        except Exception as e:
            print(f"Error deleting past event {event_id}: {e}")
            continue
    
    return {"message": f"Deleted {deleted_count} past events", "deleted_count": deleted_count}

@router.post("/{event_id}/participants", response_model=EventParticipant)
async def join_event(event_id: str, status: ParticipantStatus = ParticipantStatus.GOING, current_user: dict = Depends(get_current_user)) -> EventParticipant:
    """
    Join an event
    
    Args:
        event_id (str): The ID of the event to join.
        status (ParticipantStatus): The status of the participant (e.g., GOING, NOT_GOING).
        current_user (dict): The current authenticated user.
        
    Returns:
        EventParticipant: The participant data including event ID, user ID, and status.
    """
    check = supabase.table("event_participants").select("*").eq("event_id", event_id).eq("user_id", current_user["id"]).execute()
    
    if check.data:
        response = supabase.table("event_participants").update(
            {"status": status}
        ).eq("event_id", event_id).eq("user_id", current_user["id"]).execute()
    else:
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
    
    if status == ParticipantStatus.GOING and not check.data:
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
async def delete_event(event_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete an event
    
    Args:
        event_id (str): The ID of the event to delete.
        current_user (dict): The current authenticated user.
        
    Returns:
        dict: A message indicating the success of the deletion.
    """
    event_check = supabase.table("events").select(
        "id, creator_id"
    ).eq("id", event_id).execute()
    
    if not event_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    event = event_check.data[0]
    
    if event["creator_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the event creator can delete this event"
        )
    
    supabase.table("event_participants").delete().eq("event_id", event_id).execute()
    
    supabase.table("activities").delete().eq("event_id", event_id).execute()
    
    response = supabase.table("events").delete().eq("id", event_id).execute()
    
    if response.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(response.error)
        )
    
    return {"message": "Event deleted successfully"}
