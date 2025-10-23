"""
Amazon Translate Backend

Provides machine translation with wide language support using Amazon Translate.
- 75+ languages supported
- Best for non-European language pairs as fallback (AR, RU, ZH, JA, KR)
- Neural machine translation
- Cost-effective ($15 per 1M characters)
"""

import os
from typing import Optional, Dict, Any, List
import httpx
import json
import hashlib
import hmac
from datetime import datetime

# Environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Pricing: $15 per 1M characters
AMAZON_TRANSLATE_PRICE_PER_1M_CHARS = 15.0


def _sign_request(method: str, url: str, headers: dict, payload: str, region: str) -> dict:
    """
    Sign AWS request using Signature Version 4.
    """
    # Parse URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or '/'

    # Create canonical request
    canonical_querystring = ''
    canonical_headers = f'host:{host}\nx-amz-date:{headers["x-amz-date"]}\n'
    signed_headers = 'host;x-amz-date'
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

    canonical_request = f'{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'

    # Create string to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{headers["x-amz-date"][:8]}/{region}/translate/aws4_request'
    string_to_sign = f'{algorithm}\n{headers["x-amz-date"]}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'

    # Calculate signature
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = sign(('AWS4' + AWS_SECRET_ACCESS_KEY).encode('utf-8'), headers["x-amz-date"][:8])
    k_region = sign(k_date, region)
    k_service = sign(k_region, 'translate')
    k_signing = sign(k_service, 'aws4_request')
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # Add authorization header
    authorization_header = f'{algorithm} Credential={AWS_ACCESS_KEY_ID}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    headers['Authorization'] = authorization_header

    return headers


async def translate(
    text: str,
    src_lang: str,
    tgt_lang: str,
    context: Optional[str] = None,
    glossary: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Translate text using Amazon Translate API.

    Args:
        text: Text to translate
        src_lang: Source language code (en, pl, ar, ru, zh, ja, ko, etc.)
        tgt_lang: Target language code
        context: Optional conversation context (not directly supported)
        glossary: Optional custom terminology dictionary

    Returns:
        {
            "text": "translated text",
            "src_lang": "en",
            "tgt_lang": "ar",
            "detected_source_language": "en"
        }
    """
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise Exception("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY not set")

    # Normalize language codes
    src_code = _normalize_language(src_lang)
    tgt_code = _normalize_language(tgt_lang)

    # Prepare API request
    endpoint = f'https://translate.{AWS_REGION}.amazonaws.com/'

    payload = {
        "Text": text,
        "SourceLanguageCode": src_code,
        "TargetLanguageCode": tgt_code
    }

    payload_json = json.dumps(payload)

    # Prepare headers
    amz_date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    headers = {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSShineFrontendService_20170701.TranslateText',
        'x-amz-date': amz_date
    }

    # Sign request
    headers = _sign_request('POST', endpoint, headers, payload_json, AWS_REGION)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                content=payload_json
            )
            response.raise_for_status()
            result_data = response.json()

        # Parse response
        if "TranslatedText" not in result_data:
            raise Exception("Amazon Translate returned invalid response")

        translated_text = result_data["TranslatedText"]
        detected_lang = result_data.get("SourceLanguageCode", src_lang)

        print(f"[Amazon Translate] Translated {len(text)} chars from {src_lang} to {tgt_lang}")

        return {
            "text": translated_text,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "detected_source_language": detected_lang
        }

    except httpx.HTTPStatusError as e:
        print(f"[Amazon Translate] HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Amazon Translate HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"[Amazon Translate] Error: {e}")
        raise


def _normalize_language(language: str) -> str:
    """
    Convert language codes to Amazon Translate format.

    Amazon uses 2-letter ISO 639-1 codes (lowercase).
    """
    # Remove country codes and convert to lowercase
    lang = language.split("-")[0].lower()

    # Map to Amazon codes (mostly just lowercase 2-letter)
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
        "zh": "zh",  # Simplified Chinese
        "ja": "ja",
        "ko": "ko",
        "auto": "auto"  # Auto-detect
    }

    return lang_map.get(lang, lang)  # Default to original if not in map


async def get_cost(char_count: int) -> float:
    """
    Calculate cost for Amazon Translate translation.

    Args:
        char_count: Number of characters translated

    Returns:
        Cost in USD
    """
    millions = char_count / 1_000_000.0
    return millions * AMAZON_TRANSLATE_PRICE_PER_1M_CHARS


def is_supported_language_pair(src_lang: str, tgt_lang: str) -> bool:
    """
    Check if Amazon Translate supports this language pair.

    Amazon supports 75+ languages, so most pairs are supported.
    Returns True for nearly all combinations.
    """
    # Amazon supports a wide range of languages
    # Only reject obviously invalid codes
    src = src_lang.split("-")[0].lower()
    tgt = tgt_lang.split("-")[0].lower()

    # Very basic validation - in practice, Amazon supports most languages
    return len(src) >= 2 and len(tgt) >= 2
