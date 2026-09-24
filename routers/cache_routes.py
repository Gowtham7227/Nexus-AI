from fastapi import APIRouter, Depends
from dependencies.auth_deps import get_current_user
from auth import clear_user_response_cache

router = APIRouter(tags=["cache"])


@router.post("/cache/clear")
def clear_cache_route(
    current_user=Depends(get_current_user),
):
    """Clear cached AI responses for the authenticated user."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    cleared_count = clear_user_response_cache(user_id)
    return {
        "status": "success",
        "cleared_entries": cleared_count,
        "message": f"Successfully invalidated {cleared_count} cached response(s).",
    }
