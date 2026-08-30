"""
Service layer for Tamweel AI Chatbot.
Handles Google Gemini client initialization, prompt assembly, resilient fallback, and error management.
"""

import os
import sys
import logging
from django.conf import settings
from .knowledge import TAMWEEL_SYSTEM_INSTRUCTIONS

logger = logging.getLogger(__name__)

# Fallback responses for graceful degradation
DEFAULT_FALLBACK_MESSAGE_EN = (
    "Sorry, the Tamweel AI Assistant is temporarily unavailable. "
    "Please try again later or check our FAQ."
)
DEFAULT_FALLBACK_MESSAGE_AR = (
    "عذراً، مساعد تمويل الذكي غير متاح حالياً بشكل مؤقت. "
    "يرجى المحاولة مرة أخرى لاحقاً أو مراجعة الأسئلة الشائعة."
)

PRIMARY_MODEL = "gemini-flash-lite-latest"
FALLBACK_MODEL = "gemini-flash-latest"
MAX_OUTPUT_TOKENS = 400
TEMPERATURE = 0.3


def is_arabic_text(text: str) -> bool:
    """Detect if the input text contains predominantly Arabic characters."""
    arabic_char_count = sum(1 for char in text if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F')
    return arabic_char_count > 0


def get_fallback_message(user_message: str = "") -> str:
    """Return appropriate localized fallback message based on user query language."""
    if is_arabic_text(user_message):
        return DEFAULT_FALLBACK_MESSAGE_AR
    return DEFAULT_FALLBACK_MESSAGE_EN


def get_gemini_api_key() -> str:
    """Retrieve Gemini API key securely from environment or settings."""
    key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', '')
    if key:
        return key.strip().strip('"').strip("'")
    return ''


def log_safe_diagnostic(message: str) -> None:
    """Print safe diagnostic output to standard error/logger for developer visibility."""
    formatted_msg = f"[TAMWEEL CHATBOT DIAGNOSTICS] {message}"
    logger.warning(formatted_msg)
    print(formatted_msg, file=sys.stderr, flush=True)


def is_rate_limit_or_unavailable_error(exc: Exception) -> bool:
    """Check if the exception represents a 429 quota exhaustion or 503 service spike."""
    code = getattr(exc, 'code', None)
    if code in (429, 503):
        return True
    msg = str(exc).upper()
    return 'RESOURCE_EXHAUSTED' in msg or '429' in msg or 'UNAVAILABLE' in msg


def generate_chat_response(message: str) -> dict:
    """
    Generate an AI response using the official Google GenAI SDK with automatic fallback on rate limit (429).
    
    Args:
        message (str): Validated and trimmed user message.
        
    Returns:
        dict: {
            "success": bool,
            "reply": str,
            "error": str | None
        }
    """
    api_key = get_gemini_api_key()
    has_api_key = bool(api_key)
    fallback_text = get_fallback_message(message)

    log_safe_diagnostic(
        f"Processing message | GEMINI_API_KEY configured: {has_api_key} | Primary: {PRIMARY_MODEL} | Fallback: {FALLBACK_MODEL}"
    )

    if not has_api_key:
        log_safe_diagnostic(
            "ROOT CAUSE: GEMINI_API_KEY is missing or empty in the environment (.env). "
            "Please add 'GEMINI_API_KEY=your_key' to your .env file to enable live AI completions."
        )
        return {
            "success": False,
            "reply": fallback_text,
            "error": "API key not configured."
        }

    try:
        from google import genai
        from google.genai import types, errors

        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=TAMWEEL_SYSTEM_INSTRUCTIONS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
        )

        response = None

        # 1. Attempt generation with PRIMARY model
        try:
            log_safe_diagnostic(f"Sending request to Google Gemini API (model: {PRIMARY_MODEL})...")
            response = client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=message,
                config=config,
            )
        except (errors.ClientError, errors.ServerError, errors.APIError) as primary_err:
            if is_rate_limit_or_unavailable_error(primary_err):
                # 2. On 429 RESOURCE_EXHAUSTED or 503, immediately retry once with FALLBACK model
                log_safe_diagnostic(
                    f"Primary Gemini model rate-limited ({primary_err.__class__.__name__}: {getattr(primary_err, 'code', '429')}); "
                    f"switching to fallback ({FALLBACK_MODEL})..."
                )
                try:
                    response = client.models.generate_content(
                        model=FALLBACK_MODEL,
                        contents=message,
                        config=config,
                    )
                except Exception as fallback_err:
                    log_safe_diagnostic(f"Fallback model also failed: {fallback_err.__class__.__name__}")
                    raise fallback_err
            else:
                # Non-rate-limit error on primary
                raise primary_err

        reply_text = ""
        if response and hasattr(response, 'text') and response.text:
            reply_text = response.text.strip()

        if not reply_text:
            log_safe_diagnostic("Gemini API returned an empty completion output.")
            return {
                "success": False,
                "reply": fallback_text,
                "error": "Empty response received."
            }

        log_safe_diagnostic(f"Gemini completion succeeded (length: {len(reply_text)} chars).")
        return {
            "success": True,
            "reply": reply_text,
            "error": None
        }

    except errors.APIError as api_err:
        log_safe_diagnostic(f"ROOT CAUSE: Google Gemini API error: {api_err.__class__.__name__} ({getattr(api_err, 'code', 'N/A')})")
        return {
            "success": False,
            "reply": fallback_text,
            "error": "Gemini API error."
        }
    except Exception as exc:
        log_safe_diagnostic(f"ROOT CAUSE: Unexpected exception during Gemini generation: {exc.__class__.__name__}")
        return {
            "success": False,
            "reply": fallback_text,
            "error": "Internal assistant error."
        }
