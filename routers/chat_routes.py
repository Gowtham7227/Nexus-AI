import os
import time
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from dependencies.auth_deps import get_current_user
from schemas.chat_schemas import ChatRequest
from services.chat_service import (
    get_selected_filenames,
    resolve_or_create_conversation,
)
from services.document_service import validate_user_documents
from auth import (
    save_message,
    touch_conversation,
    compute_document_fingerprint,
    compute_cache_key,
    get_cached_response,
    set_cached_response,
    record_ai_metric,
)
from chatbot import (
    ask_gemini_general,
    ask_gemini_stream,
    ask_gemini_general_stream,
)
from local_llm import (
    ask_local,
    stream_local,
    warmup_local_model,
)
from model_provider import GeminiModelProvider, LocalQwenModelProvider
from advanced_rag import NexusAdvancedRAG
from rag_evaluation import SourceCitationManager, DeterministicGroundingEvaluator
from privacy_scanner import OutputPrivacyGuard
from services.reasoning_service import MultiHopReasoningService

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))

router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    t_req_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    try:
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", "unknown")
        user_email = current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "unknown")
        filenames = get_selected_filenames(request)

        # Stage [1] REQUEST PARSED
        print("=" * 70)
        print(f"🔹 [STAGE 1] REQUEST PARSED: req_id={request_id[:8]}, user_id={user_id}, question='{request.question[:60]}...', doc_count={len(filenames)}, filenames={filenames}")

        # Stage [2] AUTHENTICATION PASSED
        print(f"🔹 [STAGE 2] AUTHENTICATION PASSED: user_id={user_id}, email={user_email}")

        # Validate documents if specified
        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        # Resolve or create persistent conversation & save user message
        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        active_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        normalized_query = request.question.strip()
        doc_fingerprint = compute_document_fingerprint(current_user["user_id"], validated_filenames)
        cache_key = compute_cache_key(current_user["user_id"], normalized_query, doc_fingerprint, active_model)

        # ----------------------------------------------------
        # RESPONSE CACHE CHECK
        # ----------------------------------------------------
        if CACHE_ENABLED:
            cached = get_cached_response(current_user["user_id"], cache_key)
            if cached:
                total_ms = (time.perf_counter() - t_req_start) * 1000
                msg_id = save_message(conv_id, "assistant", cached["answer"])
                touch_conversation(conv_id, current_user["user_id"])
                print(f"⚡ [CACHE HIT] Query resolved in {total_ms:.2f}ms (key={cache_key[:8]}...)")

                record_ai_metric(
                    request_id=request_id,
                    user_id=current_user["user_id"],
                    conversation_id=conv_id,
                    query_type="cached",
                    optimizer_strategy="cache_hit",
                    retrieval_ms=0.0,
                    total_ms=total_ms,
                    citation_count=len(cached.get("citations", [])),
                    grounding_score=cached.get("grounding", {}).get("grounding_score", 1.0) if cached.get("grounding") else 1.0,
                    model=active_model,
                    streaming=0,
                    cache_hit=1,
                    status="success",
                )

                return {
                    "question": request.question,
                    "filenames": validated_filenames,
                    "sources": validated_filenames if validated_filenames else [],
                    "mode": "cloud",
                    "answer": cached["answer"],
                    "response": cached["answer"],
                    "citations": cached.get("citations", []),
                    "grounding": cached.get("grounding") or {
                        "grounding_score": 1.0,
                        "supported_claim_ratio": 1.0,
                        "unsupported_claim_ratio": 0.0,
                    },
                    "evidence_quality": "High",
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "request_id": request_id,
                    "message_id": msg_id,
                    "cache_hit": True,
                }

        # ----------------------------------------------------
        # GENERAL AI (No document selected)
        # ----------------------------------------------------
        if not validated_filenames:
            print("🌐 Executing General AI Chat (No documents attached)...")
            t_gen_start = time.perf_counter()
            answer = ask_gemini_general(request.question)
            gen_ms = (time.perf_counter() - t_gen_start) * 1000
            total_ms = (time.perf_counter() - t_req_start) * 1000

            msg_id = save_message(conv_id, "assistant", answer)
            touch_conversation(conv_id, current_user["user_id"])

            if CACHE_ENABLED:
                set_cached_response(
                    user_id=current_user["user_id"],
                    cache_key=cache_key,
                    normalized_query=normalized_query,
                    doc_fingerprint=doc_fingerprint,
                    model=active_model,
                    answer=answer,
                    citations=[],
                    grounding={"grounding_score": 1.0, "supported_claim_ratio": 1.0, "unsupported_claim_ratio": 0.0},
                    conversation_id=conv_id,
                    ttl_seconds=CACHE_TTL_SECONDS,
                )

            record_ai_metric(
                request_id=request_id,
                user_id=current_user["user_id"],
                conversation_id=conv_id,
                query_type="general_ai",
                optimizer_strategy="direct_generation",
                retrieval_ms=0.0,
                generation_ms=gen_ms,
                total_ms=total_ms,
                output_tokens=len(answer.split()),
                citation_count=0,
                grounding_score=1.0,
                model=active_model,
                streaming=0,
                cache_hit=0,
                status="success",
            )

            print(f"✅ [STAGE 10] CHAT SUCCESS: Mode=General AI, Answer Length={len(answer)} chars, Conv ID={conv_id}")
            print("=" * 70)
            return {
                "question": request.question,
                "filenames": [],
                "sources": [],
                "mode": "cloud",
                "answer": answer,
                "response": answer,
                "citations": [],
                "grounding": {
                    "score": 1.0,
                    "grounding_score": 1.0,
                    "supported_claim_ratio": 1.0,
                    "unsupported_claim_ratio": 0.0,
                },
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "request_id": request_id,
                "message_id": msg_id,
                "cache_hit": False,
            }

        # Stage [3] DOCUMENT LOOKUP START
        print(f"🔹 [STAGE 3] DOCUMENT LOOKUP START: checking sqlite ownership for user_id={user_id}, docs={validated_filenames}")

        # Stage [4] DOCUMENT LOOKUP RESULT
        print(f"🔹 [STAGE 4] DOCUMENT LOOKUP RESULT: verified={validated_filenames}, count={len(validated_filenames)}")

        # Stage [5] ADVANCED HYBRID RETRIEVAL START
        print(f"🔹 [STAGE 5] ADVANCED HYBRID RETRIEVAL START: querying Hybrid RAG / Multi-Hop for question='{request.question[:60]}...' against {validated_filenames}")

        # Retrieve hybrid context with multi-hop iterative reasoning, reranking, and verification
        retrieval_res = MultiHopReasoningService.execute_multi_hop_pipeline(
            request.question,
            validated_filenames,
            user_id=current_user["user_id"],
        )
        context = retrieval_res["formatted_context"]
        evidence_quality = retrieval_res["evidence_quality"]
        raw_citations = retrieval_res.get("citations", [])
        retrieval_timings = retrieval_res.get("timings", {})
        strategy_info = retrieval_res.get("strategy", {})
        reasoning_mode = retrieval_res.get("reasoning_mode", "single_pass")
        hop_count = retrieval_res.get("hop_count", 1)
        subquery_count = len(retrieval_res.get("subqueries", [request.question]))
        evidence_sufficiency = retrieval_res.get("evidence_sufficiency", "sufficient")
        conflict_detected = retrieval_res.get("conflict_detected", False)
        table_evidence = retrieval_res.get("table_evidence", False)

        # Stage [6] ADVANCED RETRIEVAL RESULT
        print(f"🔹 [STAGE 6] ADVANCED RETRIEVAL RESULT: retrieved context length={len(context)} chars, evidence_quality={evidence_quality}, reasoning_mode={reasoning_mode}, hops={hop_count}")

        if not context.strip() or evidence_sufficiency == "insufficient":
            print("⚠️ No relevant or sufficient context found across documents.")
            fallback_ans = "I couldn't find sufficient information in the selected document(s) to answer this question."
            msg_id = save_message(conv_id, "assistant", fallback_ans)
            touch_conversation(conv_id, current_user["user_id"])
            total_ms = (time.perf_counter() - t_req_start) * 1000

            record_ai_metric(
                request_id=request_id,
                user_id=current_user["user_id"],
                conversation_id=conv_id,
                query_type=strategy_info.get("query_type", "document_rag"),
                optimizer_strategy=strategy_info.get("complexity", "hybrid"),
                retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
                chroma_ms=retrieval_timings.get("semantic_search_ms"),
                bm25_ms=retrieval_timings.get("bm25_ms"),
                cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
                compression_ms=retrieval_timings.get("compression_ms"),
                generation_ms=0.0,
                total_ms=total_ms,
                citation_count=0,
                grounding_score=1.0,
                model=active_model,
                streaming=0,
                cache_hit=0,
                status="insufficient_evidence",
                reasoning_mode=reasoning_mode,
                hop_count=hop_count,
                subquery_count=subquery_count,
                evidence_sufficiency=evidence_sufficiency,
                conflict_detected=1 if conflict_detected else 0,
                table_retrieval_used=1 if table_evidence else 0,
                reasoning_latency=retrieval_timings.get("reasoning_ms", 0.0),
            )

            return {
                "question": request.question,
                "filenames": validated_filenames,
                "sources": validated_filenames if validated_filenames else [],
                "mode": "cloud",
                "answer": fallback_ans,
                "response": fallback_ans,
                "citations": [],
                "grounding": {
                    "score": 1.0,
                    "grounding_score": 1.0,
                    "supported_claim_ratio": 1.0,
                    "unsupported_claim_ratio": 0.0,
                    "is_insufficient_evidence": True,
                },
                "evidence_quality": "Low",
                "reasoning_mode": reasoning_mode,
                "hop_count": hop_count,
                "subquery_count": subquery_count,
                "evidence_sufficiency": evidence_sufficiency,
                "conflict_detected": conflict_detected,
                "conflicts": retrieval_res.get("conflicts", []),
                "table_evidence": table_evidence,
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "request_id": request_id,
                "message_id": msg_id,
                "cache_hit": False,
            }

        # Stage [7] GEMINI CALL START
        print(f"🔹 [STAGE 7] GEMINI CALL START: model={active_model}, context_chars={len(context)}, question='{request.question[:60]}...'")

        # Generate Gemini answer via ModelProvider with Output Privacy Guard
        t_gen_start = time.perf_counter()
        gemini_provider = GeminiModelProvider()
        answer = gemini_provider.generate_response(
            context,
            request.question,
            user_id=str(user_id),
        )
        gen_ms = (time.perf_counter() - t_gen_start) * 1000

        # Validate citations and compute grounding
        validated_answer, validated_citations = SourceCitationManager.validate_citations(
            answer, raw_citations, retrieval_res.get("top_chunks", [])
        )
        grounding_eval = DeterministicGroundingEvaluator.evaluate(
            request.question,
            retrieval_res.get("top_chunks", []),
            validated_answer,
            validated_citations,
        )

        total_ms = (time.perf_counter() - t_req_start) * 1000

        # Stage [8] GEMINI RESPONSE RECEIVED
        print(f"🔹 [STAGE 8] GEMINI RESPONSE RECEIVED: response_status=200, elapsed={gen_ms/1000:.2f}s, answer_chars={len(validated_answer) if validated_answer else 0}")

        # Stage [9] RESPONSE PARSED
        print(f"🔹 [STAGE 9] RESPONSE PARSED: parsed length={len(validated_answer) if validated_answer else 0} chars, sample='{str(validated_answer)[:80]}...'")

        # Save assistant answer to conversation
        msg_id = save_message(conv_id, "assistant", validated_answer)
        touch_conversation(conv_id, current_user["user_id"])

        # Cache response
        if CACHE_ENABLED:
            set_cached_response(
                user_id=current_user["user_id"],
                cache_key=cache_key,
                normalized_query=normalized_query,
                doc_fingerprint=doc_fingerprint,
                model=active_model,
                answer=validated_answer,
                citations=validated_citations,
                grounding=grounding_eval,
                conversation_id=conv_id,
                ttl_seconds=CACHE_TTL_SECONDS,
            )

        # Record telemetry
        record_ai_metric(
            request_id=request_id,
            user_id=current_user["user_id"],
            conversation_id=conv_id,
            query_type=strategy_info.get("query_type", "document_rag"),
            optimizer_strategy=strategy_info.get("complexity", "hybrid"),
            retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
            chroma_ms=retrieval_timings.get("semantic_search_ms"),
            bm25_ms=retrieval_timings.get("bm25_ms"),
            cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
            compression_ms=retrieval_timings.get("compression_ms"),
            generation_ms=gen_ms,
            total_ms=total_ms,
            context_tokens=len(context.split()),
            output_tokens=len(validated_answer.split()),
            citation_count=len(validated_citations),
            grounding_score=grounding_eval.get("grounding_score"),
            model=active_model,
            streaming=0,
            cache_hit=0,
            status="success",
            reasoning_mode=reasoning_mode,
            hop_count=hop_count,
            subquery_count=subquery_count,
            evidence_sufficiency=evidence_sufficiency,
            conflict_detected=1 if conflict_detected else 0,
            table_retrieval_used=1 if table_evidence else 0,
            reasoning_latency=retrieval_timings.get("reasoning_ms", 0.0),
        )

        # Stage [10] CHAT SUCCESS
        print(f"✅ [STAGE 10] CHAT SUCCESS: HTTP 200 returned for user_id={user_id}, docs={validated_filenames}, Conv ID={conv_id} in {total_ms:.1f}ms")
        print("=" * 70)

        return {
            "question": request.question,
            "filenames": validated_filenames,
            "sources": validated_filenames if validated_filenames else [],
            "mode": "cloud",
            "answer": validated_answer,
            "response": validated_answer,
            "citations": validated_citations,
            "grounding": {
                "score": grounding_eval["grounding_score"],
                "grounding_score": grounding_eval["grounding_score"],
                "supported_claim_ratio": grounding_eval["supported_claim_ratio"],
                "unsupported_claim_ratio": grounding_eval["unsupported_claim_ratio"],
            },
            "evidence_quality": evidence_quality,
            "reasoning_mode": reasoning_mode,
            "hop_count": hop_count,
            "subquery_count": subquery_count,
            "evidence_sufficiency": evidence_sufficiency,
            "conflict_detected": conflict_detected,
            "conflicts": retrieval_res.get("conflicts", []),
            "table_evidence": table_evidence,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
            "request_id": request_id,
            "message_id": msg_id,
            "cache_hit": False,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("=" * 70)
        print("[ERROR] ========== CHAT EXCEPTION ==========")
        print("Exception Type   :", type(e).__name__)
        print("Exception Message:", str(e))
        print("=" * 70)
        raise HTTPException(
            status_code=503,
            detail="Cloud AI service is temporarily unavailable. Please try again.",
        )


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    t_req_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    try:
        user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", "unknown")
        user_email = current_user.get("email") if isinstance(current_user, dict) else getattr(current_user, "email", "unknown")
        filenames = get_selected_filenames(request)

        # Validate documents if specified
        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        # Resolve or create persistent conversation & save user message
        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        active_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        normalized_query = request.question.strip()
        doc_fingerprint = compute_document_fingerprint(current_user["user_id"], validated_filenames)
        cache_key = compute_cache_key(current_user["user_id"], normalized_query, doc_fingerprint, active_model)

        # ----------------------------------------------------
        # STREAMING RESPONSE CACHE CHECK
        # ----------------------------------------------------
        if CACHE_ENABLED:
            cached = get_cached_response(current_user["user_id"], cache_key)
            if cached:
                def cached_event_stream():
                    # 1. Start event
                    start_payload = {
                        "conversation_id": conv_id,
                        "conversation_title": conv_title,
                        "filenames": validated_filenames,
                        "mode": "cloud",
                        "request_id": request_id,
                        "cache_hit": True,
                    }
                    yield f"event: start\ndata: {json.dumps(start_payload)}\n\n"

                    # 2. Token payload
                    yield f"event: token\ndata: {json.dumps({'text': cached['answer']})}\n\n"

                    # 3. Persist message
                    msg_id = save_message(conv_id, "assistant", cached["answer"])
                    touch_conversation(conv_id, current_user["user_id"])

                    # 4. Complete payload
                    total_ms = (time.perf_counter() - t_req_start) * 1000
                    complete_payload = {
                        "conversation_id": conv_id,
                        "conversation_title": conv_title,
                        "final_text": cached["answer"],
                        "citations": cached.get("citations", []),
                        "grounding": cached.get("grounding") or {
                            "score": 1.0,
                            "grounding_score": 1.0,
                            "supported_claim_ratio": 1.0,
                            "unsupported_claim_ratio": 0.0,
                        },
                        "status": "complete",
                        "request_id": request_id,
                        "message_id": msg_id,
                        "cache_hit": True,
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_payload)}\n\n"

                    record_ai_metric(
                        request_id=request_id,
                        user_id=current_user["user_id"],
                        conversation_id=conv_id,
                        query_type="cached",
                        optimizer_strategy="cache_hit",
                        retrieval_ms=0.0,
                        ttft_ms=total_ms,
                        total_ms=total_ms,
                        citation_count=len(cached.get("citations", [])),
                        grounding_score=cached.get("grounding", {}).get("grounding_score", 1.0) if cached.get("grounding") else 1.0,
                        model=active_model,
                        streaming=1,
                        cache_hit=1,
                        status="success",
                    )

                return StreamingResponse(
                    cached_event_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                        "X-Conversation-Id": str(conv_id),
                        "X-Conversation-Title": conv_title,
                        "X-Request-Id": request_id,
                    },
                )

        # ----------------------------------------------------
        # LIVE GENERATION STREAM (Cache Miss)
        # ----------------------------------------------------
        def event_stream():
            accumulated_text = ""
            ttft_ms = None
            retrieval_timings = {}
            strategy_info = {}
            stream_started = time.perf_counter()

            try:
                # 1. Start event
                start_payload = {
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "filenames": validated_filenames,
                    "mode": "cloud",
                    "request_id": request_id,
                }
                yield f"event: start\ndata: {json.dumps(start_payload)}\n\n"

                # 2. General AI (No document selected)
                if not validated_filenames:
                    print(f"🌐 [STREAM] Executing General AI Chat Stream (user_id={user_id}, conv_id={conv_id})...")
                    query_type = "general_ai"
                    optimizer_strat = "direct_generation"
                    for chunk in ask_gemini_general_stream(request.question):
                        # JWT Expiration Check during stream
                        if current_user.get("exp") and time.time() >= float(current_user["exp"]):
                            print(f"🔒 [STREAM AUTH] Token expired during stream for user {user_id}")
                            yield f"event: error\ndata: {json.dumps({'detail': 'Authentication token expired during stream.', 'code': 'TOKEN_EXPIRED'})}\n\n"
                            return
                        if chunk:
                            if ttft_ms is None:
                                ttft_ms = (time.perf_counter() - t_req_start) * 1000
                            accumulated_text += chunk
                            yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"

                # 3. Document Grounded RAG
                else:
                    print(f"📚 [STREAM] Executing Document RAG / Multi-Hop Stream (user_id={user_id}, docs={validated_filenames})...")
                    retrieval_res = MultiHopReasoningService.execute_multi_hop_pipeline(
                        request.question,
                        validated_filenames,
                        user_id=current_user["user_id"],
                    )
                    context = retrieval_res["formatted_context"]
                    evidence_quality = retrieval_res["evidence_quality"]
                    retrieval_timings = retrieval_res.get("timings", {})
                    strategy_info = retrieval_res.get("strategy", {})
                    query_type = strategy_info.get("query_type", "document_rag") if strategy_info else "document_rag"
                    optimizer_strat = strategy_info.get("complexity", "hybrid") if strategy_info else "hybrid"
                    reasoning_mode = retrieval_res.get("reasoning_mode", "single_pass")
                    hop_count = retrieval_res.get("hop_count", 1)
                    subquery_count = len(retrieval_res.get("subqueries", [request.question]))
                    evidence_sufficiency = retrieval_res.get("evidence_sufficiency", "sufficient")
                    conflict_detected = retrieval_res.get("conflict_detected", False)
                    table_evidence = retrieval_res.get("table_evidence", False)

                    if not context.strip() or evidence_sufficiency == "insufficient":
                        fallback_ans = "I couldn't find sufficient information in the selected document(s) to answer this question."
                        accumulated_text = fallback_ans
                        ttft_ms = (time.perf_counter() - t_req_start) * 1000
                        yield f"event: token\ndata: {json.dumps({'text': fallback_ans})}\n\n"
                    else:
                        for chunk in ask_gemini_stream(context, request.question):
                            # JWT Expiration Check during stream
                            if current_user.get("exp") and time.time() >= float(current_user["exp"]):
                                print(f"🔒 [STREAM AUTH] Token expired during stream for user {user_id}")
                                yield f"event: error\ndata: {json.dumps({'detail': 'Authentication token expired during stream.', 'code': 'TOKEN_EXPIRED'})}\n\n"
                                return
                            if chunk:
                                if ttft_ms is None:
                                    ttft_ms = (time.perf_counter() - t_req_start) * 1000
                                accumulated_text += chunk
                                yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"

                # 4. Output Privacy Guard sanitization & Citation validation
                safe_text, was_redacted, reason = OutputPrivacyGuard.guard(accumulated_text)
                if was_redacted:
                    print(f"🛡️ [STREAM PRIVACY] Output sanitized: {reason}")

                if validated_filenames and 'retrieval_res' in locals() and retrieval_res.get("top_chunks"):
                    raw_citations = retrieval_res.get("citations", [])
                    validated_text, validated_citations = SourceCitationManager.validate_citations(
                        safe_text, raw_citations, retrieval_res.get("top_chunks", [])
                    )
                    grounding_eval = DeterministicGroundingEvaluator.evaluate(
                        request.question,
                        retrieval_res.get("top_chunks", []),
                        validated_text,
                        validated_citations,
                    )
                else:
                    validated_text = safe_text
                    validated_citations = []
                    grounding_eval = {
                        "score": 1.0,
                        "grounding_score": 1.0,
                        "supported_claim_ratio": 1.0,
                        "unsupported_claim_ratio": 0.0,
                    }

                # 5. Persist final assistant response to SQLite
                msg_id = save_message(conv_id, "assistant", validated_text)
                touch_conversation(conv_id, current_user["user_id"])

                total_ms = (time.perf_counter() - t_req_start) * 1000
                gen_ms = total_ms - (retrieval_timings.get("total_retrieval_ms") or 0.0)

                # 6. Save in response cache (only on successful completed stream)
                if CACHE_ENABLED and validated_text.strip():
                    set_cached_response(
                        user_id=current_user["user_id"],
                        cache_key=cache_key,
                        normalized_query=normalized_query,
                        doc_fingerprint=doc_fingerprint,
                        model=active_model,
                        answer=validated_text,
                        citations=validated_citations,
                        grounding=grounding_eval,
                        conversation_id=conv_id,
                        ttl_seconds=CACHE_TTL_SECONDS,
                    )

                # 7. Record Telemetry
                record_ai_metric(
                    request_id=request_id,
                    user_id=current_user["user_id"],
                    conversation_id=conv_id,
                    query_type=query_type,
                    optimizer_strategy=optimizer_strat,
                    retrieval_ms=retrieval_timings.get("total_retrieval_ms"),
                    chroma_ms=retrieval_timings.get("semantic_search_ms"),
                    bm25_ms=retrieval_timings.get("bm25_ms"),
                    cross_encoder_ms=retrieval_timings.get("cross_encoder_ms"),
                    compression_ms=retrieval_timings.get("compression_ms"),
                    ttft_ms=ttft_ms,
                    generation_ms=gen_ms,
                    total_ms=total_ms,
                    context_tokens=len(context.split()) if ('context' in locals() and context) else 0,
                    output_tokens=len(validated_text.split()),
                    citation_count=len(validated_citations),
                    grounding_score=grounding_eval.get("grounding_score", 1.0),
                    model=active_model,
                    streaming=1,
                    cache_hit=0,
                    status="success",
                    reasoning_mode=reasoning_mode if 'reasoning_mode' in locals() else "single_pass",
                    hop_count=hop_count if 'hop_count' in locals() else 1,
                    subquery_count=subquery_count if 'subquery_count' in locals() else 1,
                    evidence_sufficiency=evidence_sufficiency if 'evidence_sufficiency' in locals() else "sufficient",
                    conflict_detected=1 if ('conflict_detected' in locals() and conflict_detected) else 0,
                    table_retrieval_used=1 if ('table_evidence' in locals() and table_evidence) else 0,
                    reasoning_latency=retrieval_timings.get("reasoning_ms", 0.0),
                )

                # 8. Complete event
                complete_payload = {
                    "conversation_id": conv_id,
                    "conversation_title": conv_title,
                    "final_text": validated_text,
                    "citations": validated_citations,
                    "grounding": {
                        "score": grounding_eval.get("grounding_score", 1.0),
                        "grounding_score": grounding_eval.get("grounding_score", 1.0),
                        "supported_claim_ratio": grounding_eval.get("supported_claim_ratio", 1.0),
                        "unsupported_claim_ratio": grounding_eval.get("unsupported_claim_ratio", 0.0),
                    },
                    "reasoning_mode": reasoning_mode if 'reasoning_mode' in locals() else "single_pass",
                    "hop_count": hop_count if 'hop_count' in locals() else 1,
                    "evidence_sufficiency": evidence_sufficiency if 'evidence_sufficiency' in locals() else "sufficient",
                    "conflict_detected": conflict_detected if 'conflict_detected' in locals() else False,
                    "conflicts": retrieval_res.get("conflicts", []) if 'retrieval_res' in locals() else [],
                    "table_evidence": table_evidence if 'table_evidence' in locals() else False,
                    "status": "complete",
                    "request_id": request_id,
                    "message_id": msg_id,
                    "cache_hit": False,
                }
                yield f"event: complete\ndata: {json.dumps(complete_payload)}\n\n"

            except (GeneratorExit, BaseException) as ge:
                if isinstance(ge, (GeneratorExit,)):
                    print(f"⚠️ [STREAM DISCONNECT] Client disconnected prematurely (user={user_id}, conv={conv_id})")
                    total_ms = (time.perf_counter() - t_req_start) * 1000
                    try:
                        record_ai_metric(
                            request_id=request_id,
                            user_id=current_user["user_id"],
                            conversation_id=conv_id,
                            query_type=query_type if 'query_type' in locals() else "document_rag",
                            optimizer_strategy=optimizer_strat if 'optimizer_strat' in locals() else "hybrid",
                            retrieval_ms=retrieval_timings.get("total_retrieval_ms") if 'retrieval_timings' in locals() else 0.0,
                            ttft_ms=ttft_ms,
                            total_ms=total_ms,
                            status="aborted",
                            streaming=1,
                            cache_hit=0,
                            model=active_model,
                        )
                    except Exception:
                        pass
                    return

                print(f"❌ [STREAM ERROR] {type(ge).__name__}: {str(ge)}")
                error_msg = "Cloud AI service is temporarily unavailable. Please try again."
                if accumulated_text:
                    try:
                        safe_text, _, _ = OutputPrivacyGuard.guard(accumulated_text)
                        save_message(conv_id, "assistant", safe_text)
                        touch_conversation(conv_id, current_user["user_id"])
                    except Exception:
                        pass
                try:
                    yield f"event: error\ndata: {json.dumps({'detail': error_msg})}\n\n"
                except (GeneratorExit, BrokenPipeError, ConnectionResetError):
                    return

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Conversation-Id": str(conv_id),
                "X-Conversation-Title": conv_title,
                "X-Request-Id": request_id,
            },
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ [CHAT STREAM ROUTE ERROR]:", str(e))
        raise HTTPException(
            status_code=503,
            detail="Cloud AI streaming is temporarily unavailable. Please try again.",
        )


