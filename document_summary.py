import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set in the .env file"
    )

client = genai.Client(
    api_key=GEMINI_API_KEY
)

GEMINI_MODEL = "gemini-3.6-flash"

# Hard limit: maximum 2 Gemini calls per document explanation.
MAX_GEMINI_CALLS = 2

# Keep output budgets realistic so thinking does not consume
# the entire generation budget.
FIRST_PASS_MAX_OUTPUT_TOKENS = 2200
FINAL_MAX_OUTPUT_TOKENS = 3200

# Gemini 3.6 Flash supports minimal thinking.
# This leaves more of the output budget for the actual answer.
THINKING_LEVEL = "minimal"


# ============================================================
# DYNAMIC USER FORMAT HELPERS
# ============================================================

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}


def extract_requested_count(question):
    """Detect an explicit user request for N points/items."""

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

    words = "|".join(NUMBER_WORDS.keys())

    word_patterns = [
        rf"\b(?:in|with|using)\s+({words})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",
        rf"\b(?:give|provide|list|tell|summarize|explain)"
        rf"\s+(?:me\s+)?({words})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",
        rf"\b({words})\s+"
        r"(?:points?|bullet\s+points?|bullets?|items?|"
        r"key\s+points?|key\s+items?)\b",
    ]

    for pattern in word_patterns:
        match = re.search(pattern, text)
        if match:
            return NUMBER_WORDS[match.group(1)]

    return None


def build_count_instruction(requested_count):
    if not requested_count:
        return ""

    return f"""
STRICT USER FORMAT REQUIREMENT:

The user explicitly requested {requested_count} points/items.

Return EXACTLY {requested_count} bullet points.

- Never return more or fewer.
- No heading, introduction, conclusion, or extra section.
- Each bullet must contain one meaningful supported point.
- Combine related information when necessary.
- Use only information supported by the supplied document.
"""


def normalize_requested_points(text, requested_count):
    """Final safety layer to return exactly N bullets."""

    if not text or not requested_count:
        return text.strip() if text else ""

    # Remove markdown headings.
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*?$", "", text)

    # Remove common section labels.
    text = re.sub(
        r"(?mi)^\s*(?:what this document is about|main topics|"
        r"important details|important findings and conclusions|"
        r"in simple words|summary|conclusion)\s*:?\s*$",
        "",
        text
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    bullets = []

    for line in lines:
        match = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if match and match.group(1).strip():
            bullets.append(match.group(1).strip())

    if len(bullets) >= requested_count:
        return "\n".join(
            f"- {item}" for item in bullets[:requested_count]
        )

    clean = " ".join(lines)
    clean = re.sub(r"\s+", " ", clean).strip()

    if not clean:
        return text.strip()

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", clean)
        if s.strip()
    ]

    if len(sentences) >= requested_count:
        groups = []
        total = len(sentences)

        for i in range(requested_count):
            start = round(i * total / requested_count)
            end = round((i + 1) * total / requested_count)
            group = " ".join(sentences[start:end]).strip()
            if group:
                groups.append(group)

        if len(groups) == requested_count:
            return "\n".join(
                f"- {group}" for group in groups
            )

    words = clean.split()

    if len(words) >= requested_count:
        groups = []
        total = len(words)

        for i in range(requested_count):
            start = round(i * total / requested_count)
            end = round((i + 1) * total / requested_count)
            group = " ".join(words[start:end]).strip()
            if group:
                groups.append(group)

        if len(groups) == requested_count:
            return "\n".join(
                f"- {group}" for group in groups
            )

    return text.strip()


# ============================================================
# RESPONSE HELPERS
# ============================================================

def extract_response_text(response):
    """
    Safely extract final text from a Gemini response.
    """

    direct_text = getattr(
        response,
        "text",
        None
    )

    if direct_text and str(direct_text).strip():
        return str(direct_text).strip()

    candidates = (
        getattr(
            response,
            "candidates",
            None
        )
        or []
    )

    collected = []

    for candidate in candidates:

        content = getattr(
            candidate,
            "content",
            None
        )

        if not content:
            continue

        parts = (
            getattr(
                content,
                "parts",
                None
            )
            or []
        )

        for part in parts:

            part_text = getattr(
                part,
                "text",
                None
            )

            if part_text and str(
                part_text
            ).strip():

                collected.append(
                    str(part_text).strip()
                )

    return "\n".join(
        collected
    ).strip()


