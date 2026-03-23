# CV Barber

Tailor your CV to any job description in seconds. Upload your CV, paste a job description, and get a filtered, reordered, and tailored CV as a DOCX or PDF — without changing a single word of your original content.

---

## How it works

1. **Upload your CV** (PDF or DOCX) — the app parses it into structured data once
2. **Paste a job description** — the LLM scores each experience and project entry by relevance, picks the best ones, and generates a tailored summary
3. **Download or preview** — get your tailored CV as DOCX or PDF instantly

The app never rewrites your bullet points or descriptions. It only selects, filters, and reorders.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| LLM | Google Gemini (configurable) |
| Local LLM | Ollama |
| PDF extraction | PyMuPDF (fitz) |
| DOCX extraction | python-docx |
| Output generation | python-docx + WeasyPrint |
| Structured output | Pydantic v2 |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Docker + Railway |

---

## Project structure

```
cv-barber/
├── app/
│   ├── config.py               # settings from .env
│   ├── schemas/                # Pydantic models (BaseCV, MasterCV, TailoredCV)
│   ├── extraction/             # PDF and DOCX text extraction
│   ├── llm/                    # LLM clients, prompts, parser, scorer
│   ├── generation/             # DOCX and PDF output generation
│   ├── api/                    # FastAPI routes and session management
│   │   └── routes/             # /parse, /tailor, /download, /preview
│   └── static/                 # frontend (index.html, styles.css, app.js)
├── tests/                      # pytest test suite
├── scripts/                    # dev utilities (smoke test)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Local development

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/) (optional, for local LLM)

### Setup

```bash
# clone the repo
git clone https://github.com/MoaazEmam/CV-Barber.git
cd CV-Barber

# install dependencies
poetry install

# copy and fill in environment variables
cp .env.example .env
```

Edit `.env` — at minimum set your LLM provider and API key:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

### Run

```bash
poetry run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

### Using Ollama locally

```bash
# install and pull a model
ollama pull llama3.2

# set in .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### Run tests

```bash
poetry run pytest tests/ -v
```

---

## Docker

```bash
# build
docker build -t cv-barber .

# run
docker run -p 8000:8000 \
  -e LLM_PROVIDER=gemini \
  -e GEMINI_API_KEY=your_key \
  -e GEMINI_MODEL=gemini-3.1-flash-lite-preview \
  -e SESSION_STORE=memory \
  cv-barber
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `gemini` or `ollama` |
| `GEMINI_API_KEY` | — | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Gemini model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `SESSION_STORE` | `memory` | `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL (if SESSION_STORE=redis) |
| `TOP_N_EXPERIENCE` | `3` | Default max experience entries |
| `TOP_N_PROJECTS` | `5` | Default max project entries |
| `ENV` | `development` | `development` or `production` |

---

## Deployment

Deployed on [Railway](https://railway.app). Every push to `main` triggers a redeploy.

To deploy your own instance:

1. Fork this repo
2. Create a new project on Railway → Deploy from GitHub
3. Add environment variables in the Railway dashboard
4. Done — Railway builds the Docker image and gives you a public URL

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/parse` | Upload CV file → returns session ID |
| `POST` | `/api/tailor` | Tailor CV to job description → returns tailored session ID |
| `GET` | `/api/download/{id}?format=docx` | Download tailored CV as DOCX |
| `GET` | `/api/download/{id}?format=pdf` | Download tailored CV as PDF |
| `GET` | `/api/preview/{id}` | HTML preview of tailored CV |
| `GET` | `/api/health` | Health check |

Full interactive API docs available at `/docs` (FastAPI Swagger UI).

---

## Notes

- Sessions are stored in memory by default — they are lost when the server restarts. For persistent sessions across restarts or multiple containers, set `SESSION_STORE=redis`.
- The free tier of Gemini API has rate limits. For personal/low-volume use this is fine. For higher traffic, consider upgrading your API plan.
- No user data is stored permanently. CVs and job descriptions exist only in memory for the duration of your session.

---

## License

MIT
