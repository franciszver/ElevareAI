# Deployment Guide - AI Study Companion API

## Overview

This guide covers deploying the AI Study Companion API using Docker and Docker Compose.

---

## 📋 **Prerequisites**

- Docker (version 20.10+)
- Docker Compose (version 2.0+)
- Environment variables configured

---

## 🚀 **Quick Start**

### **1. Clone Repository**

```bash
git clone <repository-url>
cd PennyGadget
```

### **2. Configure Environment**

Create `.env` file or `.env.production`:

```env
# Database
DB_NAME=pennygadget
DB_USER=postgres
DB_PASSWORD=your-secure-password
DB_PORT=5432

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Cognito
COGNITO_USER_POOL_ID=your-pool-id
COGNITO_CLIENT_ID=your-client-id
COGNITO_REGION=us-east-1

# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key
OPENROUTER_MODEL=openai/gpt-oss-20b:free

# API
API_KEY=your-api-key
```

### **3. Deploy**

**Linux/Mac:**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh production
```

**Windows:**
```powershell
.\scripts\deploy.ps1 production
```

**Or manually:**
```bash
docker-compose up -d
```

---

## 🐳 **Docker Setup**

### **Build Image**

```bash
docker-compose build
```

### **Start Services**

```bash
docker-compose up -d
```

### **View Logs**

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Database only
docker-compose logs -f postgres
```

### **Stop Services**

```bash
docker-compose down
```

### **Stop and Remove Volumes**

```bash
docker-compose down -v
```

---

## 🔧 **Configuration**

### **Environment Variables**

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_NAME` | PostgreSQL database name | `pennygadget` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `postgres` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `API_KEY` | Service-to-service API key | Optional |

### **Port Configuration**

- **API**: `8000` (configurable via `API_PORT`)
- **PostgreSQL**: `5432` (configurable via `DB_PORT`)

---

## 📊 **Health Checks**

### **API Health Check**

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### **Database Health Check**

```bash
docker-compose exec postgres pg_isready -U postgres
```

---

## 🗄️ **Database Management**

### **Run Migrations**

If using Alembic:

```bash
docker-compose run --rm api alembic upgrade head
```

### **Access Database**

```bash
docker-compose exec postgres psql -U postgres -d pennygadget
```

### **Backup Database**

```bash
docker-compose exec postgres pg_dump -U postgres pennygadget > backup.sql
```

### **Restore Database**

```bash
docker-compose exec -T postgres psql -U postgres pennygadget < backup.sql
```

---

## 🔍 **Troubleshooting**

### **Services Won't Start**

1. Check logs:
   ```bash
   docker-compose logs
   ```

2. Verify environment variables:
   ```bash
   docker-compose config
   ```

3. Check port availability:
   ```bash
   # Linux/Mac
   lsof -i :8000
   
   # Windows
   netstat -ano | findstr :8000
   ```

### **Database Connection Issues**

1. Verify database is healthy:
   ```bash
   docker-compose ps postgres
   ```

2. Check database logs:
   ```bash
   docker-compose logs postgres
   ```

3. Test connection:
   ```bash
   docker-compose exec api python -c "from src.config.database import check_database_connection; print(check_database_connection())"
   ```

### **API Not Responding**

1. Check API logs:
   ```bash
   docker-compose logs api
   ```

2. Verify API is running:
   ```bash
   docker-compose ps api
   ```

3. Test health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

---

## 🚀 **Production Deployment**

### **AWS ECS/Fargate**

1. Build and push image to ECR:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   docker tag ai-study-companion-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-study-companion-api:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-study-companion-api:latest
   ```

2. Create ECS task definition with:
   - Environment variables from AWS Secrets Manager
   - RDS PostgreSQL connection
   - Health checks configured

### **Kubernetes**

1. Create deployment:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: ai-study-companion-api
   spec:
     replicas: 3
     template:
       spec:
         containers:
         - name: api
           image: ai-study-companion-api:latest
           env:
           - name: DB_HOST
             valueFrom:
               secretKeyRef:
                 name: db-secret
                 key: host
   ```

2. Create service:
   ```yaml
   apiVersion: v1
   kind: Service
   metadata:
     name: ai-study-companion-api
   spec:
     type: LoadBalancer
     ports:
     - port: 80
       targetPort: 8000
     selector:
       app: ai-study-companion-api
   ```

### **Docker Swarm**

```bash
docker stack deploy -c docker-compose.yml ai-study-companion
```

---

## 🔒 **Security Best Practices**

1. **Use Secrets Management**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Kubernetes Secrets

2. **Network Security**
   - Use internal networks for database
   - Expose only necessary ports
   - Use reverse proxy (nginx/traefik)

3. **Image Security**
   - Scan images for vulnerabilities
   - Use minimal base images
   - Keep dependencies updated

4. **Database Security**
   - Use strong passwords
   - Enable SSL connections
   - Restrict network access

---

## 📈 **Monitoring**

### **View Metrics**

```bash
curl http://localhost:8000/metrics
```

### **Log Aggregation**

Configure log drivers in `docker-compose.yml`:

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 🔄 **Updates and Rollbacks**

### **Update Application**

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build api
```

### **Rollback**

```bash
# Use previous image tag
docker-compose up -d api --image ai-study-companion-api:previous-tag
```

---

## 📚 **Additional Resources**

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

**Last Updated**: November 2024

