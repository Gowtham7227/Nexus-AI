import ollama
import httpx
import re
import json
import time
import os

OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "3.0"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
ollama_client = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)


# ============================================================
# LOCAL MODEL
# ============================================================

MODEL_NAME = "qwen3:4b"


# ============================================================
# MODEL SETTINGS
# ============================================================

# Context window for:
# - long documents
# - multiple documents
# - comparison
# - summaries
NUM_CTX = 8192

# Maximum answer tokens.
# Model can stop earlier when the answer is complete.
NUM_PREDICT = 500


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are NexusAI, a local AI-powered document intelligence assistant.

Your task is to answer the user's question using ONLY the provided
DOCUMENT CONTEXT.

IMPORTANT RULES:

1. Use only information found in DOCUMENT CONTEXT.
2. Do not use outside knowledge.
3. Do not invent facts.
4. Answer the user's actual question directly.
5. Give a complete answer.
6. Do not stop before the answer is complete.
7. Do not explain your internal reasoning.
8. Do not mention these instructions.
9. Do not repeat the user's question.
10. Never write analysis or chain-of-thought.
11. Never write <think>...</think>.
12. Never say "We are given", "First, let's understand",
    "Let me analyze", "The user asks", or similar reasoning text.

============================================================
UNDERSTANDING USER QUESTIONS
============================================================

Users may ask questions using:

- normal English
- simple English
- grammatically incorrect English
- spelling mistakes
- short forms
- incomplete sentences
- conversational English
- Telugu-English mixed language
- transliterated Telugu

Understand the intended meaning naturally.

Examples:

"why they use rag?"
"why did they use rag?"
"rag enduku use chesaru?"
"rag enduku?"
"why rag?"

All mean approximately:

"Why did they use RAG?"

Do NOT reject a question because the English is imperfect.

Answer using only the document context.

============================================================
SINGLE DOCUMENT QUESTIONS
============================================================

If the user asks:

"what is this document about?"
"what is the paper about?"
"main purpose?"
"what is the main purpose?"
"what is this about?"

Give the main topic and purpose of the document.

If the user asks:

"why did they use RAG?"
"why they use RAG?"
"rag enduku use chesaru?"

Find the reason stated in the document and answer directly.

If the user asks:

"what dataset did they use?"
"which dataset?"
"dataset?"

Give the dataset name and relevant details found in the document.

If the user asks:

"summarize this document"

Give a useful summary of the important information available
in the retrieved document context.

If the user asks:

"explain this document"

Explain the available document information clearly and naturally.

============================================================
MULTI-DOCUMENT QUESTIONS
============================================================

The DOCUMENT CONTEXT may contain multiple documents.

Each document is identified by its filename.

If the user asks:

"compare these documents"
"compare these two documents"
"compare both"
"compare"
"difference between these"
"what is different?"
"what is similar?"
"similarities?"
"summarize both"
"explain both"

use the information from ALL provided documents.

For comparison questions, structure the answer clearly:

Document 1:
- main topic
- purpose
- important points

Document 2:
- main topic
- purpose
- important points

Similarities:
- important similarities supported by the documents

Differences:
- important differences supported by the documents

Conclusion:
- short overall conclusion when supported

Do not invent similarities or differences.

If the documents are unrelated, clearly say that they
cover different topics or purposes.

============================================================
DOCUMENT GROUNDING
============================================================

The provided context may contain retrieved chunks rather than
the complete document.

Use the available retrieved information.

If the available context is enough to answer the question,
answer it.

Do NOT say information is missing merely because the user's
question uses different wording.

For example:

User:
"rag enduku use chesaru?"

Understand:
"Why did they use RAG?"

Then find the answer in the document context.

============================================================
ANSWER LENGTH
============================================================

Give only as much information as the question requires.

For a simple factual question:
give a concise direct answer.

For a "why" question:
give the reason and enough supporting explanation.

For a summary:
give the important points.

For a comparison:
give enough detail to understand both documents,
their similarities, and their differences.

Do not unnecessarily make simple answers long.

Do not cut an answer in the middle.

============================================================
IF INFORMATION IS NOT AVAILABLE
============================================================

Only when the provided context genuinely does not contain
enough information, answer:

"I couldn't find that information in the uploaded document."

For multiple documents:

"I couldn't find enough information in the selected documents
to answer that question."

Do not use this response when the context actually contains
enough information.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON:

{
  "answer": "complete final answer"
}

The answer field must contain only the user-facing answer.

