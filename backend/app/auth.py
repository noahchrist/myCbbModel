from fastapi import Request, HTTPException
from supabase import Client

async def get_current_user(request: Request, supabase: Client) -> str:
    """
    Extract and validate user from JWT token.
    Returns user_id (UUID) from Supabase auth.
    
    Raises HTTPException if token is invalid or missing.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(" ", 1)[1]
    
    try:
        # Verify token and get user
        user_response = supabase.auth.get_user(jwt=token)
        user_id = user_response.user.id
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        
        return str(user_id)  # Return as string (UUID)
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_user_display_name(supabase: Client, token: str) -> str:
    """
    Optional helper: Get display name from Supabase user_metadata.
    
    Returns display name if set, otherwise returns email prefix.
    """
    try:
        user_response = supabase.auth.get_user(jwt=token)
        user = user_response.user
        
        # Try to get display_name from user_metadata
        display_name = user.user_metadata.get('display_name')
        
        if display_name:
            return display_name
        
        # Fallback: use email prefix
        if user.email:
            return user.email.split('@')[0]
        
        return "User"
        
    except Exception:
        return "User"