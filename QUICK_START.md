# NovaMind AI - Quick Start Guide

Get NovaMind AI up and running in minutes with this quick start guide.

## 🚀 5-Minute Local Setup

### Prerequisites
- Docker and Docker Compose
- Git

### Step 1: Clone and Setup
```bash
git clone <repository-url>
cd novamind-ai

# Copy environment templates
cp backend/.env.template backend/.env
cp web/.env.template web/.env.local
```

### Step 2: Start Services
```bash
docker-compose up --build
```

### Step 3: Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Step 4: Login
- **Email**: admin@novamind.ai
- **Password**: admin123
- **Important**: Change password immediately after first login!

## 🔑 Default Admin Credentials
```
Email: admin@novamind.ai
Password: admin123
```

## 🧪 Quick Feature Tests

### Test Voice Features (Conceptual)
In the chat interface, look for the microphone button (voice features require frontend implementation).

### Test Advanced Reasoning
1. Create a new chat
2. Send a complex question like: "How can I improve the security of my Python web application?"
3. Look for reasoning indicators in the AI response

### Test Cybersecurity Agents
1. Make sure you're logged in as admin
2. Try creating an agent task with:
   - Task: "Check my web application for common vulnerabilities"
   - Agent Type: "vulnerability_scanner"
   - Context: "Internal security assessment"

## 📦 What's Included

### Backend Services
- ✅ LLM Service with NeuraX model family
- ✅ Speech Service (voice-ready)
- ✅ Reasoning Service (6 advanced techniques)
- ✅ Security Execution (Docker sandboxing)
- ✅ Audit Logging (tamper-evident)
- ✅ Agent Platform with 4 security-focused agents
- ✅ API Key Authentication with usage tracking
- ✅ Rate Limiting and Usage Logging

### Frontend Features
- ✅ Modern Next.js React Interface
- ✅ Authentication (email/password + Google OAuth)
- ✅ Chat Interface with Message History
- ✅ Admin Dashboard
- ✅ API Key Management
- ✅ Responsive Design

## 🔧 Development Quick Start

### Backend Only
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Only
```bash
cd web
npm install
npm run dev
```

## 🐞 Troubleshooting

### "Container failed to start"
```bash
docker-compose logs backend
```
Check for missing environment variables or port conflicts.

### "Cannot connect to database"
```bash
docker-compose exec backend pg_isready -h db -U postgres
```
Ensure the database container is healthy.

### "Frontend shows blank page"
1. Check browser console for errors (F12)
2. Verify `NEXT_PUBLIC_API_URL` in web/.env.local
3. Ensure backend is accessible from your network

### "Agents fail or timeout"
```bash
docker-compose logs backend
```
Check if security tools are installed (for real scanning) or if simulation mode is working.

## 📚 Documentation
- [Full Documentation](PROJECT_DOCUMENTATION.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## 🆘 Need Help?
Check the logs:
```bash
docker-compose logs -f
```

Visit the API documentation at http://localhost:8000/docs for interactive API testing.

---

**Ready to build powerful AI applications?** Start exploring NovaMind AI's features today!