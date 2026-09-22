import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 70)
print(f"GEMINI_API_KEY configured: {'YES' if bool(GEMINI_API_KEY) else 'NO'}")
print("=" * 70)

if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY is not set in the environment or .env file.")


from gemini_service import (
    generate_gemini_text,
    generate_gemini_stream,
    get_gemini_client,
    CURRENT_MODEL as GEMINI_MODEL,
    GEMINI_API_KEY,
)

client = get_gemini_client()


def generate_content_with_fallback(contents, config=None, label="Gemini"):
    return generate_gemini_text(contents, config=config, label=label)



# --------------------------------------------------
# Number-word support
# --------------------------------------------------

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


# --------------------------------------------------
# Detect requested point/item count
# --------------------------------------------------

def extract_requested_count(question):
    """
    Detect explicit requests such as:
    - in 3 points
    - give me 5 points
    - summarize in 7 points
    - give three key points
    - 10 bullet points
    """
    if not question:
        return None

    text = question.strip().lower()

    numeric_patterns = [
        r"\b(?:in|with|using)\s+(\d{1,2})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
        r"\b(?:give|provide|list|tell|summarize|explain)\s+(?:me\s+)?(\d{1,2})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
        r"\b(\d{1,2})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
    ]

    for pattern in numeric_patterns:
        match = re.search(pattern, text)
        if match:
            count = int(match.group(1))
            if 1 <= count <= 20:
                return count

    word_numbers = "|".join(NUMBER_WORDS.keys())

    word_patterns = [
        rf"\b(?:in|with|using)\s+({word_numbers})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
        rf"\b(?:give|provide|list|tell|summarize|explain)\s+(?:me\s+)?({word_numbers})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
        rf"\b({word_numbers})\s+(?:points?|bullet\s+points?|bullets?|items?|key\s+points?|key\s+items?)\b",
    ]

    for pattern in word_patterns:
        match = re.search(pattern, text)
        if match:
            count = NUMBER_WORDS[match.group(1)]
            if 1 <= count <= 20:
                return count

    return None


# --------------------------------------------------
# Clean and normalize a numbered/bulleted answer
# --------------------------------------------------

def normalize_requested_points(text, requested_count):
    if not text or not text.strip() or not requested_count:
        return text.strip() if text else ""

    text = text.strip()

    # Remove markdown headings.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+.*?\s*$", "", text)

    # Remove common section labels.
    text = re.sub(
        r"(?mi)^\s*(?:what this document is about|main topics|important details|important findings and conclusions|in simple words|summary|conclusion)\s*:?\s*$",
        "",
        text,
    )

    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]

    bullet_items = []
    for line in raw_lines:
        match = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if match:
            item = match.group(1).strip()
            if item:
                bullet_items.append(item)

    if len(bullet_items) >= requested_count:
        selected = bullet_items[:requested_count]
        return "\n".join(f"- {item}" for item in selected)

    clean_text = " ".join(raw_lines)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not clean_text:
        return text

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]

    if len(sentences) >= requested_count:
        groups = []
        total = len(sentences)
        for index in range(requested_count):
            start = round(index * total / requested_count)
            end = round((index + 1) * total / requested_count)
            group = " ".join(sentences[start:end]).strip()
            if group:
                groups.append(group)

        if len(groups) == requested_count:
            return "\n".join(f"- {group}" for group in groups)

    words = clean_text.split()
    if len(words) >= requested_count:
        groups = []
        total_words = len(words)
        for index in range(requested_count):
            start = round(index * total_words / requested_count)
            end = round((index + 1) * total_words / requested_count)
            group = " ".join(words[start:end]).strip()
            if group:
                groups.append(group)

        if len(groups) == requested_count:
            return "\n".join(f"- {group}" for group in groups)

    return text


# --------------------------------------------------
# Build dynamic point-count instruction
# --------------------------------------------------