def print_response_debug(
    response,
    label
):
    """
    Print Gemini response metadata so truncation is visible.
    """

    print("=" * 70)
    print(
        f"🔎 GEMINI RESPONSE DEBUG — {label}"
    )

    candidates = (
        getattr(
            response,
            "candidates",
            None
        )
        or []
    )

    print(
        "Candidates:",
        len(candidates)
    )

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        finish_reason = getattr(
            candidate,
            "finish_reason",
            None
        )

        finish_message = getattr(
            candidate,
            "finish_message",
            None
        )

        print(
            f"Candidate {index} finish reason:",
            finish_reason
        )

        if finish_message:

            print(
                f"Candidate {index} finish message:",
                finish_message
            )

    prompt_feedback = getattr(
        response,
        "prompt_feedback",
        None
    )

    if prompt_feedback:

        print(
            "Prompt feedback:",
            prompt_feedback
        )

    print("=" * 70)


# ============================================================
# ONE GEMINI REQUEST
# ============================================================

def generate_gemini_response(
    prompt,
    max_output_tokens,
    label
):
    """
    Make exactly one Gemini request.

    No automatic retries are used because the document-wide
    feature is intentionally limited to two API calls.
    """

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                thinking_config=types.ThinkingConfig(
                    thinking_level=THINKING_LEVEL
                ),
            ),
        )

        print_response_debug(
            response,
            label
        )

        text = extract_response_text(
            response
        )

        print(
            f"📝 {label} extracted text length:",
            len(text)
        )

        if not text:

            print(
                f"⚠️ {label}: Gemini returned no usable text."
            )

        return text

    except Exception as e:

        print(
            f"❌ {label} Gemini error:",
            str(e)
        )

        return ""


# ============================================================
# CALL 1 — FIRST HALF COVERAGE
# ============================================================

def create_first_half_summary(
    first_half,
    filename
):
    """
    Create a compact but information-rich coverage summary
    of the first half.
    """

    print("=" * 70)
    print(
        "🧠 GEMINI CALL 1/2 — FIRST HALF COVERAGE"
    )
    print(
        "Filename:",
        filename
    )
    print(
        "First-half characters:",
        len(first_half)
    )
    print("=" * 70)

    prompt = f"""
You are NexusAI.

Read the FIRST HALF of the document below.

Create a compact factual coverage summary for a second AI
call. Capture the important information, not prose.

Rules:
- Use only the supplied text.
- No outside knowledge.
- Do not invent facts.
- Cover every major topic in this half.
- Preserve important names, dates, numbers, definitions,
  examples, classifications, findings and conclusions.
- Include information from the beginning, middle and end
  of this supplied half.
- Remove repetition.
- Do not mention AI, RAG, retrieval, embeddings, databases,
  prompts, or API processing.

Use this structure:

PURPOSE:
- Overall subject/purpose.

MAJOR TOPICS:
- Topic: important facts.

IMPORTANT FACTS:
- Important names, dates, numbers, definitions, examples.

FINDINGS / CONCLUSIONS:
- Important conclusions or debates.

Do not write an introduction or conclusion about your task.
Return only the coverage summary.

DOCUMENT:
============================================================

{first_half}

============================================================
"""

    return generate_gemini_response(
        prompt,
        FIRST_PASS_MAX_OUTPUT_TOKENS,
        "CALL 1"
    )


# ============================================================
# CALL 2 — FINAL COMPLETE EXPLANATION
# ============================================================

