# NovaMind AI Deployment Guide

This guide provides detailed instructions for deploying NovaMind AI to various platforms including web (Vercel), mobile app stores, and desktop distributions.

## Table of Contents
1. [Web Deployment (Vercel)](#web-deployment-vercel)
2. [Mobile App Deployment (APK/IPA)](#mobile-app-deployment-apkipa)
3. [Desktop Deployment (Windows ISO)](#desktop-deployment-windows-iso)
4. [Backend Deployment Options](#backend-deployment-options)
5. [CI/CD Pipeline Setup](#cicd-pipeline-setup)
6. [Environment Configuration](#environment-configuration)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)

---

## Web Deployment (Vercel)

NovaMind AI's frontend is a Next.js application that is ready for deployment on Vercel.

### Prerequisites
- Vercel account
- GitHub/GitLab/Bitbucket repository
- Backend API deployed and accessible

### Step-by-Step Deployment

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for Vercel deployment"
   git push origin main
   ```

2. **Import Project to Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel should automatically detect it's a Next.js project

3. **Configure Environment Variables**:
   In Vercel project settings:
   - `NEXT_PUBLIC_API_URL`: URL of your deployed backend (e.g., `https://your-backend-domain.com/api/v1`)
   - Any other frontend-specific environment variables

4. **Deploy**:
   - Vercel will automatically build and deploy your application
   - You'll get a preview URL for each pull request
   - Production deployments happen on pushes to main branch

### Vercel Configuration (vercel.json)
Create a `vercel.json` file in your web directory for advanced configuration:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "package.json",
      "use": "@vercel/static-build",
      "config": { "distDir": ".next" }
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/$1"
    }
  ],
  "env": {
    "NEXT_PUBLIC_TELEMETRY_DISABLED": "1"
  }
}
```

### Backend Considerations for Vercel
Vercel is optimized for frontend/static sites and serverless functions. For the NovaMind AI backend (FastAPI), you have several options:

#### Option 1: Deploy Backend Separately
- Deploy backend to a service that supports long-running processes (AWS, GCP, Azure, DigitalOcean, traditional VPS)
- Keep frontend on Vercel
- Set `NEXT_PUBLIC_API_URL` to point to your backend

#### Option 2: Use Vercel Serverless Functions (Limited)
- Convert FastAPI endpoints to Vercel serverless functions
- **Not recommended** for NovaMind AI due to:
  - Long-running processes (agents, LLM inference)
  - WebSocket-like needs for real-time features
  - Database connection pooling requirements
  - Complex dependencies

#### Option 3: Hybrid Approach
- Serve static frontend via Vercel
- Use Vercel for lightweight API endpoints (auth, etc.)
- Proxy heavier operations (LLM, agents) to separate backend service

---

## Mobile App Deployment (APK/IPA)

To publish NovaMind AI on Google Play Store and Apple App Store, you need to convert the web application to a mobile app.

### Approach 1: Progressive Web App (PWA) + Wrapper

The easiest approach is to enhance the PWA capabilities and use a wrapper to create native apps.

#### Step 1: Enhance PWA Features
Update `web/manifest.json` (create if doesn't exist):

```json
{
  "name": "NovaMind AI",
  "short_name": "NovaMind",
  "description": "AI Assistant with Voice, Reasoning & Cybersecurity Features",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#000000",
  "icons": [
    {
      "src": "/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

Add to `web/_document.tsx`:
```typescript
<link rel="manifest" href="/manifest.json" />
<meta name="theme-color" content="#000000" />
```

#### Step 2: Use a Wrapper Service
Choose one of these services to convert your PWA to native apps:

**Capacitor** (Recommended - by Ionic team):
```bash
# Install Capacitor
cd web
npm install @capacitor/core @capacitor/cli
npx cap init

# Add platforms
npx cap add android
npx cap add ios

# Copy web assets to native projects
npx cap copy

# Open in Android Studio/Xcode
npx cap open android   # For Android APK
npx cap open ios       # For iOS IPA
```

**Alternative: Cordova**
```bash
npm install -g cordova
cordova create novamind-mobile com.yourcompany.novamind NovaMindAI
cd novamind-mobile
cordova platform add android ios
# Copy web/www content
```

**Alternative: PWABuilder** (Microsoft)
- Use https://pwabuilder.com/
- Upload your PWA URL
- Generate Android/iOS packages

### Approach 2: React Native Rewrite
For maximum performance and native feel, consider rewriting in React Native:
- Reuse business logic and API integration
- Rewrite UI components using React Native
- Maintain same backend API

### App Store Submission Requirements

#### Google Play Store (Android)
- APK or AAB (Android App Bundle) file
- App name, description, screenshots
- Privacy policy URL
- Content rating questionnaire
- Optional: Demo video

#### Apple App Store (iOS)
- IPA file
- App name, description, keywords, screenshots
- Privacy policy URL
- Version number
- Build number
- Copyright information
- Demo video (optional but recommended)

### Native Feature Enhancements
For store submissions, consider adding:
- Push notifications (Firebase Cloud Messaging / APNs)
- Biometric authentication (Face ID / Touch ID)
- Offline capabilities with local storage
- Deep linking support
- App shortcuts / quick actions

---

## Desktop Deployment (Windows ISO)

To create a Windows distributable, you can package the application as a desktop executable.

### Option 1: Electron Wrapper

Convert the web app to a desktop application using Electron:

```bash
# Install Electron
cd web
npm install --save-dev electron

# Create main.js for Electron
cat > main.js << 'EOF'
const { app, BrowserWindow } = require('electron')
const path = require('path')

function createWindow () {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })

  // Load your Next.js app (in production mode)
  win.loadURL('http://localhost:3000')
  // For production build:
  // win.loadFile(path.join(__dirname, '../out/index.html'))
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
EOF

# Add to package.json scripts
# "electron": "electron ."

# Build executables
npm install --save-dev electron-packager
# or
npm install --save-dev electron-builder
```

Then use:
```bash
# For Windows
npx electron-packager . NovaMindAI --platform=win32 --arch=x64 --icon=assets/icon.ico

# For macOS
npx electron-packager . NovaMindAI --platform=darwin --arch=x64 --icon=assets/icon.icns

# For Linux
npx electron-packager . NovaMindAI --platform=linux --arch=x64 --icon=assets/icon.png
```

### Option 2: Progressive Web App (PWA) Installation
Modern Windows supports PWA installation:
1. Users visit your PWA URL in Edge or Chrome
2. Browser offers to "Install as App"
3. Creates desktop icon and runs in app window

### Option 3: Docker Desktop Application
Create a desktop application that runs Docker containers:
- Package Docker Desktop with your docker-compose.yml
- Provide a simple GUI to start/stop the application
- Include automatic updates

### Windows Installer Creation
Once you have an executable, create an installer:

**Using WiX Toolset** (free, professional):
```bash
# Install WiX
# Create .wxs file defining installer contents
# Compile with candle.exe and light.exe
```

**Using Inno Setup** (free, popular):
```pascal
; Example Inno Setup script
[Setup]
AppName=NovaMind AI
AppVersion=1.0
DefaultDirName={pf}\NovaMind AI
DefaultGroupName=NovaMind AI
OutputBaseFilename=NovaMindAI-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "NovaMindAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NovaMind AI"; Filename: "{app}\NovaMindAI.exe"
Name: "{commondesktop}\NovaMind AI"; Filename: "{app}\NovaMindAI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NovaMindAI.exe"; Description: "Launch NovaMind AI"; Flags: nowait postinstall skipifsilent
```

---

## Backend Deployment Options

Since Vercel is primarily for frontends, here are options for deploying the NovaMind AI backend:

### Option 1: Docker Container (Recommended)
```bash
# Build the image
docker build -t novamind-ai-backend ./backend

# Run the container
docker run -d \
  --name novamind-ai \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e REDIS_URL=redis://host:6379 \
  -e CHROMA_HOST=chroma-host \
  -e CHROMA_PORT=8000 \
  -e GOOGLE_CLIENT_ID=your-client-id \
  -e GOOGLE_CLIENT_SECRET=your-client-secret \
  -e GOOGLE_REDIRECT_URI=https://yourdomain.com/api/v1/auth/google/callback \
  novamind-ai-backend
```

### Option 2: Kubernetes Deployment
Create deployment.yaml:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: novamind-ai-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: novamind-ai-backend
  template:
    metadata:
      labels:
        app: novamind-ai-backend
    spec:
      containers:
      - name: novamind-ai-backend
        image: novamind-ai-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: novamind-secrets
              key: database-url
        # ... other env vars from secrets/configmaps
---
apiVersion: v1
kind: Service
metadata:
  name: novamind-ai-backend
spec:
  selector:
    app: novamind-ai-backend
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
  type: LoadBalancer
```

### Option 3: Traditional VPS/Cloud VM
1. Provision a VM (AWS EC2, DigitalOcean Droplet, etc.)
2. Install Docker
3. Pull/run your Docker image
4. Set up reverse proxy (NGINX) for SSL/HTTPS
5. Configure firewall and monitoring

### Option 4: Platform-as-a-Service (PaaS)
- **Heroku**: Supports Docker containers
- **Google Cloud Run**: Serverless containers
- **AWS ECS/Fargate**: Container orchestration
- **Azure Container Instances**: Managed containers
- **Render.com**: Easy Docker deployment

### Option 5: Serverless (Limited Suitability)
AWS Lambda/Azure Functions with container support:
- **Challenges**: Cold starts, execution limits, lack of persistent connections
- **Better for**: Lightweight APIs, not ideal for LLM inference or long-running agents

---

## CI/CD Pipeline Setup

### GitHub Actions Example
Create `.github/workflows/deploy.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install backend dependencies
      run: |
        cd backend
        pip install -r requirements.txt
    
    - name: Run backend tests
      run: |
        cd backend
        python -m pytest
    
    - name: Set up Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '16'
    
    - name: Install frontend dependencies
      run: |
        cd web
        npm ci
    
    - name: Run frontend tests
      run: |
        cd web
        npm test
    
    - name: Build frontend
      run: |
        cd web
        npm run build
    
    - name: Build Docker images
      run: |
        docker-compose build
    
    - name: Push Docker images to registry
      # Add your Docker registry login and push steps here
      env:
        REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
        REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
      run: |
        echo $REGISTRY_PASSWORD | docker login -u $REGISTRY_USERNAME --password-stdin
        docker push your-registry/novamind-ai-backend:latest
        docker push your-registry/novamind-ai-frontend:latest

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3
    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.1
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USERNAME }}
        key: ${{ secrets.SERVER_SSH_KEY }}
        script: |
          cd /path/to/novamind-ai
          docker-compose pull
          docker-compose up -d
          docker image prune -af
```

### GitLab CI/CD Example
Similar structure in `.gitlab-ci.yml`.

### Docker Hub Automated Builds
1. Link your GitHub repository to Docker Hub
2. Set up automated builds on pushes to specific branches
3. Use Docker Hub's build tags for versioning

---

## Environment Configuration

### Backend Environment Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Secret key for JWT signing | `your-32-character-secret-key-here` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry time | `480` (8 hours) |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/novamind` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `CHROMA_HOST` | ChromaDB host | `localhost` |
| `CHROMA_PORT` | ChromaDB port | `8000` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `your-google-client-id.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `your-google-client-secret` |
| `GOOGLE_REDIRECT_URI` | Google OAuth redirect URI | `https://yourdomain.com/api/v1/auth/google/callback` |
| `ENVIRONMENT` | Deployment environment | `development`, `staging`, `production` |
| `LOG_LEVEL` | Logging level | `INFO`, `DEBUG`, `WARNING`, `ERROR` |
| `MAX_UPLOAD_SIZE` | Max file upload size (MB) | `10` |
| `RATE_LIMIT_REQUESTS` | Requests per minute | `100` |
| `RATE_LIMIT_WINDOW` | Window in seconds | `60` |

### Frontend Environment Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `https://api.yourdomain.com/v1` |
| `NEXT_PUBLIC_APP_NAME` | Application name | `NovaMind AI` |
| `NEXT_PUBLIC_ENABLE_ANALYTICS` | Enable analytics | `true` |
| `NEXT_PUBLIC_ENABLE_SENTRY` | Enable error tracking | `false` |
| `NEXT_PUBLIC_DEFAULT_LANGUAGE` | Default language | `en` |
| `NEXT_PUBLIC_FEATURE_VOICE` | Enable voice features | `true` |
| `NEXT_PUBLIC_FEATURE_CYBERSECURITY` | Enable cybersecurity features | `true` |

### Database Schema
Run migrations to set up database:
```sql
-- The application creates tables automatically on startup
-- But you can run migrations manually if needed
```

### Initial Data
On first startup, the system:
1. Creates tables if they don't exist
2. Creates an initial admin user (email: admin@novamind.ai, password: admin123)
3. Sets up default configurations

**Important**: Change the admin password immediately after first login!

---

## Monitoring and Maintenance

### Health Checks
- Backend: `GET /` returns `{"message": "Welcome to NovaMind AI"}`
- Backend: `GET /docs` returns Swagger UI (if enabled)
- Frontend: Check if React app loads correctly

### Logging
- Backend logs to stdout (captured by Docker/logging system)
- Frontend logs to browser console
- Audit logs stored in `/app/logs/audit.log` (Docker volume)
- Consider implementing log rotation

### Metrics and Monitoring
- **Prometheus**: Export metrics from FastAPI using `prometheus-fastapi-instrumentator`
- **Grafana**: Visualize metrics
- **ELK Stack**: Log aggregation and visualization
- **Sentry**: Error tracking and performance monitoring
- **Healthchecks.io**: Cron job and uptime monitoring

### Backup Strategy
1. **Database**: Regular PostgreSQL dumps (`pg_dump`)
2. **Redis**: RDB snapshots or AOF persistence
3. **ChromaDB**: Backup the data directory
4. **Application Config**: Backup `.env` files and Docker volumes
5. **Frequency**: Daily backups with weekly/monthly retention

### Update Procedure
1. Pull latest code: `git pull origin main`
2. Update dependencies:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt --upgrade
   
   # Frontend
   cd web
   npm ci
   npm audit fix
   ```
3. Rebuild Docker images: `docker-compose build`
4. Restart services: `docker-compose up -d`
5. Run database migrations if needed (automatic on startup)
6. Monitor logs for issues

### Scaling Considerations
- **Horizontal Scaling**: Add more backend instances behind a load balancer
- **Database Scaling**: Use PostgreSQL read replicas, connection pooling (PgBouncer)
- **Cache Scaling**: Redis Cluster for distributed caching
- **Vector Store Scaling**: ChromaDB supports distributed deployments
- **CDN**: Serve static frontend assets via CDN (Cloudflare, AWS CloudFront, etc.)
- **Microservices**: Split services if needed (separate LLM service, agent service, etc.)

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Container Won't Start
- Check logs: `docker-compose logs backend`
- Verify environment variables are set
- Ensure required ports are free
- Validate Docker image builds correctly

#### 2. Database Connection Failed
- Verify `DATABASE_URL` format
- Ensure database service is running (`docker-compose ps db`)
- Check network connectivity between containers
- Validate credentials in PostgreSQL

#### 3. Redis Connection Failed
- Verify `REDIS_URL` format
- Ensure redis service is running
- Check if Redis is accessible from backend container
- Test with `docker-compose exec backend redis-cli ping`

#### 4. ChromaDB Connection Failed
- Verify `CHROMA_HOST` and `CHROMA_PORT`
- Ensure chroma service is running
- Check if ChromaDB is accessible from backend container
- Validate the data directory is writable

#### 5. Agent Tasks Fail Silently
- Check audit logs for detailed error information
- Verify security tools are installed and accessible
- Check Docker daemon is running (for DockerSecurityExecutor)
- Validate file permissions for temporary directories

#### 6. Frontend Can't Connect to Backend
- Verify `NEXT_PUBLIC_API_URL` is correct
- Check CORS settings in backend
- Verify backend is accessible from frontend's network
- Test API directly with curl/postman

#### 7. Speech Features Not Working
- Verify API keys for external services (if used)
- Check network connectivity to speech service APIs
- Validate audio permissions in browser
- Check browser console for errors

### Diagnostic Commands
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db

# Execute commands in containers
docker-compose exec backend /bin/bash
docker-compose exec web /bin/bash

# Check resource usage
docker stats

# Test network connectivity
docker-compose exec backend curl -s http://localhost:8000
docker-compose exec backend ping db
docker-compose exec backend redis-cli ping

# Check database
docker-compose exec db psql -U postgres -d postgres -c "\l"
docker-compose exec db psql -U postgres -d postgres -c "SELECT version();"

# Check Redis
docker-compose exec redis redis-cli ping
docker-compose exec redis redis-cli info

# Check ChromaDB
docker-compose exec chroma curl -s http://localhost:8000/api/v1/heartbeat
```

---

## Security Checklist for Production

Before deploying to production, verify:

### [ ] Authentication and Authorization
- [ ] Strong SECRET_KEY (32+ random characters)
- [ ] JWT expiration set appropriately (15-60 minutes for access tokens)
- [ ] Refresh token rotation implemented
- [ ] Password strength requirements enforced
- [ ] Rate limiting on authentication endpoints
- [ ] Account lockout after failed attempts
- [ ] HTTPS enforced in production

### [ ] Data Protection
- [ ] Passwords hashed with bcrypt (cost factor 12+)
- [ ] Sensitive data encrypted at rest (if applicable)
- [ ] Database connections use SSL/TLS in production
- [ ] Backups encrypted and stored securely
- [ ] Audit logs protected from tampering (hash chaining)
- [ ] GDPR-compliant data deletion implemented
- [ ] CORS policies restricted to trusted origins

### [ ] Network Security
- [ ] All services behind firewall
- [ ] Only necessary ports exposed (typically 80/443 for frontend, 8000 for backend API)
- [ ] Internal service communication restricted to trusted networks
- [ ] Docker containers run as non-root users
- [ ] Read-only root filesystem for security containers
- [ ] Network disabled for security tool execution containers
- [ ] Resource limits (CPU, memory) enforced on containers

### [ ] Application Security
- [ ] Input validation and sanitization on all endpoints
- [ ] SQL injection prevention via ORM/parameterized queries
- [ ] XSS protection via proper escaping and CSP headers
- [ ] CSRF protection where applicable (though JWT reduces CSRF risk)
- [ ] Secure headers implemented (HSTS, CSP, X-Frame-Options, etc.)
- [ ] File upload validation (type, size, content)
- [ ] Path traversal prevention
- [ ] Dependency scanning in CI/CD (npm audit, safety, bandit)
- [ ] Regular dependency updates

### [ ] Monitoring and Logging
- [ ] Centralized logging aggregation configured
- [ ] Error tracking system (Sentry, etc.) configured
- [ ] Performance monitoring in place
- [ ] Security event alerting configured
- [ ] Audit logs monitored for suspicious activity
- [ ] Regular security reviews and penetration testing scheduled
- [ ] Incident response plan documented and tested

### [ ] Compliance and Legal
- [ ] Privacy policy published and accessible
- [ ] Terms of service published
- [ ] Data processing agreements in place if needed
- [ ] Copyright and licensing compliance verified
- [ ] Export control considerations addressed (if applicable)
- [ ] Industry-specific regulations checked (HIPAA, PCI-DSS, etc.)

---

## Conclusion

NovaMind AI is designed to be deployable across multiple platforms with flexibility in how you choose to host each component. The key to successful deployment is:

1. **Start Simple**: Begin with Docker Compose for local/testing environments
2. **Scale Gradually**: Move to orchestration platforms (Kubernetes) as needed
3. **Separate Concerns**: Consider different hosting strategies for frontend vs backend
4. **Automate Everything**: Use CI/CD pipelines for reliable, repeatable deployments
5. **Monitor Relentlessly**: Implement comprehensive monitoring and alerting
6. **Secure Continuously**: Treat security as an ongoing process, not a one-time setup

Whether you're deploying to a single server for personal use or building a globally scalable SaaS platform, NovaMind AI provides the foundation you need to create powerful AI applications with enterprise-grade security and compliance features.

For additional help, consult the source code comments, inline documentation, and the project's issue tracker or community forums.