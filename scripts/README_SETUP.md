# Setup Instructions

## Prerequisites

1. **AWS CLI installed and configured**
   ```powershell
   aws --version
   aws configure --profile your-profile-name
   ```

2. **Python 3.11+ installed**
   ```powershell
   python --version
   ```

3. **PostgreSQL client tools** (optional, for direct DB access)

## Quick Start

### Step 1: Set Up AWS Infrastructure

**PowerShell (Windows):**
```powershell
.\scripts\setup_aws_infrastructure.ps1 -Profile your-profile-name -Region us-east-1 -Environment development
```

**Bash (Git Bash/WSL/Linux/Mac):**
```bash
bash scripts/setup_aws_infrastructure.sh --profile your-profile-name --region us-east-1 --environment development
```

This script will:
- Create RDS PostgreSQL database (takes 5-10 minutes)
- Create Cognito User Pool with user groups
- Configure SES for email
- Create S3 bucket for transcripts
- Generate `.aws-config-development.env` with all credentials

**⚠️ Important:** The script will output a database password. Save it securely!

### Step 2: Configure Environment Variables

Copy values from `.aws-config-development.env` to your `.env` file:

```powershell
# Copy the generated config
Copy-Item .aws-config-development.env .env

# Edit .env and add:
# - OPENROUTER_API_KEY=sk-or-v1-your-key-here
# - Any other missing values
```

### Step 3: Set Up Database Schema

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
python scripts/setup_db.py --env-file .env
```

This will:
- Create all database tables
- Set up indexes
- Create views and functions
- Set up triggers

### Step 4: Seed Demo Data (Optional)

```powershell
python scripts/seed_demo_data.py
```

This generates realistic test data for development.

## Verification

### Check Database Connection

```powershell
# Using psql (if installed)
psql -h $env:DB_HOST -U $env:DB_USER -d $env:DB_NAME

# Or test with Python
python -c "from src.config.database import check_database_connection; print('✅ Connected' if check_database_connection() else '❌ Failed')"
```

### Verify AWS Resources

```powershell
# Check RDS
aws rds describe-db-instances --db-instance-identifier pennygadget-db-development --profile your-profile-name

# Check Cognito
aws cognito-idp list-user-pools --max-results 60 --profile your-profile-name

# Check S3
aws s3 ls --profile your-profile-name
```

## Troubleshooting

### Database Connection Issues

1. **Check security groups:** RDS instance must allow connections from your IP
2. **Verify credentials:** Check `.env` file has correct DB_HOST, DB_USER, DB_PASSWORD
3. **Test connection:** Use `psql` or Python connection test

### AWS CLI Issues

1. **Profile not found:** Run `aws configure --profile your-profile-name`
2. **Permissions:** Ensure your AWS user has permissions for RDS, Cognito, SES, S3
3. **Region mismatch:** Ensure all resources are in the same region

### Migration Issues

1. **Database doesn't exist:** The setup script should create it, but you can create manually:
   ```sql
   CREATE DATABASE pennygadget;
   ```

2. **Extension errors:** Ensure PostgreSQL has `uuid-ossp` extension available

## Next Steps

After setup is complete:

1. **Start development server:**
   ```powershell
   uvicorn src.api.main:app --reload
   ```

2. **Run tests:**
   ```powershell
   pytest tests/
   ```

3. **Review documentation:**
   - `_docs/active/IMPLEMENTATION_PRIORITY.md` - Development roadmap
   - `_docs/active/API_CONTRACTS.md` - API specifications

## Security Notes

⚠️ **Important Security Considerations:**

1. **Database Password:** The generated password is in `.aws-config-development.env` - keep this file secure!
2. **RDS Public Access:** The script creates a publicly accessible RDS instance for development. In production:
   - Use private subnets
   - Configure security groups properly
   - Use VPC endpoints
3. **Environment Variables:** Never commit `.env` or `.aws-config-*.env` files to git
4. **API Keys:** Keep OpenAI API key and other secrets secure

## Production Setup

For production, you'll want to:

1. Use private subnets for RDS
2. Enable Multi-AZ for RDS
3. Set up proper IAM roles (not access keys)
4. Use Secrets Manager for credentials
5. Enable CloudWatch logging
6. Set up proper backup schedules
7. Configure VPC security groups

See `_docs/active/IMPLEMENTATION_PRIORITY.md` for more details.

