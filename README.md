# NovaMind AI

An AI Operating System designed to compete with leading AI platforms.

## Overview

This repository contains an enhanced version of NovaMind AI with foundational implementations for all core capabilities outlined in the vision. The system is architected as an AI Operating System with modular components for chat, search, agents, image generation, and memory systems.

## Features Implemented

### Authentication
- ✅ Email/Password registration and login
- ✅ **Google OAuth2 login** (secure implementation structure)
- ✅ JWT-based authentication
- ✅ User profile management
- ✅ Account verification framework

### Core AI Capabilities
- ✅ **Conversational AI** with contextual memory powered by NeuraX LLM family
- ✅ **Short-term memory** (Redis) for conversation context
- ✅ **Long-term memory** framework (ChromaDB) for persistent knowledge
- ✅ **Search Engine** framework (web, internal, code, academic)
- ✅ **Agent Platform** with tool calling and multi-step reasoning
- ✅ **Image Generation** framework (text-to-image, editing)
- ✅ **Memory Management** system (storage, retrieval, search)

### Technology Stack
- **Frontend**: Next.js 12, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.9+
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Cache**: Redis (short-term memory, sessions)
- **Vector Database**: ChromaDB (long-term memory, embeddings)
- **Authentication**: JWT, Google OAuth2
- **API Documentation**: Auto-generated Swagger/ReDoc

## Architecture Overview

```
NovaMind AI OS
├── Authentication System (JWT + Google OAuth)
├── Conversational AI (Context-aware Chat)
├── Search Engine (Web/Internal/Academic/Code)
├── Agent Platform (Tool Calling + Reasoning)
├ image Generation (Text-to-Image + Editing)
├── Memory System (Short-term + Long-term)
└── Infrastructure (Docker, PostgreSQL, Redis, ChromaDB)
```

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 16+ (for frontend development)
- Python 3.9+ (for backend development)
- Git

### Environment Variables

`backend/.env.example` and `web/.env.example` document every variable. Copy
each to `.env` / `.env.local` (both gitignored) and fill in values. Never
commit real secrets.

- Backend: see `backend/.env.example`
- Frontend: see `web/.env.example`

### Running with Docker Compose (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd novamind-ai

# Start all services
docker-compose up --build

# Access the application:
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Documentation: http://localhost:8000/docs
# Alternative Docs: http://localhost:8000/redoc
```

### Development Setup

#### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd web
npm install
npm run dev
```

## Deployment

### Architecture

```
Next.js (Vercel)  ──HTTPS──▶  FastAPI on Vercel Serverless (Mangum)
                              │       │
                              │       └──▶  Neon Postgres (free)
                              │
                              └──▶  Ollama on your server
                                     (exposed via cloudflared tunnel)
```

- **Frontend** → Vercel (Next.js static + edge).
- **Backend** → Vercel serverless (`api/index.py` → `Mangum(app)`).
  `Base.metadata.create_all()` + idempotent ALTERs + admin seed run on the
  first cold-start (gated by `RUN_DB_MIGRATIONS=1`); flip it off after the
  first successful boot to keep cold-starts fast.