@router.post("/local-chat-normal")
def local_chat_normal(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    try:
        filenames = get_selected_filenames(request)

        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        if not validated_filenames:
            answer = ask_local("", request.question)
            save_message(conv_id, "assistant", answer)
            touch_conversation(conv_id, current_user["user_id"])
            return {
                "question": request.question,
                "filenames": [],
                "mode": "local",
                "answer": answer,
                "conversation_id": conv_id,
                "conversation_title": conv_title,
            }

        retrieval_res = MultiHopReasoningService.execute_multi_hop_pipeline(
            request.question,
            validated_filenames,
            user_id=current_user["user_id"],
        )
        context = retrieval_res["formatted_context"]
        evidence_quality = retrieval_res["evidence_quality"]

        if not context.strip():
            fallback_ans = "I couldn't find relevant information in the selected document(s)."
            save_message(conv_id, "assistant", fallback_ans)
            touch_conversation(conv_id, current_user["user_id"])
            return {
                "question": request.question,
                "filenames": validated_filenames,
                "mode": "local",
                "answer": fallback_ans,
                "evidence_quality": "Low",
                "conversation_id": conv_id,
                "conversation_title": conv_title,
            }

        local_provider = LocalQwenModelProvider()
        answer = local_provider.generate_response(
            context,
            request.question,
            user_id=str(current_user["user_id"]),
        )

        save_message(conv_id, "assistant", answer)
        touch_conversation(conv_id, current_user["user_id"])

        return {
            "question": request.question,
            "filenames": validated_filenames,
            "sources": validated_filenames if validated_filenames else [],
            "mode": "local",
            "answer": answer,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
            "reasoning_mode": retrieval_res.get("reasoning_mode", "single_pass"),
            "hop_count": retrieval_res.get("hop_count", 1),
            "evidence_sufficiency": retrieval_res.get("evidence_sufficiency", "sufficient"),
            "conflict_detected": retrieval_res.get("conflict_detected", False),
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        err_str = str(e)
        print(f"❌ Local Chat Error ({type(e).__name__}): {err_str}")
        if any(w in err_str.lower() for w in ("refused", "connect", "11434", "unavailable", "timeout")):
            detail_msg = "Local AI (Ollama) service is unreachable. Please ensure Ollama is running or switch to Cloud mode in Settings."
            status_c = 503
        else:
            detail_msg = "Local chat generation failed."
            status_c = 500
        raise HTTPException(
            status_code=status_c,
            detail=detail_msg,
        )


@router.post("/local-chat")
def local_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    try:
        filenames = get_selected_filenames(request)

        if filenames:
            validated_filenames = validate_user_documents(
                filenames,
                current_user["user_id"],
            )
        else:
            validated_filenames = []

        conv_id, conv_title = resolve_or_create_conversation(
            current_user["user_id"],
            request.conversation_id,
            request.question,
            validated_filenames,
        )

        if not validated_filenames:
            stream_gen = stream_local("", request.question)
        else:
            retrieval_res = MultiHopReasoningService.execute_multi_hop_pipeline(
                request.question,
                validated_filenames,
                user_id=current_user["user_id"],
            )
            context = retrieval_res["formatted_context"]
            evidence_quality = retrieval_res["evidence_quality"]
            if not context.strip():
                fallback_ans = "I couldn't find relevant information in the selected document(s)."
                save_message(conv_id, "assistant", fallback_ans)
                touch_conversation(conv_id, current_user["user_id"])
                return StreamingResponse(
                    iter([fallback_ans]),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "X-Conversation-Id": str(conv_id),
                        "X-Conversation-Title": conv_title,
                        "X-Evidence-Quality": "Low",
                    },
                )
            stream_gen = stream_local(context, request.question)

        def stream_with_persistence():
            full_chunks = []
            try:
                for chunk in stream_gen:
                    full_chunks.append(chunk)
                    yield chunk
            except GeneratorExit:
                print(f"⚠️ [LOCAL STREAM DISCONNECT] Client disconnected from local stream (user_id={current_user['user_id']})")
                return
            finally:
                complete_text = "".join(full_chunks)
                if complete_text.strip():
                    try:
                        save_message(conv_id, "assistant", complete_text)
                        touch_conversation(conv_id, current_user["user_id"])
                    except Exception as persist_err:
                        print("Failed to persist streaming message:", persist_err)

        return StreamingResponse(
            stream_with_persistence(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "X-Conversation-Id": str(conv_id),
                "X-Conversation-Title": conv_title,
            },
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ Local Streaming Chat Error:", str(e))
        return StreamingResponse(
            iter(["❌ Local AI request failed."]),
            media_type="text/plain; charset=utf-8",
        )


@router.post("/local-warmup")
def local_warmup(
    current_user=Depends(get_current_user),
):
    try:
        print("=" * 70)
        print("🔥 LOCAL AI WARM-UP REQUEST")
        print("=" * 70)
        result = warmup_local_model()
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print("❌ Local Warm-up Error:", str(e))
        return {
            "status": "error",
            "error": "Local model warm-up failed.",
        }
