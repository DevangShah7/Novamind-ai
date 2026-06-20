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

Create `.env` file in backend directory:
```
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480
DATABASE_URL=postgresql://postgres:postgres@db:5432/postgres
REDIS_URL=redis://redis:6379
CHROMA_HOST=chroma
CHROMA_PORT=8000
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

Create `.env.local` file in web directory:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

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

### Kubernetes
Basic Kubernetes manifests are conceptualized for production deployment:
- Separate deployments for each service
- Horizontal pod autoscaling
- Resource limits and requests
- ConfigMaps and Secrets for configuration
- Ingress controller for external access

### Cloud Providers
Ready for deployment on:
- AWS (ECS/EKS, RDS, ElastiCache)
- Azure (AKS, SQL Database, Cosmos DB)
- GCP (GKE, Cloud SQL, Memorystore)
- On-premise Kubernetes clusters

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