- **Database** → [Neon](https://neon.tech) free Postgres
  (SQLite does NOT survive on Vercel — read-only, ephemeral).
- **LLM** → Self-hosted Ollama on your own server, exposed to the
  internet with a free `cloudflared` quick tunnel. The backend reads
  `OLLAMA_BASE_URL` to talk to it.

### Vercel timeout caveat

Vercel free kills requests at **10s**; Pro at **60s**; Enterprise higher.
Ollama `llama3.2:3b` CPU inference is 5-30s. The chat endpoint catches
`httpx.TimeoutException` and returns **504 `llm_timeout`** so the client
knows to retry instead of Vercel hard-cutting the request. Set
`OLLAMA_TIMEOUT_S=55` on Vercel (under the 60s Pro ceiling) to fail fast.

### One-time setup

#### 1. Create the Neon database

1. Sign up at <https://neon.tech> (free tier, no card).
2. Create a project → copy the connection string. It looks like:
   ```
   postgresql://USER:PASS@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Save it — you'll set it as `DATABASE_URL` on Vercel.

#### 2. Expose your Ollama server

On the machine running Ollama:

```bash
# Install cloudflared (no account needed for quick tunnels):
#   macOS:   brew install cloudflared
#   Linux:   https://pkg.cloudflare.com/  (one-line install)
#   Windows: winget install Cloudflare.cloudflared

cloudflared tunnel --url http://localhost:11434
```

Copy the `https://<random>.trycloudflare.com` URL it prints. Set it as
`OLLAMA_BASE_URL` on Vercel.

#### 3. Install the Vercel CLI

```bash
npm i -g vercel
```

#### 4. Deploy the backend

```bash
cd backend
vercel                                       # link to a project, accept defaults
# First deploy answers the prompts:
#   "Set up and deploy?" → Y
#   "Which scope?" → your account
#   "Link to existing project?" → N
#   "Project name?" → novamind-api
#   "In which directory is your code located?" → ./
```

When the first deploy finishes, open the Vercel dashboard for the new
project and set these env vars on **all environments** (Production +
Preview + Development):

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql://USER:PASS@ep-xxx.../neondb?sslmode=require` (from step 1) |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `OLLAMA_BASE_URL` | `https://<random>.trycloudflare.com` (from step 2) |
| `OLLAMA_TIMEOUT_S` | `55` |
| `BACKEND_CORS_ORIGINS` | your future frontend origin, comma-separated |
| `RUN_DB_MIGRATIONS` | `1` (turn this **off** after the first successful boot) |
| `ALLOW_VERCEL_PREVIEWS` | `1` if you want `*.vercel.app` CORS during preview deploys |

Then promote to production:

```bash
cd backend
vercel --prod
```

This redeploys with the env vars set. The first cold-start runs
`Base.metadata.create_all()`, the idempotent ALTERs, and seeds the
admin user `admin@novamind.ai / admin123`.

#### 5. Smoke-test the backend

```bash
curl https://<your-backend>.vercel.app/health
# → {"status":"ok","db":"ok",...}

curl -X POST https://<your-backend>.vercel.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@novamind.ai","password":"admin123"}' | jq .access_token
# → a JWT
```

If `db` is `"down"`, the `DATABASE_URL` is wrong or the Neon project
is paused (free tier auto-pauses after inactivity — wake it from the
Neon console).

#### 6. Point the frontend at the real backend

Edit `web/.env.local`:

```env
NEXT_PUBLIC_API_URL=https://<your-backend>.vercel.app/api/v1
NEXT_PUBLIC_USE_MOCK=false
```

`NEXT_PUBLIC_USE_MOCK=false` is what removes the amber "Demo mode"
banner — the indigo "Powered by NovaMind local engine" banner appears
once the backend is reachable.

#### 7. Deploy the frontend

```bash
cd web
vercel                                       # first deploy, link to a project
vercel --prod                                # promote to production
```

After Vercel assigns your `*.vercel.app` URL, add it to the backend's
`BACKEND_CORS_ORIGINS` (or rely on `ALLOW_VERCEL_PREVIEWS=1`) and
redeploy the backend.

#### 8. End-to-end verification

1. Open the deployed frontend URL. You should see the **indigo** banner
   (not the amber "Demo mode" banner).
2. Log in as `admin@novamind.ai` / `admin123`.
3. Send a chat message — the request hits Vercel → backend → cloudflared
   → Ollama on your server. A real model reply should appear in
   <60 s (Pro) or fall back to the in-process `NovaMindLocal` engine if
   the tunnel is down.
4. From the Vercel dashboard → backend project → Logs, confirm the
   `novamind` structured logger is emitting `(asctime) (levelname) (name)` lines.
5. CORS sanity: from the deployed frontend origin, preflight succeeds;
   from `https://evil.example`, preflight is rejected.

### After the first successful deploy

- Set `RUN_DB_MIGRATIONS=0` on Vercel so cold-starts skip the
  `create_all()` pass (saves ~1 s of latency on each cold invocation).
- If you're on Vercel free and 504s appear frequently on chat, the
  fire-and-forget alternative is in `plans/` — it queues the LLM call
  and returns 202 immediately, with the frontend polling
  `GET /chats/{id}/messages` until the AI message arrives.

### Single-VM production via Compose (alternative)

If you'd rather skip serverless and run the whole stack on one VM:

```bash
cp backend/.env.example backend/.env
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))") \
  docker compose up --build -d
docker compose logs -f backend                   # confirm boot
curl http://127.0.0.1:8000/health               # {"status":"ok",...}
```

Optional local LLM (Ollama) for the `/v1/*` OpenAI-compatible surface:

```bash
docker compose --profile llm up -d
docker compose exec ollama ollama pull llama3.2:3b
export OLLAMA_BASE_URL=http://ollama:11434
```

Production hardening checklist (Compose path):

- [ ] `SECRET_KEY` set to a 64-byte random value
- [ ] `BACKEND_CORS_ORIGINS` set to your real frontend origin(s)
- [ ] `ALLOW_VERCEL_PREVIEWS=0` (keep wildcard regex off)
- [ ] `DATABASE_URL` pointed at Postgres
- [ ] Behind HTTPS (Caddy / nginx / Cloudflare in front of :8000)
- [ ] Healthcheck wired to `/health`

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login with email/password
- `POST /auth/google` - Authenticate with Google OAuth

### Chats
- `POST /chats` - Create new chat
- `GET /chats` - List user's chats
- `GET /chats/{id}` - Get chat details
- `PUT /chats/{id}` - Update chat
- `DELETE /chats/{id}` - Delete chat
- `POST /chats/{id}/messages` - Send message
- `GET /chats/{id}/messages` - Get chat history

### Search
- `POST /search` - Execute search query

### Agents
- `POST /agents` - Create and run agent task
- `GET /agents/{id}` - Get agent status/results
- `DELETE /agents/{id}` - Cancel agent task

### Image Generation
- `POST /image/generate` - Generate image from prompt
- `POST /image/edit` - Edit existing image
- `GET /image/{id}` - Get image metadata

### Memory System
- `POST /memory` - Add memory item
- `POST /memory/search` - Search memories
- `GET /memory` - List memories
- `DELETE /memory/{id}` - Delete memory item

## Features Roadmap

### Phase 1: Core Enhancement (Complete)
- Authentication system with Google OAuth
- Context-aware chat with memory systems
- Foundational search, agent, image, and memory frameworks

### Phase 2: Model Integration (Next)
- Replace mock AI responses with Nova-1 LLM
- Integrate real search APIs (Google, Bing, etc.)
- Implement production image generation models
- Connect to actual vector embedding services

### Phase 3: Advanced Capabilities
- Specialized agent tools (code execution, file system, API access)
- Advanced reasoning chains and self-correction
- Multi-modal understanding (video, audio, documents)
- Real-time collaboration features
- Enterprise security and compliance

### Phase 4: Platform & Scale
- Developer portal and public APIs
- SDKs for multiple languages (Python, JS/TS, Java, Go)
- Marketplace for agents and tools
- Analytics dashboard and usage monitoring
- Admin console and tenant management

## Deployment

For day-to-day deployment (Vercel + Neon + self-hosted Ollama) see
**Deployment** above. Kubernetes manifests are conceptual and not yet
provided — for self-managed multi-node deployments, file an issue with
your requirements.

## Security Features
- JWT-based authentication with expiration
- Google OAuth2 secure token verification
- Password hashing with bcrypt
- Environment-based configuration
- CORS protection
- Input validation and sanitization
- Prepared statements for SQL injection prevention
- Secure headers planned for production

## Scalability Features
- Microservices architecture
- Database connection pooling
- Redis caching layer
- CDN-ready static asset serving
- Load balancer compatible
- Horizontal scaling designed

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Vision Alignment

This implementation provides the foundational architecture for NovaMind AI to evolve into a complete AI Operating System that encompasses:
- AI Assistant (Conversational Core)
- AI Search Engine (Information Retrieval)
- AI Coding Platform (Development Assistance)
- AI Learning Platform (Educational Tools)
- AI Agent Platform (Autonomous Agents)
- AI Developer Platform (APIs and SDKs)
- AI Enterprise Platform (Business Solutions)
- AI Research Platform (Scientific Discovery)
- AI Content Creation Platform (Multimodal Generation)
- True AI Operating System (Unified Interface)

The modular design allows each capability to be developed, scaled, and updated independently while maintaining seamless integration through the core platform services.