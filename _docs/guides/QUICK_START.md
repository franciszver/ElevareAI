# Quick Start Guide

Get the AI Study Companion platform up and running in minutes.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Docker)
- OpenRouter API key (sk-or-v1-... format)
- AWS Cognito (for authentication)

## 1. Clone & Setup

```bash
git clone <repository-url>
cd PennyGadget
pip install -r requirements.txt
```

## 2. Configure Environment

Create `.env` file:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/ai_study_companion
OPENROUTER_API_KEY=sk-or-v1-your-key-here
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=your-pool-id
COGNITO_CLIENT_ID=your-client-id
```

## 3. Start Database (Docker)

```bash
docker-compose up -d postgres
```

## 4. Initialize Database

```bash
# Create tables (using SQLAlchemy)
python -c "from src.config.database import engine, Base; from src.models import *; Base.metadata.create_all(engine)"

# Or use Alembic migrations
alembic upgrade head
```

## 5. Seed Demo Data (Optional)

```bash
python scripts/create_demo_data.py
```

## 6. Start API Server

**Option 1: Using Python module (Recommended)**
```bash
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Option 2: Using the run script**
```bash
python run_server.py
```

**Option 3: Using PowerShell script (Windows)**
```powershell
.\START_SERVER.ps1
```

**Option 4: Using bash script (Linux/Mac)**
```bash
chmod +x START_SERVER.sh
./START_SERVER.sh
```

## 7. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

## Quick Test

```bash
# Test Q&A endpoint
curl -X POST http://localhost:8000/api/v1/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "test-student-id",
    "query": "What is algebra?",
    "context": {}
  }'
```

## Docker Quick Start

```bash
# Start everything
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

## Next Steps

1. **Explore API**: Visit http://localhost:8000/docs
2. **Run Tests**: `pytest tests/ -v`
3. **Read Docs**: Check `docs/` directory
4. **Try Demo**: See `DEMO_GUIDE.md`

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql $DATABASE_URL
```

### Import Errors
```bash
# Ensure you're in the project root
pwd

# Install dependencies
pip install -r requirements.txt
```

### Port Already in Use
```bash
# Use different port
uvicorn src.api.main:app --port 8001
```

## Production Deployment

See `_docs/guides/AWS_DEPLOYMENT_CHECKLIST.md` for AWS deployment guide.

---

**Need Help?** Check the documentation in `docs/` or see `PROJECT_STATUS.md` for feature overview.

