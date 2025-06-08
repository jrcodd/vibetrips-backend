from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ParticipantStatus(str, Enum):
    GOING = "going"
    MAYBE = "maybe"
    INVITED = "invited"

class LocationPoint(BaseModel):
    longitude: float
    latitude: float

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: LocationPoint
    location_name: str
    place_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    cover_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    is_private: bool = False

class FrontendEventCreate(BaseModel):
    """Schema that matches the frontend event creation data"""
    title: str
    description: Optional[str] = None
    location: str  # Frontend sends location as string
    category: str
    price: Optional[str] = None
    max_attendees: Optional[int] = None
    image_url: Optional[str] = None
    event_date: str  # Frontend sends as ISO string

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[LocationPoint] = None
    location_name: Optional[str] = None
    place_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    cover_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    is_private: Optional[bool] = None

class Event(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    creator_id: str
    location_name: str
    place_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    cover_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    is_private: bool
    created_at: datetime
    updated_at: datetime
    
    # Additional fields
    creator: Optional[Dict[str, Any]] = None
    participants_count: Optional[int] = 0
    is_user_participating: Optional[bool] = False

class EventParticipant(BaseModel):
    id: str
    event_id: str
    user_id: str
    status: ParticipantStatus
    created_at: datetime
    updated_at: datetime
