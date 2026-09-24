from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth_deps import get_current_user
from schemas.chat_schemas import (
    CreateConversationRequest,
    UpdateConversationRequest,
)
from auth import (
    create_conversation,
    get_user_conversations,
    get_conversation,
    update_conversation_title,
    delete_conversation,
)

router = APIRouter(tags=["conversations"])


@router.post("/conversations")
def create_new_conversation(
    request: CreateConversationRequest = None,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    title = request.title if (request and request.title) else "New Conversation"
    conv = create_conversation(user_id, title)
    return conv


@router.get("/conversations")
def list_conversations(
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    conversations = get_user_conversations(user_id)
    return conversations


@router.get("/conversations/{conversation_id}")
def get_single_conversation(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    conv = get_conversation(conversation_id, user_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return conv


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    if not request.title or not request.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Conversation title cannot be empty.",
        )
    success = update_conversation_title(conversation_id, user_id, request.title.strip())
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return {
        "message": "Conversation renamed successfully.",
        "id": conversation_id,
        "title": request.title.strip(),
    }


@router.delete("/conversations/{conversation_id}")
def remove_conversation(
    conversation_id: int,
    current_user=Depends(get_current_user),
):
    user_id = current_user["user_id"]
    success = delete_conversation(conversation_id, user_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )
    return {
        "message": "Conversation deleted successfully.",
        "id": conversation_id,
    }
