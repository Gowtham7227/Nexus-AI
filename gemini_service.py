import os
import re
import time
from typing import Optional, Tuple, List
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 70)
print(f"[Gemini Service] Initializing | Configured: {'YES' if bool(GEMINI_API_KEY) else 'NO'}")
print("=" * 70)

# SDK Import
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    SDK_AVAILABLE = False
    print("[WARNING] google-genai package is not installed.")

# Active client and model state
_client = None

# Verified active models on Gemini API v1beta / google-genai SDK
# (excluding models known to return 404 NOT_FOUND such as 1.5, 2.0, 2.5)
VERIFIED_FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
]

# Primary model from environment
DEFAULT_ENV_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
if not DEFAULT_ENV_MODEL or any(legacy in DEFAULT_ENV_MODEL for legacy in ["1.5", "2.0", "2.5"]):
    DEFAULT_ENV_MODEL = "gemini-3.5-flash-lite"

# Construct deduplicated candidate model fallback chain
CANDIDATE_MODELS: List[str] = []
if DEFAULT_ENV_MODEL:
    CANDIDATE_MODELS.append(DEFAULT_ENV_MODEL)

for m in VERIFIED_FALLBACK_MODELS:
    if m not in CANDIDATE_MODELS:
        CANDIDATE_MODELS.append(m)

CURRENT_MODEL = CANDIDATE_MODELS[0]
print(f"[Gemini Service] Primary Model: {CURRENT_MODEL} | Fallback Chain: {CANDIDATE_MODELS}")


def get_gemini_client():
    """Return the shared initialized Google GenAI client instance."""
    global _client
    if _client is not None:
        return _client

    if not SDK_AVAILABLE or not GEMINI_API_KEY:
        return None

    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        print("[Gemini Service] Google GenAI client initialized successfully.")
        return _client
    except Exception as e:
        print("[Gemini Service] Failed to initialize Google GenAI client:", str(e))
        return None