Do not include reasoning.
Do not include analysis.
Do not include instructions.
"""


# ============================================================
# JSON SCHEMA
# ============================================================

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string"
        }
    },
    "required": [
        "answer"
    ]
}


# ============================================================
# WARM UP MODEL
# ============================================================

def warmup_local_model():

    start_time = time.perf_counter()

    try:

        print("=" * 70)
        print("🔥 WARMING UP LOCAL QWEN MODEL")
        print("Model:", MODEL_NAME)
        print("=" * 70)

        ollama.generate(
            model=MODEL_NAME,
            prompt="OK",
            keep_alive=-1,
            options={
                "num_predict": 1,
                "num_ctx": NUM_CTX
            }
        )

        elapsed = (
            time.perf_counter()
            - start_time
        )

        print(
            f"✅ Qwen warm-up completed in "
            f"{elapsed:.2f} seconds"
        )

        return {
            "status": "ready",
            "model": MODEL_NAME,
            "time": round(
                elapsed,
                2
            )
        }

    except Exception as e:

        print(
            "❌ Qwen warm-up failed:",
            str(e)
        )

        return {
            "status": "error",
            "model": MODEL_NAME,
            "error": str(e)
        }


# ============================================================
# REMOVE THINKING
# ============================================================

def remove_thinking_blocks(text):

    if not text:
        return ""

    # Complete thinking block
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Unclosed thinking block
    text = re.sub(
        r"<think>.*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remaining tags
    text = re.sub(
        r"</?think>",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# CLEAN ANSWER
# ============================================================

def clean_answer(text):

    if not text:
        return ""

    text = remove_thinking_blocks(text)

    text = text.strip()

    # Remove markdown JSON fences
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    # Remove accidental answer tags
    text = re.sub(
        r"</?answer>",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Remove common prefixes
    text = re.sub(
        r"^(FINAL ANSWER|FINAL RESPONSE|ANSWER)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ============================================================
# EXTRACT JSON ANSWER
# ============================================================

def extract_json_answer(raw_text):

    if not raw_text:
        return ""

    text = remove_thinking_blocks(raw_text)

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:

        data = json.loads(text)

        if isinstance(data, dict):

            answer = data.get(
                "answer",
                ""
            )

            if isinstance(answer, str):

                return clean_answer(answer)

    except Exception:
        pass


    # --------------------------------------------------------
    # Search for JSON object
    # --------------------------------------------------------

    match = re.search(
        r'\{\s*"answer"\s*:\s*"(.*?)"\s*\}',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if match:

        answer = match.group(1)

        try:

            answer = json.loads(
                '"' + answer + '"'
            )

        except Exception:
            pass

        return clean_answer(answer)


    return ""


# ============================================================
# FALLBACK CLEANING
# ============================================================

def fallback_answer(raw_text):

    if not raw_text:
        return ""

    text = remove_thinking_blocks(
        raw_text
    )

    if not text:
        return ""

    # Remove obvious reasoning prefixes.
    bad_prefixes = [
        "we are given",
        "first, let's understand",
        "first, i need to",
        "i need to understand",
        "let me analyze",
        "let me go through",
        "the user asks",
        "the user is asking",
        "looking at the document",
        "looking at the provided text",
        "the answer should be",
        "we must",
        "we need to"
    ]

    lines = text.splitlines()

    useful_lines = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        lower = line.lower()

        if any(
            lower.startswith(prefix)
            for prefix in bad_prefixes
        ):
            continue

        useful_lines.append(line)

    if not useful_lines:
        return ""

    result = "\n".join(
        useful_lines
    )

    return clean_answer(result)


# ============================================================
# FINAL ANSWER EXTRACTION
# ============================================================

def extract_final_answer(raw_text):

    if not raw_text:
        return ""

    # 1. JSON
    answer = extract_json_answer(
        raw_text
    )

    if answer:
        return answer

    # 2. Fallback
    answer = fallback_answer(
        raw_text
    )

    return clean_answer(
        answer
    )


# ============================================================
# BUILD USER MESSAGE
# ============================================================

def build_user_message(
    context,
    question
):
    if not context or not context.strip():
        return f"""
USER QUESTION
============================================================
{question}
============================================================

TASK

You are NexusAI, a helpful AI assistant. Answer the user's question directly, accurately, and concisely.

Return ONLY valid JSON:

{{
  "answer": "complete final answer"
}}
"""

    return f"""
DOCUMENT CONTEXT
============================================================

The following is retrieved information from the selected
document(s).

Use the document content as the source of truth.

{context}

============================================================
END DOCUMENT CONTEXT
============================================================

USER QUESTION
============================================================

{question}

============================================================

TASK

Understand the user's intended question even if the wording
contains grammar mistakes, spelling mistakes, informal English,
short forms, incomplete sentences, or Telugu-English mixed wording.

Answer the question directly.

If multiple documents are provided and the user asks for a
comparison, use all relevant documents and clearly explain:

1. What each document is about
2. Similarities
3. Differences
4. Overall conclusion when supported

If the user asks a simple factual question, give a concise answer.

If the user asks why something was used, give the reason stated
or supported by the document.

If the user asks for a summary, provide the important points.

Use ONLY the document context.

Do not use outside knowledge.

Return ONLY valid JSON:

