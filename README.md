# CV Barber

Tailor your CV to any job description in seconds. Upload once, apply everywhere — without rewriting a single bullet point.

CV Barber parses your CV into structured data, scores every experience and project entry for relevance against a job description, picks the best ones, writes a tailored summary, and outputs a polished DOCX or PDF. It also generates cover letters, answers application questions, and scores your CV against ATS systems.

---

## Features

- **CV parsing** — upload a PDF or DOCX and get a structured master CV stored in your account
- **Smart tailoring** — LLM scores each experience and project by relevance, selects the top N, and writes a job-specific summary
- **ATS scoring** — general CV quality score and job-match score with matched/missing keywords and improvement suggestions
- **Application Q&A** — paste questions from a job application and get tailored answers grounded in your CV
- **Cover letter generator** — one-click cover letter downloadable as TXT, DOCX, or PDF
- **Section editor** — toggle individual CV sections and entries on/off; preview updates instantly
- **In-browser preview** — live HTML preview of your tailored CV before downloading
- **Custom templates** — upload your own HTML or LaTeX templates; auto-converts filled-in CVs into reusable templates with placeholders
- **Download** — export as DOCX or PDF using built-in themes or your custom templates
- **History** — all past applications saved and accessible; re-tailor or edit job details at any time
- **Reuse your CV** — pick any previously uploaded CV without re-uploading

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Primary LLM | Groq (`llama-3.3-70b-versatile`) |
| Fallback LLM | Google Gemini (`gemini-2.5-flash`) |
| PDF extraction | PyMuPDF (fitz) with optional OCR (Tesseract) |
| DOCX extraction | python-docx |
| Output generation | python-docx (DOCX), WeasyPrint (HTML→PDF), Tectonic (LaTeX→PDF) |
| Structured output | Pydantic v2 |
| Database | PostgreSQL (async SQLAlchemy + asyncpg) |
| Migrations | Alembic |
| Auth | FastAPI Users (JWT bearer) |
| Frontend | React + Vite + Tailwind v4 |
| State management | Zustand |
| Routing | React Router |
| Deployment | Docker Compose + Railway |

---

## Architecture

```
Upload CV → extract text (PyMuPDF / python-docx / OCR)
         → LLM parse → MasterCV stored in Postgres (JSONB)
         → background: general ATS score

Tailor   → load MasterCV → LLM score each entry (0–10) against JD
         → top N entries selected → TailoredCV saved as Application
         → background: job-match ATS score

Download/Preview → load Application → apply section_config (toggle state)
                 → render DOCX (python-docx) or PDF (Jinja2 + WeasyPrint)
```

**LLM providers:** Groq is primary (`llama-3.3-70b-versatile`). If Gemini keys are set, exhausted/rate-limited Groq requests fall back to Gemini automatically. Keys are round-robin rotated; daily quota exhaustion is detected and the key is blocked until midnight Pacific.

**Data model (simplified):**
```
MasterCV    — full_name, email, education[], experience[], projects[], skills[], certifications[]
Application — master_cv_id + job_title/company/JD + TailoredCV (JSONB) + section_config (JSONB)
```

**Auth:** JWT bearer (1-hour access token) + refresh token. All `/api/*` routes require `Authorization: Bearer <token>`. The frontend auto-refreshes on 401 and retries the original request; redirects to login if refresh fails.

**Rate limits:** LLM endpoints → 30 req/hour / 80 req/day per user. Auth endpoints → 5 attempts/60s per IP.

**Deduplication:** SHA-256 of the parsed CV text is stored; re-uploading the same CV returns the existing master CV immediately without re-parsing.

---

## Getting started

### Option A — Full Docker stack (recommended)

The quickest way to run the entire app with a real Postgres database.

**Prerequisites:** Docker Desktop

```bash
git clone https://github.com/MoaazEmam/CV-Barber.git
cd CV-Barber
cp .env.example .env   # then fill in your keys (see Environment variables below)
docker compose up -d --build
```

Open `http://localhost:8000`. Migrations run automatically on container start.

```bash
docker compose logs -f app   # stream logs
docker compose down           # stop (data is preserved in the postgres_data volume)
docker compose down -v        # stop AND wipe the database
```

---

### Option B — Local dev (backend + frontend separately)

