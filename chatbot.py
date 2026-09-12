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

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set in the .env file"
    )


# --------------------------------------------------
# Configure Gemini
# --------------------------------------------------

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# --------------------------------------------------
# Gemini model
# --------------------------------------------------

GEMINI_MODEL = "gemini-3.6-flash"

# --------------------------------------------------
# Gemini transient-error retry settings
# --------------------------------------------------

# Retry only transient 503/high-demand errors.
# This applies to normal chat calls, not document-summary's
# dedicated two-call workflow.
GEMINI_MAX_ATTEMPTS = 2
GEMINI_RETRY_DELAY_SECONDS = 2



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
        r"\b(?:in|with|using)\s+(\d{1,2})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",

        r"\b(?:give|provide|list|tell|summarize|explain)"
        r"\s+(?:me\s+)?(\d{1,2})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",

        r"\b(\d{1,2})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",
    ]

    for pattern in numeric_patterns:
        match = re.search(pattern, text)

        if match:
            count = int(match.group(1))

            if 1 <= count <= 20:
                return count

    word_numbers = "|".join(NUMBER_WORDS.keys())

    word_patterns = [
        rf"\b(?:in|with|using)\s+({word_numbers})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",

        rf"\b(?:give|provide|list|tell|summarize|explain)"
        rf"\s+(?:me\s+)?({word_numbers})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",

        rf"\b({word_numbers})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",
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
    """
    Make the final answer contain exactly the requested number
    of bullets when the user explicitly asks for N points.

    Gemini is still responsible for selecting the content.
    This function only removes headings/extra sections and
    groups content into the requested number of bullets.
    """

    if not text or not text.strip() or not requested_count:
        return text.strip() if text else ""

    text = text.strip()

    # Remove markdown headings.
    text = re.sub(
        r"(?m)^\s{0,3}#{1,6}\s+.*?\s*$",
        "",
        text
    )

    # Remove common section labels that Gemini may generate.
    text = re.sub(
        r"(?mi)^\s*(?:what this document is about|"
        r"main topics|important details|"
        r"important findings and conclusions|"
        r"in simple words|summary|conclusion)\s*:?\s*$",
        "",
        text
    )

    # Extract bullet/numbered lines.
    raw_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    bullet_items = []

    for line in raw_lines:
        match = re.match(
            r"^(?:[-*•]|\d+[.)])\s+(.*)$",
            line
        )

        if match:
            item = match.group(1).strip()

            if item:
                bullet_items.append(item)

    # If Gemini already returned enough structured bullets,
    # use the requested number directly.
    if len(bullet_items) >= requested_count:

        selected = bullet_items[:requested_count]

        return "\n".join(
            f"- {item}"
            for item in selected
        )

    # If Gemini returned fewer bullets, split paragraph-style
    # content into sentences and build the requested number.
    clean_text = " ".join(raw_lines)

    # Remove duplicated whitespace.
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not clean_text:
        return text

    # Sentence extraction.
    sentences = re.split(
        r"(?<=[.!?])\s+",
        clean_text
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

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

            return "\n".join(
                f"- {group}"
                for group in groups
            )

    # Final fallback: ask Gemini's already-generated text to be
    # divided into exactly N parts without adding information.
    words = clean_text.split()

    if len(words) >= requested_count:

        groups = []

        total_words = len(words)

        for index in range(requested_count):
            start = round(index * total_words / requested_count)
            end = round(
                (index + 1) * total_words / requested_count
            )

            group = " ".join(
                words[start:end]
            ).strip()

            if group:
                groups.append(group)

        if len(groups) == requested_count:

            return "\n".join(
                f"- {group}"
                for group in groups
            )

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


# --------------------------------------------------
# Ask Gemini - General Chat
# --------------------------------------------------

def ask_gemini_general(question):

    if not question or not question.strip():
        return "Please enter a question."

    requested_count = extract_requested_count(question)

    count_instruction = build_count_instruction(
        requested_count
    )

    prompt = f"""
You are NexusAI, a helpful AI assistant.

Answer the user's question directly and clearly.

The user has not selected a document, so do not claim
to use or quote an uploaded document.

Do not expose internal reasoning.
Return only the final answer.

{count_instruction}

USER QUESTION:
{question.strip()}

Provide only the final answer.
"""

    # Short factual questions need very little output.
    # A smaller generation budget can reduce response latency while
    # leaving normal questions at the existing budget.
    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = (
        256
        if is_fast_factual
        else 1500
    )

    if is_fast_factual:
        print(
            "⚡ FAST FACTUAL GENERATION MODE"
        )
        print(
            "Max output tokens:",
            max_output_tokens
        )

    last_error = None

    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):

        try:

            print(
                f"☁️ Gemini general chat attempt "
                f"{attempt}/{GEMINI_MAX_ATTEMPTS}"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1500,
                ),
            )

            response_text = getattr(
                response,
                "text",
                None
            ) or ""

            if not response_text.strip():
                return "I couldn't generate an answer at this time."

            if requested_count:
                response_text = normalize_requested_points(
                    response_text,
                    requested_count
                )

            return response_text.strip()

        except Exception as e:

            last_error = e
            error_text = str(e)

            print(
                "❌ Gemini General Chat Error:",
                error_text
            )

            # Retry only transient 503/high-demand errors.
            if (
                "503" not in error_text
                and "UNAVAILABLE" not in error_text.upper()
            ):
                break

            if attempt < GEMINI_MAX_ATTEMPTS:

                print(
                    f"⏳ Gemini temporarily unavailable. "
                    f"Retrying in {GEMINI_RETRY_DELAY_SECONDS} seconds..."
                )

                time.sleep(
                    GEMINI_RETRY_DELAY_SECONDS
                )

    return (
        "Sorry, I was unable to generate an answer "
        "at this time."
    )


