import os
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MT_MODEL = os.getenv("OPENAI_MT_MODEL", "gpt-4o-mini")

async def translate_text(text: str, src_lang: str, tgt_lang: str) -> dict:
    """
    Translate text using OpenAI GPT with optimized settings for Arabic

    Returns:
        dict: {
            "text": translated text,
            "model": model name used (gpt-4o or gpt-4o-mini)
        }
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not set")

    # Configure language names and translation approach
    translating_to_arabic = tgt_lang == "ar"
    translating_from_arabic = src_lang == "ar"
    is_arabic_translation = translating_to_arabic or translating_from_arabic

    # Use Egyptian Arabic dialect when working with Arabic
    target_language = "Egyptian Arabic (colloquial/spoken dialect)" if translating_to_arabic else tgt_lang
    source_language = "Egyptian Arabic (colloquial/spoken dialect)" if translating_from_arabic else src_lang

    # Use gpt-4o-mini for all translations (including Arabic)
    model = OPENAI_MT_MODEL

    # Build messages with system prompt for Arabic translations
    messages = []

    if translating_to_arabic:
        # System prompt for translating TO Egyptian Arabic
        messages.append({
            'role': 'system',
            'content': (
                'You are a professional translator specializing in Egyptian Arabic. '
                'Translate the following text into natural, colloquial Egyptian Arabic '
                'as it would be spoken in everyday conversation. '
                'Use the Egyptian dialect (Masri), not formal Modern Standard Arabic. '
                'Return ONLY the translated text with no explanations, notes, or additional commentary.'
            )
        })
    elif translating_from_arabic:
        # System prompt for translating FROM Egyptian Arabic
        messages.append({
            'role': 'system',
            'content': (
                'You are a professional translator specializing in Egyptian Arabic. '
                'The source text is in colloquial Egyptian Arabic (Masri dialect). '
                'Translate it naturally to the target language. '
                'Return ONLY the translated text with no explanations, notes, or additional commentary.'
            )
        })

    # Add user prompt
    messages.append({
        'role': 'user',
        'content': f"Translate this {source_language} text to {target_language}:\n\n{text}"
    })

    # Use optimized settings: temperature 0.1-0.2 for faithful output
    request_params = {
        'model': model,
        'messages': messages,
        'temperature': 0.15,  # Low temperature for faithful, consistent translations
        'max_tokens': 1000,  # Increased to handle longer segments
    }

    # Add seed for reproducibility if using gpt-4o or gpt-4o-mini
    if 'gpt-4o' in model:
        request_params['seed'] = 42

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENAI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=request_params
        )
        response.raise_for_status()
        result = response.json()

        translated = result['choices'][0]['message']['content'].strip()
        return {
            "text": translated,
            "model": model
        }
