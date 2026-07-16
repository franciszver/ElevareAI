# AWS Production Deployment Guide

Complete guide for deploying ElevareAI to AWS using the provided PowerShell scripts.

## 📋 Overview

This guide walks you through deploying ElevareAI to AWS using a step-by-step PowerShell script approach. The deployment creates:

- **RDS PostgreSQL** database
- **ECS Fargate** service for the backend API
- **Application Load Balancer** for routing
- **S3 + CloudFront** for frontend hosting
- **Security Groups** and **IAM Roles** for access control

## ✅ Prerequisites

Before starting, ensure you have:

- ✅ AWS CLI installed and configured (`aws configure`)
- ✅ Docker installed (for building images)
- ✅ Python 3.8+ installed
- ✅ PowerShell 5.1+ (Windows) or PowerShell Core (cross-platform)
- ✅ AWS Account with appropriate permissions
- ✅ Cognito User Pool ID (get from AWS Console)
- ✅ Cognito Client ID (get from AWS Console)

## 🚀 Quick Start

### Step 1: Initial Setup (Steps 1-5)

Run the first deployment script:

```powershell
.\scripts\deployment\deploy-aws.ps1
```

This script will:
1. Get your AWS Account ID
2. Find default VPC and subnets
3. Create security groups for RDS and ECS
4. Create RDS PostgreSQL database
5. Save all variables to `aws-deployment-vars.json`

**⏱️ Wait 5-10 minutes** for RDS database to become available.

### Step 2: Infrastructure Setup (Steps 6-12)

After RDS is ready, run:

```powershell
.\scripts\deployment\deploy-aws-step2.ps1
```

This script will:
6. Update security groups (allow ECS → RDS)
7. Create ECR repository
8. Build and push Docker image
9. Create IAM role for ECS tasks
10. Create ECS cluster
12. Create CloudWatch log group

### Step 3: Deploy Backend Service (Steps 11, 13-16)

Run:

```powershell
.\scripts\deployment\deploy-aws-step3.ps1
```

This script will:
11. Create ECS task definition
13. Create Application Load Balancer
14. Create target group
15. Create ALB listener
16. Create ECS service

**⏱️ Wait 2-3 minutes** for ECS service to start.

### Step 4: Database Setup & Demo Users (Steps 17-19)

Run:

```powershell
.\scripts\deployment\deploy-aws-step4.ps1
```

This script will:
17. Test backend API health endpoint
18. Run database migrations
19. Create demo users and verify

### Step 5: Deploy Frontend (Steps 20-23)

Run:

```powershell
.\scripts\deployment\deploy-aws-step5.ps1
```

This script will:
20. Create S3 bucket for frontend
21. Build and upload frontend
22. Create CloudFront distribution
23. Display deployment summary

**⏱️ Wait 10-15 minutes** for CloudFront to deploy.

## 📝 Detailed Steps

### Environment Variables Required

The scripts automatically set these from `aws-deployment-vars.json`, but you can also set them manually:

```powershell
$env:DB_HOST = "your-rds-endpoint.amazonaws.com"
$env:DB_PORT = "5432"
$env:DB_NAME = "elevareai"
$env:DB_USER = "elevareai_admin"
$env:DB_PASSWORD = "your-password"
```

### Manual Migration (Alternative)

If the automated migration fails, you can run migrations manually:

```powershell
python scripts/run_migrations_aws.py `
    --host $DB_ENDPOINT `
    --database elevareai `
    --user elevareai_admin `
    --password $DB_PASSWORD
```

Or using psql:

```powershell
psql -h $DB_ENDPOINT -U elevareai_admin -d elevareai -f migrations/001_initial_schema.sql
```

### Adding OpenRouter API Key

After deployment, add your OpenRouter API key to the ECS task definition:

1. Go to AWS Console → ECS → Task Definitions → `elevareai-api`
2. Create new revision
3. Add environment variable: `OPENROUTER_API_KEY` = `sk-or-v1-your-key-here`
4. Update ECS service to use new revision:

```powershell
aws ecs update-service `
    --cluster elevareai-cluster `
    --service elevareai-api `
    --task-definition elevareai-api:NEW_REVISION `
    --region us-east-1
```

