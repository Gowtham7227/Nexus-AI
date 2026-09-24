from fastapi import HTTPException
from schemas.chat_schemas import ChatRequest
from auth import (
    get_conversation,
    create_conversation,
    save_message,
    generate_conversation_title,
    set_conversation_documents,
)
from retriever import retrieve_context


def get_selected_filenames(
    request: ChatRequest,
) -> list[str]:
    filenames = []

    # New frontend format
    if request.filenames:
        for filename in request.filenames:
            if filename and filename.strip():
                clean_filename = filename.strip()
                if clean_filename not in filenames:
                    filenames.append(clean_filename)

    # Old frontend format
    if request.filename and request.filename.strip():
        clean_filename = request.filename.strip()
        if clean_filename not in filenames:
            filenames.append(clean_filename)

    return filenames


def retrieve_multi_document_context(
    question: str,
    filenames: list[str],
) -> str:
    if not filenames:
        return ""

    all_contexts = []

    print("=" * 70)
    print("🔍 MULTI-DOCUMENT RETRIEVAL")
    print("Question:", question)
    print("Documents:", filenames)
    print("=" * 70)

    # Retrieve each document separately
    for index, filename in enumerate(filenames, start=1):
        try:
            print(f"🔍 Retrieving document {index}/{len(filenames)}: {filename}")
            context = retrieve_context(
                question,
                filename,
            )

            if context and context.strip():
                document_context = (
                    "\n"
                    + "=" * 60
                    + "\n"
                    + f"DOCUMENT {index}: {filename}"
                    + "\n"
                    + "=" * 60
                    + "\n"
                    + context.strip()
                    + "\n"
                )
                all_contexts.append(document_context)
                print(f"✅ Context retrieved from: {filename}")
                print("Context length:", len(context))
            else:
                print(f"⚠️ No relevant context found in: {filename}")

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            print(f"❌ Retrieval failed for {filename}:", str(e))

    combined_context = "\n".join(all_contexts)
    print("=" * 70)
    print("📚 COMBINED CONTEXT LENGTH:", len(combined_context))
    print("📄 DOCUMENT COUNT:", len(filenames))
    print("=" * 70)

    return combined_context


def resolve_or_create_conversation(
    user_id: int,
    conv_id: int | None,
    question: str,
    filenames: list[str],
) -> tuple[int, str]:
    if conv_id:
        conv = get_conversation(conv_id, user_id)
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )
        conv_title = conv.get("title", "Conversation")
    else:
        conv_title = generate_conversation_title(question)
        conv = create_conversation(user_id, conv_title)
        conv_id = conv["id"]

    # Save user message
    save_message(conv_id, "user", question)

    # Persist document selection for this conversation
    if filenames:
        set_conversation_documents(conv_id, user_id, filenames)
    else:
        set_conversation_documents(conv_id, user_id, [])

    return conv_id, conv_title
