from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from app.schemas.user import User

class FollowCreate(BaseModel):
    following_id: str

class Follow(BaseModel):
    id: str
    follower_id: str
    following_id: str
    created_at: datetime

class ActivityType(str, Enum):
    POST = "post"
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    EVENT_CREATE = "event_create"
    EVENT_JOIN = "event_join"

class Activity(BaseModel):
    id: str
    user_id: str
    actor_id: Optional[str]
    activity_type: ActivityType
    post_id: Optional[str]
    comment_id: Optional[str]
    event_id: Optional[str]
    created_at: datetime
    
    # Include these when returning activities to clients
    actor: Optional[User] = None
    post_data: Optional[Dict[str, Any]] = None
    comment_data: Optional[Dict[str, Any]] = None
    event_data: Optional[Dict[str, Any]] = None