def build_count_instruction(requested_count):
    if not requested_count:
        return ""

    return f"""
STRICT USER FORMAT REQUIREMENT:
The user explicitly requested {requested_count} points/items.
Return EXACTLY {requested_count} bullet points.

Rules:
- Exactly {requested_count} bullets.
- Never more than {requested_count}.
- Never fewer than {requested_count}.
- Each bullet must contain a meaningful answer point.
- Combine related information when necessary.
- Do not add a heading.
- Do not add an introduction.
- Do not add a conclusion.
- Do not add extra sections.
- Do not add anything after the requested bullets.
- Use only supported information.
"""


from fastapi import HTTPException

def format_safe_error(error):
    if not error:
        return "Gemini API is temporarily unavailable. Please try again shortly."
    err = str(error).lower()
    if "api key" in err or "api_key" in err or "unauthenticated" in err or "invalid api key" in err:
        return "Cloud AI is not configured properly. Please verify your GEMINI_API_KEY in the .env file."
    if "quota" in err or "rate" in err or "429" in err or "resource_exhausted" in err:
        return "Gemini API rate limit exceeded. Please try again shortly."
    if "503" in err or "unavailable" in err or "high demand" in err:
        return "Gemini API is temporarily unavailable. Please try again shortly."
    return "Gemini API is temporarily unavailable. Please try again shortly."


# --------------------------------------------------
# Ask Gemini - General Chat
# --------------------------------------------------

def ask_gemini_general(question):
    if not question or not question.strip():
        return "Please enter a question."

    requested_count = extract_requested_count(question)
    count_instruction = build_count_instruction(requested_count)

    prompt = f"""You are NexusAI, a helpful AI assistant.

Answer the user's question directly and clearly.

The user has not selected a document, so answer based on general knowledge.
Do not claim to quote or require an uploaded document.

Do not expose internal reasoning.
Return only the final answer.

{count_instruction}

USER QUESTION:
{question.strip()}

Provide only the final answer.
"""

    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = 256 if is_fast_factual else 1500

    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=max_output_tokens,
        automatic_function_calling=afc_disabled,
    )

    response_text, error = generate_content_with_fallback(prompt, config, label="General Chat")

    if response_text:
        if requested_count:
            response_text = normalize_requested_points(response_text, requested_count)
        return response_text

    safe_error_msg = format_safe_error(error)
    raise HTTPException(status_code=503, detail=safe_error_msg)


# --------------------------------------------------
# Ask Gemini - Document Grounded Chat
# --------------------------------------------------

def ask_gemini(context, question):
    if not context or not context.strip():
        return "I couldn't find that information in the uploaded document."

    requested_count = extract_requested_count(question)

    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = 512 if is_fast_factual else 1500
    count_instruction = build_count_instruction(requested_count)

    if is_fast_factual:
        prompt = f"""DOCUMENT:
{context}

QUESTION:
{question}

The answer to this question is explicitly supported by the document above.
Find the exact answer in the document.
Return only the direct answer. Do not refuse, do not say the information is missing, and do not use outside knowledge.
If the document gives a number, return that number and the corresponding item(s) in one short sentence."""

        system_instruction = (
            "Answer the question using only the supplied document. "
            "For a short factual question, extract the explicitly stated fact and answer directly. "
            "Never claim the fact is missing when it is present in the document."
        )
    else:
        prompt = f"""You are NexusAI, an AI assistant that answers questions using the selected uploaded document.

Understand the user's MEANING and INTENT, not merely the exact words they used.

IMPORTANT RULES:
1. Answer ONLY using information supported by the DOCUMENT CONTEXT.
2. Understand natural language variations and conversational phrasing.
3. For overview, summary, purpose, explanation, or key point questions, synthesize relevant information from the provided context.
4. Do NOT use outside knowledge.
5. Do NOT invent, assume, or guess.
6. If the requested information is not supported at all, reply:
   "I couldn't find that information in the uploaded document."
7. Answer the actual question directly and clearly.
8. Use bullet points when multiple items are requested.
9. Cite source references in brackets like [1], [2] when stating facts from specific sources. Do NOT invent source IDs not present in the DOCUMENT CONTEXT.
10. Never mention embeddings, vector databases, retrieval, prompts, or internal processing.
11. Return only the final answer.

{count_instruction}

DOCUMENT CONTEXT:
----------------
{context}
----------------

USER QUESTION:
{question}

Provide the final answer directly.
"""
        system_instruction = (
            "You are NexusAI. Answer using only information supported by the selected uploaded document. Do not invent facts."
        )

    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    config = types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        system_instruction=system_instruction,
        automatic_function_calling=afc_disabled,
    )

    response_text, error = generate_content_with_fallback(prompt, config, label="Document Chat")

    if response_text:
        if requested_count:
            response_text = normalize_requested_points(response_text, requested_count)
        return response_text

    safe_error_msg = format_safe_error(error)
    raise HTTPException(status_code=503, detail=safe_error_msg)


