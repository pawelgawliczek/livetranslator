import os
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MT_MODEL = os.getenv("OPENAI_MT_MODEL", "gpt-4o-mini")

async def translate_text(text: str, src_lang: str, tgt_lang: str) -> str:
    """
    Translate text using OpenAI GPT
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not set")
    
    prompt = f"Translate this {src_lang} text to {tgt_lang}. Return ONLY the translation, no explanations:\n\n{text}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENAI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': OPENAI_MT_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 500
            }
        )
        response.raise_for_status()
        result = response.json()
        
        translated = result['choices'][0]['message']['content'].strip()
        return translated
