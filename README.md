# LiveTranslator

Open-source real-time speech translation. You talk, other people read what you said in their language.

## Why I built this

My wife speaks Arabic. My parents speak Polish. I speak both plus English. Every family call, every dinner with both sides, I'm the interpreter. It's exhausting and I'm bad at it - I miss things, I paraphrase wrong, I can't keep up when two people talk at once.

So I built this. You open a room, everyone joins on their phone or laptop, and as people speak, translations appear on everyone's screen in their own language. The words show up as you talk (partial results every 400ms), then get cleaned up when the sentence finishes. About 2-4 seconds from speech to translated text.

## How it works

```
You speak Polish
    -> browser captures audio (VAD detects speech)
    -> WebSocket sends PCM16 chunks every 400ms
    -> STT Router picks the best provider for Polish (Speechmatics)
    -> partial transcription streams back immediately
    -> final transcription goes to MT Router
    -> MT Router picks provider per language pair (DeepL for European, OpenAI for Arabic)
    -> translations broadcast to all room participants via WebSocket
    -> your wife reads Arabic, your colleague reads English
```

The pipeline is split across Redis Pub/Sub channels. Each stage (STT, MT, TTS, persistence, cost tracking) runs in its own container. If one stage is slow, the others don't block.

## Architecture

```
Browser (React + VAD)
    |
    | WebSocket / REST
    v
Caddy (auto HTTPS)
    |
    v
API (FastAPI) ──── PostgreSQL (users, rooms, translations, costs)
    |
    | Redis Pub/Sub
    |
    ├── STT Router ──> Speechmatics / Google Cloud / OpenAI Whisper / Deepgram / Azure
    ├── MT Router  ──> DeepL / Google Translate / Amazon Translate / OpenAI GPT-4o-mini
    ├── TTS Router ──> Google Cloud TTS / Azure Speech
    ├── Cost Tracker
    ├── Persistence (Redis -> PostgreSQL)
    └── Room Cleanup (deletes empty rooms after 30min)
```

That's 12 Docker containers total. Sounds like a lot, but each one does one thing and they're all defined in a single `docker-compose.yml`.

## What it can do

Each language gets routed to whatever STT provider handles it best - Polish goes to Speechmatics, Arabic to Google Cloud, English to Deepgram when you want speed or OpenAI Whisper when you want accuracy. Same for translation: European pairs go through DeepL, Arabic through OpenAI. All of this is configured in the database and you can change it from the admin panel without restarting anything.

If a provider goes down, the system switches to a fallback after three consecutive failures. Usually takes about 500ms.

When multiple people are in a room speaking different languages, each person's speech gets translated into every other language. 3 people = 6 translation streams. 5 people = 20. It adds up fast, which is why cost tracking exists - every API call gets logged with the provider, price, and which room it came from.

Other things: guest access (share a link, no signup, 1-hour sessions), budget alerts at 80% and 95% of monthly limits, a presence indicator showing who's in the room and what language they speak, and the UI itself is translated into 12 languages.

## Providers

### Speech-to-text
| Provider | Good at | Runs where |
|----------|---------|------------|
| Speechmatics | Polish, English (streaming) | Cloud |
| Google Cloud Speech v2 | Arabic, broad language support | Cloud |
| OpenAI Whisper | General purpose, decent at everything | Cloud |
| Deepgram Nova-3 | English, fast and cheap | Cloud |
| Azure Speech | European languages | Cloud |
| Faster-Whisper | Offline fallback when APIs are down | Local container |

### Translation
| Provider | Good at | Runs where |
|----------|---------|------------|
| DeepL | European language pairs (best quality) | Cloud |
| Google Cloud Translation | Broad coverage | Cloud |
| Amazon Translate | Fallback | Cloud |
| OpenAI GPT-4o-mini | Arabic dialects, context-aware | Cloud |
| CTranslate2 + NLLB | Polish <-> English only, but free | Local container |

### Text-to-speech
| Provider | Notes |
|----------|-------|
| Google Cloud TTS | Multiple voices per language |
| Azure Speech | Speed and pitch controls |

## Getting started

You need Docker and at least an OpenAI API key. The other providers are optional - you can add them later for better quality on specific languages.

```bash
git clone https://github.com/pawelgawliczek/livetranslator.git
cd livetranslator

cp .env.example .env
# Edit .env - at minimum set POSTGRES_PASSWORD and OPENAI_API_KEY

mkdir -p data/{pg,redis,models,audio,logs}

docker compose up -d

curl http://localhost:9003/healthz
# {"ok": true}
```

The app runs at `http://localhost` (port 80). For production, put Caddy or nginx in front for HTTPS and set `DOMAIN` in `.env`.

## Configuration

Everything is in `.env`. See [`.env.example`](.env.example) for the full list.

The bare minimum:

```env
POSTGRES_PASSWORD=something-long-and-random
OPENAI_API_KEY=sk-...
```

To get better results for specific languages, add more API keys:

```env
SPEECHMATICS_API_KEY=...    # much better Polish/English STT
DEEPL_API_KEY=...           # much better European MT
GOOGLE_CLOUD_PROJECT=...    # much better Arabic STT
```

## Tech stack

| | |
|-------|------|
| Frontend | React 18, Vite, Tailwind CSS, i18next |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Database | PostgreSQL 16 |
| Messaging | Redis 7 (Pub/Sub) |
| Auth | JWT + Google OAuth |
| Infrastructure | Docker Compose, Caddy 2 |
| Tests | pytest + Vitest, 690+ tests |

## Project layout

```
livetranslator/
├── api/                    # FastAPI backend
│   ├── routers/
│   │   ├── stt/            # STT router (separate container)
│   │   ├── mt/             # MT router (separate container)
│   │   └── tts/            # TTS router (separate container)
│   ├── services/           # Cost tracker, persistence, cleanup
│   ├── tests/
│   └── main.py
├── web/                    # React frontend
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       └── locales/        # 12 languages
├── workers/
│   ├── stt/                # Local Whisper worker
│   └── mt/                 # Local NLLB worker
├── migrations/             # SQL migrations
├── docker-compose.yml
└── .env.example
```

## Tests

```bash
# Backend
docker compose exec api pytest api/tests/ -v

# Frontend
cd web && npm test

# Git hooks run tests automatically on commit
TEST_LEVEL=fast git commit -m "message"    # unit tests only (~10s)
git commit -m "message"                     # unit + integration (~30s)
```

## What it costs to run

You pay the API providers directly. Here's roughly what a 1-hour call with 3 people speaking 3 different languages costs:

| | |
|---------|----------|
| STT (Speechmatics) | ~$0.60 |
| MT (DeepL) | ~$0.10 |
| MT (OpenAI fallback) | ~$0.05 |
| Total | ~$0.75/hr |

Going all-OpenAI (Whisper + GPT-4o-mini) is cheaper at maybe $0.40/hr but noticeably worse for Polish. The local workers (Faster-Whisper + NLLB) are free but only do Polish <-> English.

The admin panel has cost breakdowns by room, provider, and day, so you can see where the money goes.

## License

MIT

## Contributing

PRs welcome. There are 690+ tests and I'd like to keep that number going up, not down.

```bash
docker compose exec api pytest api/tests/ --tb=short -q
cd web && npm run test:run
```
