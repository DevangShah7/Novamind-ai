# NovaMind AI - Comprehensive Documentation

## Overview
NovaMind AI is a comprehensive AI Operating System that combines advanced AI capabilities with cybersecurity features, voice assistance, and a extensible agent platform. Built with a modular architecture, it provides a foundation for creating intelligent AI assistants with enterprise-grade security and compliance features.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Key Features](#key-features)
3. [Technical Components](#technical-components)
4. [API Endpoints](#api-endpoints)
5. [Deployment Guide](#deployment-guide)
6. [Development Setup](#development-setup)
7. [Usage Examples](#usage-examples)
8. [Security Considerations](#security-considerations)
9. [Extensibility](#extensibility)
10. [FAQ](#faq)

---

## System Architecture

NovaMind AI follows a microservices-inspired modular architecture with clearly defined layers:

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (Web)                     │
│  - Next.js React Application                        │
│  - Voice Controls & Media Components                │
│  - Chat Interface                                   │
│  - Admin Dashboard                                  │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/REST API
┌─────────────────────▼───────────────────────────────┐
│                  Backend API                        │
│  - FastAPI Application                              │
│  - Authentication & Authorization                   │
│  - Rate Limiting & Usage Logging                    │
│  - Core Services Layer                              │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────▼─────────────┐
        │     Core Services         │
        │  - LLM Service (NeuraX)   │
        │  - Speech Service         │
        │  - Reasoning Service      │
        │  - Security Execution     │
        │  - Audit Logging          │
        │  - Usage Logging          │
        │  - Rate Limiting          │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │     Infrastructure        │
        │  - PostgreSQL Database    │
        │  - Redis Cache            │
        │  - ChromaDB Vector Store  │
        │  - Docker (for security)  │
        └───────────────────────────┘
```

## Key Features

### 1. 🧠 Advanced AI Capabilities
- **NeuraX LLM Family**: Base, Code, Creative, and Analysis models
- **Advanced Reasoning**: Chain-of-Thought, Tree-of-Thoughts, Self-Consistency, Debate, Reflection, Refinement
- **Contextual Memory**: Short-term and long-term memory systems
- **Multimodal Ready**: Framework for image/audio/video understanding

### 2. 🔒 Cybersecurity Assistant
- **Security-Focused Agents**:
  - Vulnerability Scanner Agent
  - Secure Code Reviewer Agent
  - Threat Analyst Agent
  - Security Researcher Agent
- **Secure Execution Environment**: Docker-based sandboxing with process fallback
- **Immutable Audit Logging**: Tamper-evident logs with hash chaining
- **Real Tool Integration**: Works with Bandit, Semgrep, Safety, Trivy when available

### 3. 🎙️ Voice Assistance
- **Speech-to-Text**: Ready for Whisper API or local models
- **Text-to-Speech**: Ready for ElevenLabs, Coqui TTS, or local models
- **Voice Controls**: Microphone input and audio playback components

### 4. 👨‍💻 Developer Platform
- **API Key Authentication**: With usage tracking and rate limiting
- **Extensible Agent Platform**: Custom agent types and tool integration
- **Comprehensive API Docs**: Auto-generated Swagger/OpenAPI documentation
- **Webhooks & Events**: Real-time capabilities ready

### 5. 📊 Enterprise Features
- **Role-Based Access Control**: Admin/user roles with permissions
- **Usage Analytics**: Detailed API usage tracking and metrics
- **Admin Dashboard**: User management and system statistics
- **Compliance Ready**: Audit trails for regulatory requirements

---

## Technical Components

### Backend Services

#### 1. LLM Service (`backend/app/core/llm_service.py`)
- Abstract base class for LLM implementations
- NeuraX model family: Base, Code, Creative, Analysis
- ExampleLLMService for testing/development
- Dependency injection pattern for easy swapping

#### 2. Speech Service (`backend/app/core/speech_service.py`)
- `SpeechService` abstract base class
- `WhisperSpeechService` implementation (API-ready)
- `SpeechServiceFactory` for service instantiation
- `speech_to_text()` and `text_to_speech()` convenience functions

#### 3. Reasoning Service (`backend/app/core/reasoning_service.py`)
- `ReasoningService` enhances any LLM with advanced reasoning
- Six reasoning strategies implemented:
  - Chain-of-Thought (CoT)
  - Tree-of-Thoughts (ToT)
  - Self-Consistency
  - Debate
  - Reflection
  - Refinement
- `apply_reasoning()` convenience function

#### 4. Security Execution (`backend/app/core/security_execution.py`)
- `SecurityExecutor` abstract base class
- `DockerSecurityExecutor` for containerized sandboxing
- `ProcessSecurityExecutor` for OS-level restrictions (fallback)
- `SecurityExecutorFactory` for executor creation
- `SecurityToolExecutor` for common security tools (Bandit, Semgrep, etc.)

#### 5. Audit Logging (`backend/app/core/audit_logging.py`)
- `AuditEvent` dataclass for structured events
- `AuditLevel` enum (INFO, WARNING, ERROR, SECURITY, COMPLIANCE)
- `AuditStorage` abstract base class
- `ImmutableAuditStorage` with hash chaining
- `AuditLogger` main logging service
- Convenience functions for common event types

### Frontend Components

#### Pages
- `login.tsx`: Authentication with Google OAuth
- `signup.tsx`: User registration
- `chat/[id].tsx`: Individual chat interface
- `chat/index.tsx`: Chat list
- `admin/index.tsx`: Admin dashboard

#### Components
- `MessageInput.tsx`: Message input with voice/button controls
- `MessageList.tsx`: Message display with playback controls
- `ChatList.tsx`: Chat listing component
- Layout and admin components

#### Libraries
- `api.ts`: API service functions
- `auth.ts`: Authentication context and utilities
- `voice.ts`: Voice service integration (placeholder)
- `media.ts`: Media handling utilities (placeholder)
- `security.ts`: Security API integration (placeholder)
- `types.ts`: TypeScript interfaces

---

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - Email/password login
- `POST /auth/google` - Google OAuth authentication
- `POST /auth/refresh` - Refresh access token

### Chats
- `POST /chats` - Create new chat
- `GET /chats` - List user's chats
- `GET /chats/{id}` - Get specific chat
- `POST /chats/{id}/messages` - Send message to chat
- `GET /chats/{id}/messages` - Get chat messages

### Agent Platform
- `POST /agents` - Create and run agent task
- `GET /agents/{agent_id}` - Get agent status/results
- `DELETE /agents/{agent_id}` - Cancel agent task

### API Keys
- `POST /api-key` - Create new API key
- `GET /api-key` - List user's API keys
- `GET /api-key/{key_id}` - Get specific API key
- `GET /api-key/{key_id}/usage` - Get usage statistics
- `GET /api-key/usage/summary` - Get usage summary

### Search
- `POST /search` - Perform search query
- `POST /search/vectors` - Store vector embeddings

### Image Generation
- `POST /image/generate` - Generate image from prompt

### Memory
- `POST /memory` - Store memory item
- `GET /memory` - Retrieve memory items
- `DELETE /memory/{id}` - Delete memory item

### Admin
- `GET /admin/users` - List all users
- `GET /admin/stats` - Get system statistics

---

## Deployment Guide

### Prerequisites
- Docker and Docker Compose
- Git
- Node.js 16+ (for frontend)
- Python 3.9+ (for backend)
- PostgreSQL 13+ (optional, uses Docker)
- Redis 6+ (optional, uses Docker)

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd novamind-ai
   ```

2. **Set up environment variables**:
   ```bash
   # Backend
   cp backend/.env.template backend/.env
   # Edit backend/.env with your values

   # Frontend
   cp web/.env.template web/.env.local
   # Edit web/.env.local with your values
   ```

3. **Start the services**:
   ```bash
   docker-compose up --build
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Production Deployment

#### Option 1: Docker Compose (Recommended)
```bash
# Build and start in production mode
docker-compose -f docker-compose.yml up --build -d

# Stop and remove
docker-compose down
```

#### Option 2: Kubernetes
The docker-compose.yml can be converted to Kubernetes manifests using tools like Kompose.

#### Option 3: Vercel (Frontend Only)
The frontend is a Next.js app ready for Vercel:
1. Push to GitHub
2. Import project in Vercel
3. Set environment variable: `NEXT_PUBLIC_API_URL` (your backend URL)
4. Deploy

**Note**: For full deployment on Vercel, you would need to:
- Deploy backend to a service that supports FastAPI (AWS, GCP, Azure, or traditional VPS)
- Update `NEXT_PUBLIC_API_URL` to point to your deployed backend

#### Option 4: GitHub Actions CI/CD
GitHub Actions workflow can be set up to:
- Run tests on push/pull request
- Build and push Docker images
- Deploy to staging/production environments

### Environment Variables

#### Backend (`backend/.env`)
```
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=480
DATABASE_URL=postgresql://postgres:postgres@db:5432/postgres
REDIS_URL=redis://redis:6379
CHROMA_HOST=chroma
CHROMA_PORT=8000
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://yourdomain.com/api/v1/auth/google/callback
```

#### Frontend (`web/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Development Setup

### Backend Development
1. Create virtual environment:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run tests:
   ```bash
   python -m pytest
   ```

4. Run development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Development
1. Install dependencies:
   ```bash
   cd web
   npm install
   ```

2. Run development server:
   ```bash
   npm run dev
   ```

3. Run tests:
   ```bash
   npm test
   ```

4. Build for production:
   ```bash
   npm run build
   ```

---

## Usage Examples

### Creating and Running a Security Agent

```python
import requests
import json

# First, authenticate to get a token
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "user@example.com", "password": "password123"}
)
access_token = login_response.json()["access_token"]

# Create a vulnerability scanner agent
agent_response = requests.post(
    "http://localhost:8000/api/v1/agents",
    json={
        "task": "Scan my web application for security vulnerabilities",
        "agent_type": "vulnerability_scanner",
        "context": "Internal security assessment",
        "max_steps": 5
    },
    headers={"Authorization": f"Bearer {access_token}"}
)
agent_id = agent_response.json()["agent_id"]

# Check agent status
status_response = requests.get(
    f"http://localhost:8000/api/v1/agents/{agent_id}",
    headers={"Authorization": f"Bearer {access_token}"}
)

# When completed, get results
if status_response.json()["status"] == "completed":
    result_response = requests.get(
        f"http://localhost:8000/api/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print(result_response.json()["result"])
```

### Using Advanced Reasoning

```python
import requests
import json

# Get authentication token (as above)
# ...

# Send a chat message with reasoning
chat_response = requests.post(
    "http://localhost:8000/api/v1/chats",
    json={
        "title": "Complex Problem Solving",
        "messages": [
            {
                "role": "user",
                "content": "How can I improve the security of my Python web application?",
                "metadata": {
                    "use_reasoning": True,
                    "reasoning_strategy": "tree_of_thoughts"
                }
            }
        ]
    },
    headers={"Authorization": f"Bearer {access_token}"}
)
```

### Voice Interaction (Conceptual - requires frontend implementation)

```javascript
// In your frontend code
import { useVoice } from '@/lib/voice';

// Example usage in a React component
function ChatInput() {
  const { 
    isListening, 
    transcript, 
    startListening, 
    stopListening,
    isSpeaking,
    speakText
  } = useVoice();

  const handleVoiceInput = async () => {
    if (!isListening) {
      await startListening();
    } else {
      const text = await stopListening();
      // Send text to chat API
    }
  };

  const handleSpeakResponse = async (text) => {
    await speakText(text);
  };

  return (
    <div>
      <button onClick={handleVoiceInput}>
        {isListening ? '🔴 Listening...' : '🎤 Speak'}
      </button>
      {transcript && <div>{transcript}</div>}
    </div>
  );
}
```

---

## Security Considerations

### 1. Authentication & Authorization
- JWT-based authentication with refresh tokens
- Password hashing using bcrypt
- Google OAuth 2.0 integration
- Role-based access control (admin vs regular users)
- API key authentication with usage tracking

### 2. Data Protection
- HTTPS/TLS enforcement in production
- Passwords never stored in plaintext
- Sensitive data encryption at rest (configurable)
- Secure headers implementation (CSP, HSTS, etc.)

### 3. Network Security
- Rate limiting to prevent abuse
- CORS policies configured per environment
- Input validation and sanitization
- SQL injection prevention via ORM/parameterized queries

### 4. Application Security
- Secure execution environment for security tools
- Immutable audit logging for compliance
- Regular dependency updates
- Security scanning integrated into development workflow

### 5. Deployment Security
- Docker containerization with minimal privileges
- Read-only root filesystem in containers
- Network isolation for security tool execution
- Resource limits (CPU, memory) on containers
- Non-root user execution where possible

---

## Extensibility

### Adding New LLM Models
1. Create a new class inheriting from `BaseLLMService`
2. Implement the required methods (`agenerate`, `astream`)
3. Register the new service in `get_llm_service()` if needed
4. Update the NeuraX model family exports in `__init__.py`

### Adding New Reasoning Strategies
1. Add new method to `ReasoningService` class
2. Update `ReasoningStrategy` enum
3. Add strategy to `apply_reasoning()` function
4. Write unit tests for the new strategy

### Adding New Security Tools
1. Add tool to `_get_available_security_tools()` list
2. Create executor method in `SecurityToolExecutor` (if needed)
3. Update agent implementations to use the new tool
4. Add documentation and examples

### Adding New Frontend Features
1. Create new components in `/web/components/`
2. Add new pages in `/web/pages/`
3. Update routing in Next.js
4. Add state management as needed
5. Write tests for new components

### Adding New API Endpoints
1. Create new router in `/backend/app/api/endpoints/`
2. Implement endpoints with proper dependency injection
3. Add Pydantic models for request/validation
4. Include router in `/backend/app/api/v1.py`
5. Add OpenAPI documentation via docstrings
6. Write integration tests

---

## Frequently Asked Questions

### Q: Is NovaMind AI completely free from external API dependencies?
A: The core system is designed to work without external API keys. Speech services and some advanced features can work with local models/tools. However, for production use of certain features (like premium TTS voices), you may want to integrate with external services.

### Q: Can I use NovaMind AI without Docker?
A: Yes! The system includes fallback mechanisms:
- `ProcessSecurityExecutor` works without Docker
- You can use SQLite instead of PostgreSQL (modify DATABASE_URL)
- Local storage can be used instead of Redis for basic caching
- ChromaDB can work in embedded mode

### Q: How do I make the speech services work with local models?
A: 
1. For Speech-to-Text: Install Whisper.cpp or similar and implement `LocalWhisperSpeechService`
2. For Text-to-Speech: Install Coqui TTS or similar and implement `LocalCoquiTTSService`
3. Update `SpeechServiceFactory` to use your local implementations

### Q: What security tools should I install for real vulnerability scanning?
A: Recommended tools:
```bash
pip install bandit semgrep safety
# For Trivy, download from: https://github.com/aquasecurity/trivy/releases
```

### Q: How scalable is NovaMind AI?
A: The system is designed for horizontal scaling:
- Stateless backend services can be load-balanced
- Redis can be clustered for shared cache
- PostgreSQL can be replicated for read scaling
- ChromaDB supports distributed deployments
- Frontend can be served via CDN

### Q: Is NovaMind AI compliant with GDPR/HIPAA/etc?
A: The system includes features to support compliance:
- Immutable audit logging with hash chaining
- Data access logging and monitoring
- User data export/deletion capabilities
- Consent tracking framework
- However, full compliance requires proper configuration and additional legal/administrative measures

### Q: Can I deploy just the backend as a microservice?
A: Absolutely! The backend is designed to be deployed independently:
- It provides a complete REST API
- Authentication is JWT-based (stateless)
- All state is stored in the database/cache
- Can be scaled horizontally behind a load balancer

### Q: How do I contribute to NovaMind AI?
A: 
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Ensure all existing tests pass
6. Submit a pull request
7. Follow the code style and conventions

---

## Conclusion

NovaMind AI provides a powerful, extensible foundation for building AI-powered applications with enterprise-grade security and compliance features. Its modular architecture allows for easy customization and extension while maintaining a clean separation of concerns.

Whether you're building a personal AI assistant, an enterprise chatbot, or a specialized AI agent platform, NovaMind AI gives you the tools and framework to create intelligent, secure, and scalable solutions.

For the most up-to-date information, please refer to the source code and inline documentation throughout the project.