## 🔍 Verification

### Check Backend Health

```powershell
$ALB_DNS = (Get-Content aws-deployment-vars.json | ConvertFrom-Json).ALB_DNS
Invoke-WebRequest -Uri "http://$ALB_DNS/health"
```

### Check ECS Service Status

```powershell
aws ecs describe-services `
    --cluster elevareai-cluster `
    --services elevareai-api `
    --query 'services[0].[status,runningCount,desiredCount]' `
    --output table `
    --region us-east-1
```

### Check RDS Status

```powershell
aws rds describe-db-instances `
    --db-instance-identifier elevareai-db `
    --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]' `
    --output table `
    --region us-east-1
```

### View Logs

```powershell
aws logs tail /ecs/elevareai-api --follow --region us-east-1
```

## 🎯 Demo Users

After running step 4, the following demo accounts are created:

1. **demo_goal_complete@demo.com** - Goal completion scenario
2. **demo_sat_complete@demo.com** - SAT completion → College prep
3. **demo_chemistry@demo.com** - Chemistry → STEM pathway
4. **demo_struggling@demo.com** - Struggling student scenario
5. **demo_advanced@demo.com** - Advanced student scenario
6. **demo_tutor@demo.com** - Tutor account

See `_docs/Demo_Accounts.md` for detailed credentials and scenarios.

## 🔧 Troubleshooting

### ECS Service Not Starting

Check task logs:
```powershell
aws logs tail /ecs/elevareai-api --follow --region us-east-1
```

Check service events:
```powershell
aws ecs describe-services `
    --cluster elevareai-cluster `
    --services elevareai-api `
    --query 'services[0].events[0:5]' `
    --output table
```

### Database Connection Issues

Verify security group rules:
```powershell
aws ec2 describe-security-groups `
    --group-ids $RDS_SG_ID `
    --query 'SecurityGroups[0].IpPermissions' `
    --output json
```

### Frontend Not Loading

Check CloudFront status:
```powershell
aws cloudfront get-distribution `
    --id $CF_DIST_ID `
    --query 'Distribution.Status' `
    --output text
```

Check S3 bucket policy:
```powershell
aws s3api get-bucket-policy --bucket $BUCKET_NAME
```

## 📊 Cost Estimation

Approximate monthly costs (us-east-1):

- **RDS db.t3.micro**: ~$15/month
- **ECS Fargate** (0.25 vCPU, 0.5GB): ~$7/month
- **ALB**: ~$16/month
- **S3**: ~$0.50/month (for small static site)
- **CloudFront**: ~$1/month (first 10GB free)
- **Data Transfer**: Variable

**Total**: ~$40-50/month (excluding data transfer)

## 🔐 Security Notes

1. **Database Password**: Generated in step 1, saved in `aws-deployment-vars.json`. Keep this secure!
2. **RDS Access**: Currently allows ECS security group. Consider restricting further in production.
3. **HTTPS**: Currently using HTTP. Add ACM certificate and HTTPS listener for production.
4. **OpenAI API Key**: Add via ECS task definition environment variables (not in code).

## 📚 Additional Resources

- [AWS Deployment Plan](./demo-data-and-requirements-implementation.plan.md) - Detailed step-by-step plan
- [AWS Deployment Checklist](_docs/guides/AWS_DEPLOYMENT_CHECKLIST.md) - Pre-deployment checklist
- [Demo User Guide](_docs/DEMO_USER_GUIDE.md) - Demo account details
- [Troubleshooting Guide](_docs/guides/TROUBLESHOOTING_DOCKER.md) - Common issues

## 🎉 Next Steps

After deployment:

1. ✅ Add OpenAI API key to ECS task definition
2. ✅ Wait for CloudFront to deploy (10-15 minutes)
3. ✅ Test frontend at CloudFront URL
4. ✅ Test backend at ALB DNS name
5. ✅ Test demo user logins
6. ✅ (Optional) Set up Route 53 and ACM for custom domain
7. ✅ (Optional) Set up monitoring and alerts

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Check ECS service events
4. Verify security group rules
5. Ensure all environment variables are set correctly

---

**Last Updated**: Based on deployment scripts version 1.0

