from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth_deps import get_current_user
from schemas.chat_schemas import FeedbackRequest
from auth import (
    get_conversation,
    save_message_feedback,
    get_conversation_feedback,
)

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
def submit_feedback(
    payload: FeedbackRequest,
    current_user=Depends(get_current_user),
):
    """Submit user feedback (thumbs up/down, reason, notes) for a message."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)

    # Verify conversation ownership
    conv = get_conversation(payload.conversation_id, user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )

    # Sanitize and validate inputs
    raw_rating = payload.rating
    if raw_rating in (1, "1", "helpful"):
        norm_rating = 1
    elif raw_rating in (-1, "-1", "unhelpful"):
        norm_rating = -1
    else:
        raise HTTPException(
            status_code=400,
            detail="Rating must be 1/helpful (positive) or -1/unhelpful (negative).",
        )

    valid_reasons = {
        "accurate", "fast", "helpful", "good_citations",
        "hallucination", "missing_info", "slow", "poor_citations",
        "incorrect_facts", "refused_answer", "other",
        "incorrect_answer", "missing_information", "poor_citation", "irrelevant_sources", "too_verbose"
    }
    chosen_reason = payload.feedback_reason or payload.reason
    if chosen_reason:
        clean_reason = str(chosen_reason).strip().lower()
        if clean_reason not in valid_reasons:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback reason. Allowed: {', '.join(sorted(valid_reasons))}",
            )
        chosen_reason = clean_reason

    clean_text = payload.feedback_text or payload.note
    if clean_text:
        clean_text = str(clean_text).strip()[:1000]

    feedback_id = save_message_feedback(
        user_id=user_id,
        conversation_id=payload.conversation_id,
        rating=norm_rating,
        message_id=payload.message_id,
        feedback_reason=chosen_reason,
        feedback_text=clean_text,
        latency_perceived=payload.latency_perceived,
        request_id=payload.request_id,
    )

    if not feedback_id:
        raise HTTPException(
            status_code=400,
            detail="Failed to record feedback. Invalid message or foreign message reference.",
        )

    return {
        "status": "success",
        "feedback_id": feedback_id,
        "message": "Feedback recorded successfully",
    }


@router.get("/feedback/conversation/{conversation_id}")
def get_conversation_feedback_route(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    """Get all feedback submitted for a conversation."""
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", 1)

    # Verify conversation ownership
    conv = get_conversation(conversation_id, user_id)
    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )

    feedback_list = get_conversation_feedback(conversation_id, user_id)
    return {"feedback": feedback_list}
