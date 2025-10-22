"""
Azure Translator Backend

Provides machine translation with wide language support using Azure Cognitive Services.
- 100+ languages supported
- Best for non-European language pairs (AR, RU, ZH, JA, KO)
- Custom terminology support
- Document translation with context
- Cost-effective ($10 per 1M characters)
"""

import os
from typing import Optional, Dict, Any, List
import httpx

# Environment variables
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY", "")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "eastus")
AZURE_TRANSLATOR_ENDPOINT = os.getenv(
    "AZURE_TRANSLATOR_ENDPOINT",
    "https://api.cognitive.microsofttranslator.com"
)

# Pricing: $10 per 1M characters
AZURE_TRANSLATOR_PRICE_PER_1M_CHARS = 10.0


async def translate(
    text: str,
    src_lang: str,
    tgt_lang: str,
    context: Optional[str] = None,
    glossary: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Translate text using Azure Translator API.

    Args:
        text: Text to translate
        src_lang: Source language code (en, pl, ar, ru, zh, ja, ko, etc.)
        tgt_lang: Target language code
        context: Optional conversation context (not directly supported, but can influence via sentence context)
        glossary: Optional custom terminology dictionary

    Returns:
        {
            "text": "translated text",
            "src_lang": "en",
            "tgt_lang": "ar",
            "detected_source_language": "en"
        }
    """
    if not AZURE_TRANSLATOR_KEY:
        raise Exception("AZURE_TRANSLATOR_KEY not set")

    # Normalize language codes
    src_code = _normalize_language(src_lang)
    tgt_code = _normalize_language(tgt_lang)

    # Prepare API request
    path = "/translate"
    constructed_url = AZURE_TRANSLATOR_ENDPOINT + path

    params = {
        "api-version": "3.0",
        "to": tgt_code
    }

    # Add source language if not auto-detect
    if src_code != "auto":
        params["from"] = src_code

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
        "Content-Type": "application/json"
    }

    body = [{"text": text}]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                constructed_url,
                params=params,
                headers=headers,
                json=body
            )
            response.raise_for_status()
            result_data = response.json()

        # Parse response
        if not result_data or len(result_data) == 0:
            raise Exception("Azure Translator returned empty response")

        translation = result_data[0]
        translations = translation.get("translations", [])

        if not translations:
            raise Exception("No translations returned")

        translated_text = translations[0].get("text", "")
        detected_lang = translation.get("detectedLanguage", {}).get("language", src_lang)

        print(f"[Azure Translator] Translated {len(text)} chars from {src_lang} to {tgt_lang}, "
              f"detected={detected_lang}")

        return {
            "text": translated_text,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "detected_source_language": detected_lang
        }

    except httpx.HTTPStatusError as e:
        print(f"[Azure Translator] HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Azure Translator HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"[Azure Translator] Error: {e}")
        raise


async def translate_batch(
    texts: List[str],
    src_lang: str,
    tgt_lang: str,
    context: Optional[str] = None,
    glossary: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Translate multiple texts in a single API call for efficiency.

    Args:
        texts: List of texts to translate (max 100 per request)
        src_lang: Source language code
        tgt_lang: Target language code
        context: Optional conversation context
        glossary: Optional custom terminology

    Returns:
        List of translation results
    """
    if not AZURE_TRANSLATOR_KEY:
        raise Exception("AZURE_TRANSLATOR_KEY not set")

    # Normalize language codes
    src_code = _normalize_language(src_lang)
    tgt_code = _normalize_language(tgt_lang)

    # Prepare API request
    path = "/translate"
    constructed_url = AZURE_TRANSLATOR_ENDPOINT + path

    params = {
        "api-version": "3.0",
        "to": tgt_code
    }

    if src_code != "auto":
        params["from"] = src_code

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_TRANSLATOR_REGION,
        "Content-Type": "application/json"
    }

    # Azure supports up to 100 texts per request
    body = [{"text": t} for t in texts[:100]]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                constructed_url,
                params=params,
                headers=headers,
                json=body
            )
            response.raise_for_status()
            result_data = response.json()

        # Parse results
        translations = []
        for i, item in enumerate(result_data):
            item_translations = item.get("translations", [])
            if item_translations:
                translated_text = item_translations[0].get("text", "")
                detected_lang = item.get("detectedLanguage", {}).get("language", src_lang)

                translations.append({
                    "text": translated_text,
                    "src_lang": src_lang,
                    "tgt_lang": tgt_lang,
                    "detected_source_language": detected_lang,
                    "original": texts[i]
                })

        print(f"[Azure Translator] Batch translated {len(translations)} texts from {src_lang} to {tgt_lang}")

        return translations

    except httpx.HTTPStatusError as e:
        print(f"[Azure Translator] Batch HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Azure Translator batch HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"[Azure Translator] Batch error: {e}")
        raise


def _normalize_language(language: str) -> str:
    """
    Convert language codes to Azure Translator format.

    Azure uses 2-letter ISO 639-1 codes (lowercase).
    Some languages need specific variants.
    """
    # Remove country codes and convert to lowercase
    lang = language.split("-")[0].lower()

    # Map to Azure codes (mostly just lowercase 2-letter)
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
        "zh": "zh-Hans",  # Simplified Chinese
        "ja": "ja",
        "ko": "ko",
        "auto": "auto"  # Auto-detect
    }

    return lang_map.get(lang, lang)  # Default to original if not in map


async def get_cost(char_count: int) -> float:
    """
    Calculate cost for Azure Translator translation.

    Args:
        char_count: Number of characters translated

    Returns:
        Cost in USD
    """
    millions = char_count / 1_000_000.0
    return millions * AZURE_TRANSLATOR_PRICE_PER_1M_CHARS


def is_supported_language_pair(src_lang: str, tgt_lang: str) -> bool:
    """
    Check if Azure Translator supports this language pair.

    Azure supports 100+ languages, so almost all pairs are supported.
    Returns True for nearly all combinations.
    """
    # Azure supports a very wide range of languages
    # Only reject obviously invalid codes
    src = src_lang.split("-")[0].lower()
    tgt = tgt_lang.split("-")[0].lower()

    # Very basic validation - in practice, Azure supports almost everything
    return len(src) >= 2 and len(tgt) >= 2