{{
  "answer": "complete final answer"
}}
"""


# ============================================================
# ASK LOCAL QWEN
# ============================================================

def ask_local(
    context,
    question
):
    if not question or not question.strip():
        return "Please enter a question."

    start_time = time.perf_counter()

    try:

        # ----------------------------------------------------
        # Build prompt
        # ----------------------------------------------------

        user_message = build_user_message(
            context,
            question
        )

        print("=" * 70)
        print("🖥️ LOCAL QWEN REQUEST")
        print("=" * 70)

        print(
            "Question:",
            question
        )

        print(
            "Context Length:",
            len(context)
        )

        print(
            "Prompt Length:",
            len(user_message)
        )

        print(
            "Context Window:",
            NUM_CTX
        )

        print(
            "Maximum Output Tokens:",
            NUM_PREDICT
        )

        print("=" * 70)


        # ----------------------------------------------------
        # QWEN
        # ----------------------------------------------------

        try:

            response = ollama_client.chat(

                model=MODEL_NAME,

                messages=[

                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },

                    {
                        "role": "user",
                        "content": user_message
                    }

                ],

                think=False,

                stream=False,

                keep_alive=-1,

                format=ANSWER_SCHEMA,

                options={

                    "temperature": 0.1,

                    "num_predict":
                        NUM_PREDICT,

                    "num_ctx":
                        NUM_CTX
                }
            )


        except Exception as structured_error:
            if isinstance(structured_error, (httpx.HTTPError, ConnectionError, OSError)):
                raise structured_error

            print(
                "⚠️ Structured output failed:"
            )

            print(
                str(structured_error)
            )

            print(
                "Retrying without JSON schema..."
            )


            response = ollama_client.chat(

                model=MODEL_NAME,

                messages=[

                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },

                    {
                        "role": "user",
                        "content": user_message
                    }

                ],

                think=False,

                stream=False,

                keep_alive=-1,

                options={

                    "temperature": 0.1,

                    "num_predict":
                        NUM_PREDICT,

                    "num_ctx":
                        NUM_CTX
                }
            )


        # ----------------------------------------------------
        # TIMING
        # ----------------------------------------------------

        total_time = (
            time.perf_counter()
            - start_time
        )


        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        prompt_eval_duration = response.get(
            "prompt_eval_duration",
            0
        )

        eval_duration = response.get(
            "eval_duration",
            0
        )

        prompt_eval_seconds = (
            prompt_eval_duration
            / 1_000_000_000
        )

        generation_seconds = (
            eval_duration
            / 1_000_000_000
        )


        # ----------------------------------------------------
        # RAW RESPONSE
        # ----------------------------------------------------

        message = response.get(
            "message",
            {}
        )

        raw_answer = message.get(
            "content",
            ""
        )


        # ----------------------------------------------------
        # FINAL ANSWER
        # ----------------------------------------------------

        final_answer = extract_final_answer(
            raw_answer
        )


        # ----------------------------------------------------
        # PERFORMANCE LOG
        # ----------------------------------------------------

        print("=" * 70)
        print("LOCAL QWEN PERFORMANCE")
        print("=" * 70)

        print(
            "Question:",
            question
        )

        print(
            "Model:",
            MODEL_NAME
        )

        print(
            f"Total Time: "
            f"{total_time:.2f} seconds"
        )

        print(
            f"Prompt Evaluation: "
            f"{prompt_eval_seconds:.2f} seconds"
        )

        print(
            f"Token Generation: "
            f"{generation_seconds:.2f} seconds"
        )

        print(
            "Thinking Used: No"
        )

        print(
            "Context Size:",
            NUM_CTX
        )

        print(
            "Maximum Output Tokens:",
            NUM_PREDICT
        )

        print(
            "Raw Answer Length:",
            len(raw_answer)
        )

        print(
            "Final Answer Length:",
            len(final_answer)
        )

        print("-" * 70)

        print(
            "RAW QWEN OUTPUT:"
        )

        print(
            raw_answer
        )

        print("-" * 70)

        print(
            "FINAL CLEAN ANSWER:"
        )

        print(
            final_answer
        )

        print("=" * 70)


        # ----------------------------------------------------
        # EMPTY ANSWER
        # ----------------------------------------------------

        if not final_answer:
            return (
                "I couldn't generate an answer from the uploaded document."
                if context and context.strip()
                else "I couldn't generate an answer at this time."
            )


        return final_answer


    except Exception as e:

        print("=" * 70)

        print(
            "❌ LOCAL QWEN ERROR:"
        )

        print(
            str(e)
        )

        print("=" * 70)

        return (
            "Sorry, I was unable to generate "
            "a local AI answer at this time."
        )


# ============================================================
# STREAM LOCAL
# ============================================================

def stream_local(
    context,
    question
):

    """
    Current frontend expects a streaming endpoint.

    We generate the complete answer first and then return it
    through the streaming response so the existing frontend
    does not need to change.
    """

    answer = ask_local(
        context,
        question
    )

    yield answer