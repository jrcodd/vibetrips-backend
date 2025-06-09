from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.endpoints import auth, posts, users, locations, events

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
#app.include_router(posts.router, prefix="/api/v1/posts", tags=["posts"])
#app.include_router(locations.router, prefix="/api/v1/locations", tags=["locations"])

@app.get("/")
async def root():
    return {"message": "VibeTrip API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