def generate_gemini_text(
    contents: str,
    config: Optional[object] = None,
    max_output_tokens: Optional[int] = None,
    label: str = "Gemini",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Centralized generation function with automatic model fallback and exponential backoff.
    - Resolves Automatic Function Calling (AFC) SDK warning by disabling AFC when unused.
    - Handles transient 503 UNAVAILABLE and 429 RESOURCE_EXHAUSTED with exponential backoff.
    - Seamlessly transitions across verified fallback models.
    - Avoids deprecated/404 models.
    Returns: (generated_text, error_message)
    """
    global CURRENT_MODEL, CANDIDATE_MODELS

    if not GEMINI_API_KEY:
        return None, "Cloud AI is unavailable: Gemini API key is not configured in .env."

    client = get_gemini_client()
    if not client:
        return None, "Cloud AI is unavailable: Failed to initialize Google GenAI client."

    # Prepare AFC disabled config helper
    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if types and hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    last_error_summary = ""
    max_retries_per_model = 2

    for model_idx, model_name in enumerate(CANDIDATE_MODELS, start=1):
        for attempt in range(1, max_retries_per_model + 1):
            t_start = time.time()
            try:
                print(f"[GEMINI] [{label}] Calling model '{model_name}' (Model {model_idx}/{len(CANDIDATE_MODELS)}, Attempt {attempt}/{max_retries_per_model})...")

                # Build or adapt configuration safely
                gen_config = config
                if gen_config is None:
                    if types:
                        gen_config = types.GenerateContentConfig(
                            temperature=0.0,
                            max_output_tokens=max_output_tokens or 1500,
                            automatic_function_calling=afc_disabled,
                        )
                else:
                    # Disable AFC on provided config if not already set
                    if hasattr(gen_config, "automatic_function_calling") and gen_config.automatic_function_calling is None:
                        try:
                            gen_config.automatic_function_calling = afc_disabled
                        except Exception:
                            pass

                # Execute generate_content call
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=gen_config,
                )
                elapsed = time.time() - t_start

                # Extract text from response safely
                text = getattr(response, "text", None) or ""
                if not text.strip() and hasattr(response, "candidates") and response.candidates:
                    c0 = response.candidates[0]
                    if hasattr(c0, "content") and c0.content and hasattr(c0.content, "parts") and c0.content.parts:
                        text = "".join([p.text for p in c0.content.parts if hasattr(p, "text") and p.text])

                if text and text.strip():
                    print(f"[SUCCESS] [{label}] Generated response via model '{model_name}' in {elapsed:.2f}s (length={len(text)} chars)")
                    CURRENT_MODEL = model_name
                    return text.strip(), None

                print(f"[WARNING] [{label}] Model '{model_name}' returned empty response text in {elapsed:.2f}s.")
                break  # Advance to next candidate model

            except Exception as e:
                elapsed = time.time() - t_start
                err_str = str(e)
                err_type = type(e).__name__
                last_error_summary = f"{err_type}: {err_str}"

                is_404 = "404" in err_str or "NOT_FOUND" in err_str.upper() or "not found" in err_str.lower()
                is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str.upper() or "quota" in err_str.lower()
                is_503 = "503" in err_str or "UNAVAILABLE" in err_str.upper() or "high demand" in err_str.lower()

                status_label = "404 Not Found" if is_404 else ("429 Resource Exhausted" if is_429 else ("503 Unavailable" if is_503 else err_type))
                print(f"[ERROR] [{label}] Model '{model_name}' failed in {elapsed:.2f}s with {status_label}")

                # Permanent 404: skip to next candidate model immediately without retrying
                if is_404:
                    print(f"[FALLBACK] [{label}] Model '{model_name}' is not available (404). Skipping to next candidate model.")
                    break

                # Transient 429 or 503: exponential backoff then retry
                if (is_429 or is_503) and attempt < max_retries_per_model:
                    backoff = 1.0 * (2 ** (attempt - 1))
                    print(f"[RETRY] [{label}] Transient {status_label}. Backing off {backoff:.1f}s before retry...")
                    time.sleep(backoff)
                    continue
                else:
                    print(f"[FALLBACK] [{label}] Retries exhausted for model '{model_name}'. Transitioning to next candidate model...")
                    break

    print(f"[FAIL] [{label}] All candidate Gemini models were exhausted.")
    return None, "Gemini API is temporarily unavailable. Please try again shortly."


def test_direct_gemini() -> Tuple[bool, str]:
    """Perform a direct test query to verify live Gemini connectivity."""
    text, error = generate_gemini_text("Say hello in one sentence.", label="DirectTest")
    if text and text.strip():
        return True, text.strip()
    return False, error or "No response received"


def generate_gemini_stream(
    contents: str,
    config: Optional[object] = None,
    max_output_tokens: Optional[int] = None,
    label: str = "GeminiStream",
):
    """
    Progressively yields text token chunks via Google GenAI SDK generate_content_stream.
    """
    global CURRENT_MODEL

    if not GEMINI_API_KEY:
        yield "Cloud AI is unavailable: Gemini API key is not configured in .env."
        return

    client = get_gemini_client()
    if not client:
        yield "Cloud AI is unavailable: Failed to initialize Google GenAI client."
        return

    afc_disabled = (
        types.AutomaticFunctionCallingConfig(disable=True)
        if types and hasattr(types, "AutomaticFunctionCallingConfig")
        else None
    )

    gen_config = config
    if gen_config is None:
        if types:
            gen_config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=max_output_tokens or 1500,
                automatic_function_calling=afc_disabled,
            )
    else:
        if hasattr(gen_config, "automatic_function_calling") and gen_config.automatic_function_calling is None:
            try:
                gen_config.automatic_function_calling = afc_disabled
            except Exception:
                pass

    candidate_models = [CURRENT_MODEL] if CURRENT_MODEL else []
    for m in CANDIDATE_MODELS:
        if m not in candidate_models:
            candidate_models.append(m)

    t_start = time.perf_counter()
    has_tokens = False

    for model_name in candidate_models:
        try:
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=gen_config,
            )

            for chunk in response_stream:
                chunk_text = getattr(chunk, "text", "") or ""
                if not chunk_text and hasattr(chunk, "candidates") and chunk.candidates:
                    c0 = chunk.candidates[0]
                    if hasattr(c0, "content") and c0.content and hasattr(c0.content, "parts") and c0.content.parts:
                        chunk_text = "".join([p.text for p in c0.content.parts if hasattr(p, "text") and p.text])
                if chunk_text:
                    has_tokens = True
                    yield chunk_text

            elapsed = time.perf_counter() - t_start
            print(f"[SUCCESS] [{label}] Stream completed via model '{model_name}' in {elapsed:.2f}s")
            CURRENT_MODEL = model_name
            return

        except Exception as e:
            elapsed = time.perf_counter() - t_start
            print(f"[ERROR] [{label}] Stream failed via model '{model_name}' after {elapsed:.2f}s: {type(e).__name__} - {e}")
            if has_tokens:
                # If we already yielded tokens, do not attempt to stream from a different model mid-stream
                return
            # If no tokens have been yielded yet, try next candidate model
            continue

    if not has_tokens:
        yield "Gemini API is temporarily unavailable. Please try again shortly."