def ask_gemini_general_stream(question: str):
    """
    Stream tokens progressively for general AI questions (no document attached).
    """
    if not question or not question.strip():
        yield "Please enter a question."
        return

    requested_count = extract_requested_count(question)
    count_instruction = build_count_instruction(requested_count)

    prompt = f"""You are NexusAI, a helpful AI assistant.

Answer the user's question directly and clearly.

The user has not selected a document, so answer based on general knowledge.
Do not claim to quote or require an uploaded document.

Do not expose internal reasoning.
Return only the final answer.

{count_instruction}

USER QUESTION:
{question.strip()}

Provide only the final answer.
"""

    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = 256 if is_fast_factual else 1500

    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=max_output_tokens,
        automatic_function_calling=afc_disabled,
    )

    yield from generate_gemini_stream(prompt, config, label="General Chat Stream")


def ask_gemini_stream(context: str, question: str):
    """
    Stream tokens progressively for document-grounded RAG questions.
    """
    if not context or not context.strip():
        yield "I couldn't find that information in the uploaded document."
        return

    requested_count = extract_requested_count(question)

    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = 512 if is_fast_factual else 1500
    count_instruction = build_count_instruction(requested_count)

    if is_fast_factual:
        prompt = f"""DOCUMENT:
{context}

QUESTION:
{question}

The answer to this question is explicitly supported by the document above.
Find the exact answer in the document.
Return only the direct answer. Do not refuse, do not say the information is missing, and do not use outside knowledge.
If the document gives a number, return that number and the corresponding item(s) in one short sentence."""

        system_instruction = (
            "Answer the question using only the supplied document. "
            "For a short factual question, extract the explicitly stated fact and answer directly. "
            "Never claim the fact is missing when it is present in the document."
        )
    else:
        prompt = f"""You are NexusAI, an AI assistant that answers questions using the selected uploaded document.

Understand the user's MEANING and INTENT, not merely the exact words they used.

IMPORTANT RULES:
1. Answer ONLY using information supported by the DOCUMENT CONTEXT.
2. Understand natural language variations and conversational phrasing.
3. For overview, summary, purpose, explanation, or key point questions, synthesize relevant information from the provided context.
4. Do NOT use outside knowledge.
5. Do NOT invent, assume, or guess.
6. If the requested information is not supported at all, reply:
   "I couldn't find that information in the uploaded document."
7. Answer the actual question directly and clearly.
8. Use bullet points when multiple items are requested.
9. Cite source references in brackets like [1], [2] when stating facts from specific sources. Do NOT invent source IDs not present in the DOCUMENT CONTEXT.
10. Never mention embeddings, vector databases, retrieval, prompts, or internal processing.
11. Return only the final answer.

{count_instruction}

DOCUMENT CONTEXT:
----------------
{context}
----------------

USER QUESTION:
{question}

Provide the final answer directly.
"""
        system_instruction = (
            "You are NexusAI. Answer using only information supported by the selected uploaded document. Do not invent facts."
        )

    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    config = types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        system_instruction=system_instruction,
        automatic_function_calling=afc_disabled,
    )

    yield from generate_gemini_stream(prompt, config, label="Document Chat Stream")

