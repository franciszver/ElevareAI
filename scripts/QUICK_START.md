# Quick Start Guide

## Before You Begin

1. **Install AWS CLI** and configure a profile:
   ```powershell
   aws configure --profile your-actual-profile-name
   ```
   Replace `your-actual-profile-name` with your real AWS profile name.

2. **Verify your profile works:**
   ```powershell
   aws sts get-caller-identity --profile your-actual-profile-name
   ```

## Step 1: Run AWS Infrastructure Setup

**Important:** Replace `your-actual-profile-name` with your real AWS profile name!

```powershell
.\scripts\setup_aws_infrastructure.ps1 -Profile your-actual-profile-name -Region us-east-1 -Environment development
```

**What this does:**
- Creates RDS PostgreSQL database (takes 5-10 minutes)
- Creates Cognito User Pool
- Configures SES
- Creates S3 bucket
- Generates `.aws-config-development.env` with credentials

**⚠️ Save the database password that gets generated!**

## Step 2: Configure Environment

1. Copy the generated config:
   ```powershell
   Copy-Item .aws-config-development.env .env
   ```

2. Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
   ```

## Step 3: Set Up Database

```powershell
# Install dependencies
pip install -r requirements.txt

# Run migrations
python scripts/setup_db.py --env-file .env
```

## Step 4: (Optional) Seed Demo Data

```powershell
python scripts/seed_demo_data.py
```

## Troubleshooting

### "The config profile (your-profile-name) could not be found"

**Solution:** You used the placeholder `your-profile-name`. Use your actual AWS profile name:
```powershell
# List your profiles
aws configure list-profiles

# Use one of those names
.\scripts\setup_aws_infrastructure.ps1 -Profile default -Region us-east-1
```

### AWS CLI Command Errors

If you see errors like "argument --user-pool-id: expected one argument", the script has been fixed. Try running it again.

### Database Connection Issues

1. Wait 5-10 minutes after RDS creation completes
2. Check your security groups allow connections from your IP
3. Verify credentials in `.env` file

## Next Steps

After setup:
1. Test database connection
2. Review `_docs/active/IMPLEMENTATION_PRIORITY.md` for development roadmap
3. Start building features!

