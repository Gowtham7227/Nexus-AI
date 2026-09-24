from fastapi import APIRouter, Depends
from dependencies.auth_deps import get_current_user
from auth import (
    get_user_analytics_summary,
    get_user_latency_series,
    get_user_rag_distribution,
    get_user_model_stats,
)

router = APIRouter(tags=["analytics"])


@router.get("/analytics/overview")
def get_analytics_overview(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve overall system analytics for the authenticated user."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    summary = get_user_analytics_summary(user_id, days=safe_days)
    return summary


@router.get("/analytics/latency")
def get_analytics_latency(
    days: int = 7,
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """Retrieve time-series latency breakdown records for charts."""
    safe_days = max(1, min(days, 90))
    safe_limit = max(1, min(limit, 200))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_latency_series(user_id, days=safe_days, limit=safe_limit)
    return {"latency_series": data}


@router.get("/analytics/rag")
def get_analytics_rag(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve query type distribution and RAG optimizer strategy breakdown."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_rag_distribution(user_id, days=safe_days)
    return data


@router.get("/analytics/models")
def get_analytics_models(
    days: int = 7,
    current_user=Depends(get_current_user),
):
    """Retrieve per-model usage and latency metrics."""
    safe_days = max(1, min(days, 90))
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)
    data = get_user_model_stats(user_id, days=safe_days)
    return {"models": data}