# --------------------------------------------------
# Ask Gemini - Document Grounded Chat
# --------------------------------------------------

def ask_gemini(context, question):

    if not context or not context.strip():
        return (
            "I couldn't find that information in the "
            "uploaded document."
        )

    requested_count = extract_requested_count(question)

    # Short factual questions need very little output.
    is_fast_factual = (
        question.lower().strip().startswith("how many ")
        or question.lower().strip().startswith("how much ")
    ) and len(question.strip().split()) <= 12 and not requested_count

    max_output_tokens = 512 if is_fast_factual else 1500

    if is_fast_factual:
        print("⚡ FAST FACTUAL GENERATION MODE")
        print("Max output tokens:", max_output_tokens)

    count_instruction = build_count_instruction(
        requested_count
    )

    # --------------------------------------------------
    # Fast factual path
    # --------------------------------------------------
    # For short "how many/how much" questions, use a very
    # small, direct prompt. The normal long instruction set
    # contains a fallback rule that can cause Gemini to choose
    # the fallback even when the answer is visibly present.
    # This path asks Gemini only to extract the supported fact.
    if is_fast_factual:
        prompt = f"""DOCUMENT:
{context}

QUESTION:
{question}

The answer to this question is explicitly supported by the
document above. Find the exact answer in the document.
Return only the direct answer. Do not refuse, do not say the
information is missing, and do not use outside knowledge.
If the document gives a number, return that number and the
corresponding item(s) in one short sentence."""

        system_instruction = (
            "Answer the question using only the supplied document. "
            "For a short factual question, extract the explicitly "
            "stated fact and answer directly. Never claim the fact "
            "is missing when it is present in the document."
        )
    else:
        prompt = f"""
You are NexusAI, an AI assistant that answers questions
using the selected uploaded document.

Understand the user's MEANING and INTENT, not merely
the exact words they used.

IMPORTANT RULES:

1. Answer ONLY using information supported by the
   DOCUMENT CONTEXT.

2. Understand natural language variations.

3. The user may ask conversationally, indirectly,
   briefly, or using imperfect English.

4. For overview, summary, purpose, explanation, or
   important-point questions, synthesize relevant
   information from the provided context.

5. Do NOT require predefined question formats.

6. Do NOT use outside knowledge.

7. Do NOT invent, assume, or guess.

8. If the requested information is not supported,
   reply exactly:

   "I couldn't find that information in the uploaded document."

9. Answer the actual question directly.

10. Keep answers concise unless the user explicitly
    asks for more detail.

11. Use bullet points when multiple items are requested.

12. For comparison questions, clearly identify supported
    similarities and differences.

13. For follow-up questions, use the available document
    context and conversation intent.

14. Never mention chunks, embeddings, vector databases,
    retrieval, prompts, or internal processing.

15. Do not expose internal reasoning.

16. Return only the final answer.

17. Complete the answer.

18. Do not create unnecessary sections.

19. For comparison questions, normally provide:
    - 2 to 3 similarities
    - 2 to 3 differences
    - 1 short conclusion

20. Do not provide long summaries of each document.

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
            "You are NexusAI. Answer using only information supported "
            "by the selected uploaded document. Do not invent facts."
        )

    last_error = None

    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):

        try:

            print(
                f"☁️ Gemini document chat attempt "
                f"{attempt}/{GEMINI_MAX_ATTEMPTS}"
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=max_output_tokens,
                    system_instruction=system_instruction,
                ),
            )

            # --------------------------------------------------
            # Gemini diagnostic logging
            # --------------------------------------------------

            print("=" * 70)
            print("GEMINI DEBUG")
            print("Model:", GEMINI_MODEL)
            print(
                "Requested point count:",
                requested_count
            )

            try:

                if response.candidates:

                    candidate = response.candidates[0]

                    print(
                        "Finish reason:",
                        candidate.finish_reason
                    )

                else:

                    print(
                        "Finish reason: No candidates"
                    )

            except Exception as debug_error:

                print(
                    "Finish reason unavailable:",
                    str(debug_error)
                )

            response_text = getattr(
                response,
                "text",
                None
            ) or ""

            print(
                "Raw response text length:",
                len(response_text)
            )

            print(
                "Raw response:",
                response_text
            )

            # --------------------------------------------------
            # Enforce requested point count
            # --------------------------------------------------

            if requested_count and response_text.strip():

                response_text = normalize_requested_points(
                    response_text,
                    requested_count
                )

                print(
                    "Normalized response:",
                    response_text
                )

            print("=" * 70)

            if not response_text.strip():

                return (
                    "I couldn't generate an answer from "
                    "the uploaded document."
                )

            return response_text.strip()

        except Exception as e:

            last_error = e
            error_text = str(e)

            print(
                "❌ Gemini Error:",
                error_text
            )

            # Retry only transient 503/high-demand errors.
            if (
                "503" not in error_text
                and "UNAVAILABLE" not in error_text.upper()
            ):
                break

            if attempt < GEMINI_MAX_ATTEMPTS:

                print(
                    f"⏳ Gemini temporarily unavailable. "
                    f"Retrying in {GEMINI_RETRY_DELAY_SECONDS} seconds..."
                )

                time.sleep(
                    GEMINI_RETRY_DELAY_SECONDS
                )

    return (
        "Sorry, I was unable to generate an answer "
        "at this time."
    )