def create_final_explanation(
    first_summary,
    second_half,
    filename,
    question=None
):
    """
    Generate the final user-facing explanation.

    Source A covers the first half.
    Source B is the complete second half.
    """

    print("=" * 70)
    print(
        "🧠 GEMINI CALL 2/2 — FINAL DOCUMENT EXPLANATION"
    )
    print(
        "Filename:",
        filename
    )
    print(
        "First summary characters:",
        len(first_summary)
    )
    print(
        "Second-half characters:",
        len(second_half)
    )

    requested_count = extract_requested_count(question)

    print(
        "Requested point count:",
        requested_count
    )

    count_instruction = build_count_instruction(
        requested_count
    )

    print("=" * 70)

    prompt = f"""
You are NexusAI.

Explain the COMPLETE uploaded document in simple language.

SOURCE A — FIRST HALF COVERAGE:
============================================================

{first_summary}

============================================================

SOURCE B — COMPLETE SECOND HALF:
============================================================

{second_half}

============================================================

Rules:

1. Use only information supported by Source A or Source B.
2. Do not use outside knowledge.
3. Cover the document as a whole.
4. Cover the beginning, middle and end.
5. Do not focus only on Source B.
6. Cover all major topics.
7. Preserve important facts, names, dates, numbers,
   definitions, examples, classifications and conclusions.
8. Explain technical ideas simply.
9. Remove repetition.
10. Do not mention AI, RAG, retrieval, embeddings,
    databases, prompts, Gemini, API calls or internal
    processing.
11. Do not write "(continued)".
12. Never leave a bullet or sentence unfinished.
13. Do not invent information to make the answer longer.

{count_instruction}

If the user explicitly requested a number of points, that
format requirement overrides the normal five-heading format.

When a point count was NOT requested, use EXACTLY these five headings:

### What this document is about

Explain the overall purpose and scope.

### Main topics

Use clear bullet points. Explain every major topic.

### Important details

Give the most useful supporting facts, names, dates,
numbers, definitions, examples and classifications.

### Important findings and conclusions

Give important findings, conclusions, debates or key
takeaways supported by the document.

### In simple words

Explain what the whole document is saying in beginner-friendly
language.

When no point count was requested, keep the answer complete but
concise and aim for roughly 700–1000 words when the document
supports that amount.

Before finishing:
- If a point count was requested, verify the answer has exactly
  the requested number of bullets and no extra sections.
- Otherwise verify all five headings are present.
- In both cases, represent the beginning, middle and end.
- Cover major topics.
- Do not leave bullets or sentences unfinished.
- Do not invent information.

Return ONLY the final explanation.
"""

    return generate_gemini_response(
        prompt,
        FINAL_MAX_OUTPUT_TOKENS,
        "CALL 2"
    )


# ============================================================
# MAIN DOCUMENT EXPLANATION
# ============================================================

def explain_document(
    text,
    filename,
    question=None
):
    """
    Document-wide explanation with a hard maximum of two
    Gemini requests.

    Call 1:
        First half -> compact factual coverage.

    Call 2:
        First-half coverage + complete second half
        -> final explanation.

    Existing /chat, /local-chat and comparison routes are not
    changed by this function.
    """

    if not text or not text.strip():

        return (
            "I couldn't find readable content "
            "in the uploaded document."
        )

    text = text.strip()

    print("=" * 70)
    print(
        "📄 DOCUMENT-WIDE EXPLANATION"
    )
    print(
        "Filename:",
        filename
    )
    print(
        "Text length:",
        len(text)
    )

    print(
        "User question:",
        question
    )

    print(
        "Requested point count:",
        extract_requested_count(question)
    )

    print("=" * 70)

    print(
        "📌 Strategy: TWO Gemini requests"
    )

    print(
        "📌 Maximum Gemini calls:",
        MAX_GEMINI_CALLS
    )

    print(
        "📌 Thinking level:",
        THINKING_LEVEL
    )

    # --------------------------------------------------------
    # LOCAL SPLIT
    # --------------------------------------------------------

    midpoint = len(text) // 2

    first_half = text[:midpoint]
    second_half = text[midpoint:]

    print(
        "📚 First-half characters:",
        len(first_half)
    )

    print(
        "📚 Second-half characters:",
        len(second_half)
    )

    # --------------------------------------------------------
    # CALL 1
    # --------------------------------------------------------

    first_summary = create_first_half_summary(
        first_half,
        filename
    )

    if not first_summary:

        print(
            "❌ Call 1 failed or returned empty text."
        )

        return (
            "I couldn't generate an explanation "
            "from the uploaded document. "
            "Gemini did not return usable content "
            "for the first analysis step."
        )

    print(
        "✅ Call 1 complete."
    )

    print(
        "📝 First-half coverage length:",
        len(first_summary)
    )

    # --------------------------------------------------------
    # CALL 2
    # --------------------------------------------------------

    final_answer = create_final_explanation(
        first_summary,
        second_half,
        filename,
        question
    )

    if not final_answer:

        print(
            "❌ Call 2 failed or returned empty text."
        )

        return (
            "I couldn't generate the final explanation "
            "from the uploaded document. "
            "Gemini did not return usable content "
            "for the final explanation step."
        )

    # --------------------------------------------------------
    # FINAL FORMAT ENFORCEMENT
    # --------------------------------------------------------

    requested_count = extract_requested_count(question)

    if requested_count:
        final_answer = normalize_requested_points(
            final_answer,
            requested_count
        )

        print(
            "🎯 Final requested point count:",
            requested_count
        )

        print(
            "📝 Normalized final response length:",
            len(final_answer)
        )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    print("=" * 70)
    print(
        "🎉 DOCUMENT EXPLANATION COMPLETE"
    )
    print(
        "Gemini calls used: 2"
    )
    print(
        "Final response length:",
        len(final_answer)
    )
    print("=" * 70)

    return final_answer
