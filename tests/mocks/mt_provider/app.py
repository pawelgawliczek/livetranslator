"""
Mock MT Provider for Testing
Simulates DeepL, Google Translate, OpenAI, etc.
"""
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Mock MT Provider")


class TranslationRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock_mt_provider"}


@app.post("/translate")
async def translate(request: TranslationRequest):
    """Mock translation endpoint."""
    # Simulate processing delay
    await asyncio.sleep(0.1)

    # Simple mock translation
    mock_translations = {
        ("en", "pl"): {
            "hello": "cześć",
            "world": "świat",
            "test": "test"
        },
        ("pl", "en"): {
            "cześć": "hello",
            "świat": "world",
            "test": "test"
        },
        ("en", "ar"): {
            "hello": "مرحبا",
            "world": "عالم",
            "test": "اختبار"
        }
    }

    # Get translation or return mock
    text_lower = request.text.lower()
    lang_pair = (request.source_lang, request.target_lang)

    if lang_pair in mock_translations and text_lower in mock_translations[lang_pair]:
        translated = mock_translations[lang_pair][text_lower]
    else:
        translated = f"[MOCK {request.target_lang.upper()}] {request.text}"

    return {
        "text": translated,
        "source_lang": request.source_lang,
        "target_lang": request.target_lang,
        "confidence": 0.95,
        "provider": "mock"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
