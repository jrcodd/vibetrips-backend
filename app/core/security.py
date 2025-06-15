from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.supabase import supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The hashed password to compare against.
        
    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generate password hash
    
    Args:
        password (str): The plain text password to hash.
        
    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token
    
    Args:
        data (dict): The data to encode in the token.
        expires_delta (Optional[timedelta]): The expiration time for the token. Defaults to 15 minutes if not provided.

    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Get current authenticated user
    
    Args:
        credentials (HTTPAuthorizationCredentials): The HTTP authorization credentials containing the Bearer token.

    Returns:
        dict: The user information extracted from the token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        print(f"DEBUG: Received token: {token[:50]}...")
        
        response = supabase.auth.get_user(token)
        print(f"DEBUG: Supabase auth response: {response}")
        
        if not response.user:
            print("DEBUG: No user found in Supabase auth response")
            raise credentials_exception
            
        user_id = response.user.id
        print(f"DEBUG: Extracted user_id from Supabase: {user_id}")
        
        return {"id": user_id}
        
    except Exception as e:
        print(f"DEBUG: Authentication error: {e}")
        raise credentials_exception