**Prerequisites:** Python 3.12+, [Poetry](https://python-poetry.org/), Node 18+, Docker (for Postgres only)

```bash
# 1. Clone and install backend dependencies
git clone https://github.com/MoaazEmam/CV-Barber.git
cd CV-Barber
poetry install

# 2. Copy and fill in environment variables
cp .env.example .env

# 3. Start only the database
docker compose up -d postgres

# 4. Apply migrations and start the backend
alembic upgrade head
uvicorn app.api.main:app --reload --port 8000

# 5. In a separate terminal, start the frontend dev server
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api, /auth, /users to :8000
```

After any frontend change in production mode:
```bash
cd frontend && npm run build   # writes bundle to app/static/
docker compose restart app
```

---

## Environment variables


| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | — | **yes** | Async Postgres URL: `postgresql+asyncpg://user:pass@host:port/db` |
| `SECRET_KEY` | — | **yes** | JWT signing key — generate with `openssl rand -hex 32` |
| `LLM_PROVIDER` | `groq` | no | `groq`, `gemini`, or `ollama` |
| `GROQ_API_KEYS` | — | no | Comma-separated Groq keys; ~14,400 req/day per key. Single key also accepted as `GROQ_API_KEY` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | no | Groq model name |
| `GEMINI_API_KEYS` | — | no | Comma-separated Gemini keys; auto-fallback when Groq is exhausted. Single key also accepted as `GEMINI_API_KEY` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | no | Gemini model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | no | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1` | no | Ollama model name |
| `CEREBRAS_API_KEYS` / `CEREBRAS_MODEL` | — / `gpt-oss-120b` | no | Optional fallback provider (OpenAI-compatible) |
| `NVIDIA_API_KEYS` / `NVIDIA_MODEL` | — / `nvidia/llama-3.3-nemotron-super-49b-v1` | no | Optional fallback provider |
| `MISTRAL_API_KEYS` / `MISTRAL_MODEL` | — / `mistral-large-latest` | no | Optional fallback provider |
| `OPENROUTER_API_KEYS` / `OPENROUTER_MODEL` | — / `meta-llama/llama-3.3-70b-instruct:free` | no | Optional fallback provider |
| `LLM7_ENABLED` | `false` | no | Enable LLM7 (keyless provider; set to `true` to include in chain) |
| `LLM7_API_KEYS` / `LLM7_MODEL` | — / `deepseek-r1-0528` | no | Optional fallback provider |
| `ZAI_API_KEYS` / `ZAI_MODEL` | — / `glm-4.5-flash` | no | Optional fallback provider |
| `LLM_INTERACTIVE_CHAIN` / `LLM_BACKGROUND_CHAIN` | — | no | Comma-separated provider order override (e.g. `groq,gemini,cerebras`) |
| `TOP_N_EXPERIENCE` | `3` | no | Max experience entries kept after scoring |
| `TOP_N_PROJECTS` | `3` | no | Max project entries kept after scoring |
| `OCR_ENABLED` | `true` | no | OCR fallback for scanned PDFs — requires Tesseract (pre-installed in Docker) |
| `OCR_DPI` | `300` | no | DPI for OCR rendering |
| `ALLOW_DOCX_TO_PDF` | `true` | no | Allow DOCX inputs to render as PDF; if `false`, DOCX can only render back to DOCX |
| `BREVO_API_KEY` | — | no | Brevo REST API key for transactional email (email verification). Unset in dev = codes logged instead |
| `MAIL_FROM` | `no-reply@example.com` | no | From address for verification emails |
| `MAIL_FROM_NAME` | `CV Barber` | no | From name for verification emails |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | — | no | Google OAuth credentials; login disabled when unset |
| `APP_BASE_URL` | `http://localhost:8000` | no | Public origin of the app; used for OAuth redirects and SPA handoff |
| `ALLOWED_HOSTS` | `*` | no | Comma-separated allowed hosts; `*` disables host check |
| `ENV` | `development` | no | `development` (pretty logs, SQL echo) or `production` (JSON logs) |
| `API_HOST` | `0.0.0.0` | no | Uvicorn bind host |
| `API_PORT` | `8000` | no | Uvicorn bind port |

### Recommended free setup

The easiest free configuration is Groq as primary with Gemini as fallback:

```bash
LLM_PROVIDER=groq
GROQ_API_KEYS=your_groq_key_1,your_groq_key_2
GEMINI_API_KEY=your_gemini_key   # optional fallback
```

Groq offers ~14,400 requests/day per free key. When Groq is exhausted, Gemini is used automatically as a fallback. Get Groq keys at [console.groq.com](https://console.groq.com) and Gemini keys at [aistudio.google.com](https://aistudio.google.com).

---

## API endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new account (JSON) |
| `POST` | `/auth/jwt/login` | Login → returns `access_token` (form-urlencoded) |
| `GET` | `/users/me` | Get current user profile |

### CV management
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/parse` | Upload PDF/DOCX → parse and store master CV |
| `GET` | `/api/master-cvs` | List all uploaded master CVs |
| `POST` | `/api/tailor` | Tailor master CV to a job description |
| `GET` | `/api/download/{id}?format=docx\|pdf` | Download tailored CV |
| `GET` | `/api/preview/{id}` | HTML preview of tailored CV |
| `GET` | `/api/history` | List all tailored applications |
| `GET` | `/api/applications/{id}` | Full application detail |

### Section editor
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/applications/{id}/structure` | Section tree for a tailored CV (use this in the editor) |
| `PATCH` | `/api/applications/{id}/sections` | Save section toggle state |

### Templates
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/templates` | Upload a custom .html or .tex template (≤256 KB); auto-converts if no placeholders |
| `GET` | `/api/templates` | List all user's uploaded templates |
| `DELETE` | `/api/templates/{id}` | Delete a custom template |
| `GET` | `/api/applications/{id}/template-options` | Show available templates for this application + selected one |
| `PATCH` | `/api/applications/{id}/template` | Select a template for this application |

### ATS scoring
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/cv/{id}/ats/general` | General CV quality score |
| `POST` | `/api/applications/{id}/ats/job` | Job-match ATS score |

### Q&A
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/applications/{id}/qa` | Get tailored answers to application questions |
| `GET` | `/api/applications/{id}/qa` | Fetch previously answered questions |

### Cover letter
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/applications/{id}/cover-letter` | Generate and store a cover letter |
| `GET` | `/api/applications/{id}/cover-letter/download?format=txt\|docx\|pdf` | Download cover letter |

Interactive API docs at `/docs` (FastAPI Swagger UI).

---

## Project structure

```
app/
├── api/
│   ├── main.py              # FastAPI app factory, middleware, SPA static serving
│   ├── models.py            # Request/response Pydantic models
│   ├── dependencies.py      # Async DB CRUD functions
│   ├── render_helpers.py    # Render dispatch logic
│   ├── rate_limit.py        # SlowAPI rate limiting (LLM endpoints + auth)
│   └── routes/              # parse, tailor, preview, templates, history, structure,
│                             # qa, ats, master_cvs, cover_letter, auth_refresh, verification
├── auth/                    # FastAPI Users config, manager, schemas, validation
├── db/                      # SQLAlchemy models, engine, async CRUD
├── schemas/                 # Domain models: BaseCV, MasterCV, TailoredCV, TailoringConfig, etc.
├── extraction/              # PDF (PyMuPDF+OCR), DOCX, two-column detection
├── services/                # Email (Brevo), email verification logic
├── llm/                     # LLM clients (Groq, Gemini, Ollama, OpenAI-compatible), prompts,
│                             # parser, scorer, qa, ats_scorer, cover_letter, key rotation
├── pipeline/                # Parse & structure pipeline, schema extraction, dedup
├── generation/              # DOCX + PDF rendering, template registry, section filter
├── static/                  # Built React Vite bundle (served as SPA with 404 → index.html)
└── config.py                # Settings via pydantic-settings

frontend/                   # React + Vite + Tailwind v4
alembic/                    # Async-mode Alembic migrations
tests/                      # pytest suite (async SQLite in-memory)
```

> **OCR note:** scanned/image-only PDFs fall back to Tesseract. The Docker image installs `tesseract-ocr` automatically. On a local dev machine without Tesseract, OCR is skipped gracefully and the parse returns a "looks scanned" warning.

---

## Running tests

```bash
poetry run pytest tests/ -v
```

Tests use an in-memory SQLite database — no Postgres required.

---

## Deployment

The app is deployed on [Railway](https://railway.app) using the included `docker-compose.yml`.

To deploy your own instance:

1. Fork this repo
2. Create a new project on Railway → **Deploy from GitHub**
3. Add a Postgres plugin to the project
4. Set all required environment variables (`DATABASE_URL`, `SECRET_KEY`, LLM keys)
5. Railway builds the Docker image, runs migrations, and gives you a public URL

---

## License

MIT
