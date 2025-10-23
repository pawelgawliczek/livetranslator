"""
Google Cloud Translation Backend

Provides machine translation with wide language support using Google Cloud Translation API.
- 100+ languages supported
- Best for non-European language pairs as fallback (AR, RU, ZH, JA, KO)
- Neural machine translation
- Cost-effective ($20 per 1M characters)
"""

import os
from typing import Optional, Dict, Any, List
import httpx

# Environment variables
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
GOOGLE_TRANSLATE_ENDPOINT = os.getenv(
    "GOOGLE_TRANSLATE_ENDPOINT",
    "https://translation.googleapis.com/language/translate/v2"
)

# Pricing: $20 per 1M characters
GOOGLE_TRANSLATE_PRICE_PER_1M_CHARS = 20.0


async def translate(
    text: str,
    src_lang: str,
    tgt_lang: str,
    context: Optional[str] = None,
    glossary: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Translate text using Google Cloud Translation API.

    Args:
        text: Text to translate
        src_lang: Source language code (en, pl, ar, ru, zh, ja, ko, etc.)
        tgt_lang: Target language code
        context: Optional conversation context (not directly supported)
        glossary: Optional custom terminology dictionary (not directly supported)

    Returns:
        {
            "text": "translated text",
            "src_lang": "en",
            "tgt_lang": "ar",
            "detected_source_language": "en"
        }
    """
    if not GOOGLE_TRANSLATE_API_KEY:
        raise Exception("GOOGLE_TRANSLATE_API_KEY not set")

    # Normalize language codes
    src_code = _normalize_language(src_lang)
    tgt_code = _normalize_language(tgt_lang)

    # Prepare API request
    params = {
        "key": GOOGLE_TRANSLATE_API_KEY,
        "q": text,
        "target": tgt_code,
        "format": "text"
    }

    # Add source language if not auto-detect
    if src_code != "auto":
        params["source"] = src_code

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TRANSLATE_ENDPOINT,
                params=params
            )
            response.raise_for_status()
            result_data = response.json()

        # Parse response
        if "data" not in result_data or "translations" not in result_data["data"]:
            raise Exception("Google Translate returned invalid response")

        translations = result_data["data"]["translations"]
        if not translations:
            raise Exception("No translations returned")

        translation = translations[0]
        translated_text = translation.get("translatedText", "")
        detected_lang = translation.get("detectedSourceLanguage", src_lang)

        print(f"[Google Translate] Translated {len(text)} chars from {src_lang} to {tgt_lang}, "
              f"detected={detected_lang}")

        return {
            "text": translated_text,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "detected_source_language": detected_lang
        }

    except httpx.HTTPStatusError as e:
        print(f"[Google Translate] HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Google Translate HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"[Google Translate] Error: {e}")
        raise


def _normalize_language(language: str) -> str:
    """
    Convert language codes to Google Translate format.

    Google uses 2-letter ISO 639-1 codes (lowercase).
    Some languages need specific variants.
    """
    # Remove country codes and convert to lowercase
    lang = language.split("-")[0].lower()

    # Map to Google codes (mostly just lowercase 2-letter)
    lang_map = {
        "pl": "pl",
        "en": "en",
        "ar": "ar",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ru": "ru",
        "zh": "zh-CN",  # Simplified Chinese
        "ja": "ja",
        "ko": "ko",
        "auto": "auto"  # Auto-detect
    }

    return lang_map.get(lang, lang)  # Default to original if not in map


async def get_cost(char_count: int) -> float:
    """
    Calculate cost for Google Translate translation.

    Args:
        char_count: Number of characters translated

    Returns:
        Cost in USD
    """
    millions = char_count / 1_000_000.0
    return millions * GOOGLE_TRANSLATE_PRICE_PER_1M_CHARS


def is_supported_language_pair(src_lang: str, tgt_lang: str) -> bool:
    """
    Check if Google Translate supports this language pair.

    Google supports 100+ languages, so almost all pairs are supported.
    Returns True for nearly all combinations.
    """
    # Google supports a very wide range of languages
    # Only reject obviously invalid codes
    src = src_lang.split("-")[0].lower()
    tgt = tgt_lang.split("-")[0].lower()

    # Very basic validation - in practice, Google supports almost everything
    return len(src) >= 2 and len(tgt) >= 2
