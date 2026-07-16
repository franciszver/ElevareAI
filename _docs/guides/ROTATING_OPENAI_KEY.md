# Rotating OpenAI API Key in AWS ECS Deployment

## Overview

This guide explains how to update the OpenAI API key for the deployed application running on AWS ECS (Elastic Container Service). The OpenAI API key is stored as an environment variable in the ECS Task Definition.

---

## 🔐 Security Note

**Important:** Never commit API keys to version control. The OpenAI API key should only be:
- Set as an environment variable locally
- Stored in the ECS Task Definition (encrypted at rest)
- Optionally stored in AWS Secrets Manager (recommended for production)

---

## 📍 Where is the Key Stored?

The `OPENROUTER_API_KEY` is stored in:
- **AWS Service:** ECS (Elastic Container Service)
- **Location:** Task Definition environment variables
- **Task Definition Family:** `elevareai-api` (or your project name)
- **Container:** Main API container

---

## 🔄 Methods to Update the Key

### Method 1: AWS Console (Recommended for Beginners)

**Time required:** 5-10 minutes

1. **Get your new OpenAI API key:**
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Copy the key (starts with `sk-proj-` or `sk-`)

2. **Navigate to ECS Task Definitions:**
   - Open AWS Console
   - Go to: **ECS** → **Task Definitions**
   - Find your task definition (e.g., `elevareai-api`)
   - Click on the latest revision

3. **Create a new revision:**
   - Click **"Create new revision"** button
   - Scroll to **Container Definitions**
   - Click on your container name

4. **Update the environment variable:**
   - Scroll to **Environment variables**
   - Find `OPENROUTER_API_KEY`
   - Update the value with your new key
   - Click **Update** (at bottom of container settings)
   - Click **Create** (to create the new task definition revision)

5. **Update the ECS Service:**
   - Go to: **ECS** → **Clusters** → your cluster
   - Click on **Services** tab
   - Select your service
   - Click **Update**
   - Under **Task definition**, select the new revision you just created
   - Check **Force new deployment**
   - Click **Update**

6. **Wait for deployment:**
   - The deployment takes 2-3 minutes
   - Watch the **Deployments** tab until status shows **Completed**
   - Old tasks will be replaced by new ones with the updated key

---

### Method 2: AWS CLI (Faster, Requires Setup)

**Prerequisites:**
- AWS CLI installed and configured
- AWS credentials with ECS permissions
- PowerShell (Windows) or Bash (Linux/Mac)

#### PowerShell (Windows):

```powershell
# 1. Set your new OpenAI API key
$env:OPENROUTER_API_KEY = "sk-your-new-key-here"

# 2. Set your AWS profile (if using profiles)
$env:AWS_PROFILE = "your-profile-name"

# 3. Load deployment variables
$vars = Get-Content "aws-deployment-vars.json" | ConvertFrom-Json
$PROJECT_NAME = $vars.PROJECT_NAME
$REGION = $vars.REGION
$DB_ENDPOINT = $vars.DB_ENDPOINT
$DB_PASSWORD = $vars.DB_PASSWORD
$COGNITO_USER_POOL_ID = $vars.COGNITO_USER_POOL_ID
$COGNITO_CLIENT_ID = $vars.COGNITO_CLIENT_ID
$ECS_TASK_ROLE_ARN = $vars.ECS_TASK_ROLE_ARN
$ECR_REPO_URI = $vars.ECR_REPO_URI

# 4. Create new task definition with updated key
$TASK_DEF_JSON = @{
    family = "$PROJECT_NAME-api"
    networkMode = "awsvpc"
    requiresCompatibilities = @("FARGATE")
    cpu = "256"
    memory = "512"
    executionRoleArn = $ECS_TASK_ROLE_ARN
    taskRoleArn = $ECS_TASK_ROLE_ARN
    containerDefinitions = @(@{
        name = "$PROJECT_NAME-api"
        image = "$ECR_REPO_URI:latest"
        essential = $true
        portMappings = @(@{
            containerPort = 8000
            protocol = "tcp"
        })
        environment = @(
            @{ name = "DB_HOST"; value = $DB_ENDPOINT },
            @{ name = "DB_PORT"; value = "5432" },
            @{ name = "DB_NAME"; value = "elevareai" },
            @{ name = "DB_USER"; value = "elevareai_admin" },
            @{ name = "DB_PASSWORD"; value = $DB_PASSWORD },
            @{ name = "COGNITO_USER_POOL_ID"; value = $COGNITO_USER_POOL_ID },
            @{ name = "COGNITO_CLIENT_ID"; value = $COGNITO_CLIENT_ID },
            @{ name = "COGNITO_REGION"; value = $REGION },
            @{ name = "OPENROUTER_API_KEY"; value = $env:OPENROUTER_API_KEY },
            @{ name = "ENVIRONMENT"; value = "production" },
            @{ name = "LOG_LEVEL"; value = "INFO" }
        )
        logConfiguration = @{
            logDriver = "awslogs"
            options = @{
                "awslogs-group" = "/ecs/$PROJECT_NAME-api"
                "awslogs-region" = $REGION
                "awslogs-stream-prefix" = "ecs"
            }
        }
        healthCheck = @{
            command = @("CMD-SHELL", "curl -f http://localhost:8000/health || exit 1")
            interval = 30
            timeout = 5
            retries = 3
            startPeriod = 60
        }
    })
} | ConvertTo-Json -Depth 10

# 5. Save to file
[System.IO.File]::WriteAllText("$PWD\task-definition.json", $TASK_DEF_JSON, [System.Text.UTF8Encoding]::new($false))

# 6. Register new task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json --region $REGION

# 7. Get new revision number
$NEW_REVISION = aws ecs describe-task-definition `
    --task-definition "$PROJECT_NAME-api" `
    --region $REGION `
    --query 'taskDefinition.revision' `
    --output text

Write-Host "New revision: $NEW_REVISION" -ForegroundColor Green

# 8. Update service
aws ecs update-service `
    --cluster "$PROJECT_NAME-cluster" `
    --service "$PROJECT_NAME-api" `
    --task-definition "$PROJECT_NAME-api:$NEW_REVISION" `
    --region $REGION `
    --force-new-deployment

Write-Host "Service update initiated!" -ForegroundColor Green

# 9. Cleanup
Remove-Item "task-definition.json" -ErrorAction SilentlyContinue
```

#### Bash (Linux/Mac):

```bash
# 1. Set your new OpenAI API key
export OPENROUTER_API_KEY="sk-your-new-key-here"

# 2. Set AWS profile (if using profiles)
export AWS_PROFILE="your-profile-name"

# 3. Load deployment variables
PROJECT_NAME=$(jq -r '.PROJECT_NAME' aws-deployment-vars.json)
REGION=$(jq -r '.REGION' aws-deployment-vars.json)

# 4. Get current task definition
aws ecs describe-task-definition \
    --task-definition "$PROJECT_NAME-api" \
    --region $REGION \
    --query 'taskDefinition' > task-def-current.json

# 5. Update OPENROUTER_API_KEY in the JSON
# (Use jq or manually edit task-def-current.json to update the OPENROUTER_API_KEY value)

# 6. Register new task definition
aws ecs register-task-definition \
    --cli-input-json file://task-def-current.json \
    --region $REGION

# 7. Get new revision
NEW_REVISION=$(aws ecs describe-task-definition \
    --task-definition "$PROJECT_NAME-api" \
    --region $REGION \
    --query 'taskDefinition.revision' \
    --output text)

echo "New revision: $NEW_REVISION"

# 8. Update service
aws ecs update-service \
    --cluster "$PROJECT_NAME-cluster" \
    --service "$PROJECT_NAME-api" \
    --task-definition "$PROJECT_NAME-api:$NEW_REVISION" \
    --region $REGION \
    --force-new-deployment

echo "Service update initiated!"

# 9. Cleanup
rm task-def-current.json
```

---

### Method 3: Using Deployment Script

If you're using the deployment scripts:

```powershell
# 1. Set your new OpenAI API key
$env:OPENROUTER_API_KEY = "sk-your-new-key-here"

# 2. Set AWS profile
$env:AWS_PROFILE = "your-profile-name"

# 3. Run the deployment script step 3
.\scripts\deployment\deploy-aws-step3.ps1
```

**Note:** This will recreate the task definition and attempt to update the service.

---

## ✅ Verification Steps

### 1. Check Task Definition

Verify the new revision was created:

```powershell
# PowerShell
aws ecs describe-task-definition `
    --task-definition "elevareai-api" `
    --region us-east-1 `
    --query 'taskDefinition.revision' `
    --output text
```

```bash
# Bash
aws ecs describe-task-definition \
    --task-definition "elevareai-api" \
    --region us-east-1 \
    --query 'taskDefinition.revision' \
    --output text
```

### 2. Check Service Status

Monitor the deployment:

```powershell
# PowerShell
aws ecs describe-services `
    --cluster "elevareai-cluster" `
    --services "elevareai-api" `
    --region us-east-1 `
    --query 'services[0].[status,runningCount,desiredCount,deployments[0].rolloutState]' `
    --output table
```

```bash
# Bash
aws ecs describe-services \
    --cluster "elevareai-cluster" \
    --services "elevareai-api" \
    --region us-east-1 \
    --query 'services[0].[status,runningCount,desiredCount,deployments[0].rolloutState]' \
    --output table
```

Wait until `rolloutState` shows `COMPLETED`.

### 3. Check Running Tasks

Verify the new task is using the new revision:

```powershell
# PowerShell
$taskArn = aws ecs list-tasks `
    --cluster "elevareai-cluster" `
    --service-name "elevareai-api" `
    --region us-east-1 `
    --query 'taskArns[0]' `
    --output text

aws ecs describe-tasks `
    --cluster "elevareai-cluster" `
    --tasks $taskArn `
    --region us-east-1 `
    --query 'tasks[0].[taskDefinitionArn,lastStatus,healthStatus]' `
    --output table
```

### 4. Check Application Logs

View recent logs to ensure no OpenAI errors:

```powershell
# PowerShell
aws logs tail /ecs/elevareai-api --since 5m --region us-east-1 --follow
```

```bash
# Bash
aws logs tail /ecs/elevareai-api --since 5m --region us-east-1 --follow
```

Look for:
- ✅ No `401 Unauthorized` errors from OpenAI
- ✅ Successful API calls to OpenAI
- ✅ Healthy status checks

### 5. Test the Application

Make a test API call to an endpoint that uses OpenAI (e.g., Q&A endpoint):

```bash
curl -X POST https://your-alb-dns.amazonaws.com/api/v1/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "test-user-id",
    "query": "What is 2+2?",
    "context": {}
  }'
```

Expected: Successful response (not 401 or 500 error).

---

## 🔒 Security Best Practices

### 1. Revoke Old Keys

After confirming the new key works:
1. Go to https://platform.openai.com/api-keys
2. Find the old API key
3. Click **Revoke** or **Delete**
4. Confirm the action

This prevents unauthorized use of the old key.

### 2. Key Rotation Schedule

Recommended rotation frequency:
- **Regular rotation:** Every 90 days
- **Suspected compromise:** Immediately
- **Team member departure:** Immediately
- **Compliance requirement:** As specified

### 3. Use AWS Secrets Manager (Advanced)

For enhanced security, store the key in AWS Secrets Manager:

```powershell
# Store key in Secrets Manager
aws secretsmanager create-secret `
    --name "/elevareai/openai-api-key" `
    --secret-string "sk-your-key-here" `
    --region us-east-1

# Update task definition to reference the secret
# (Requires task execution role with secretsmanager:GetSecretValue permission)
```

### 4. Audit Access

Regularly review who has access to:
- AWS ECS console
- AWS CLI credentials
- OpenAI dashboard

---

## 🔧 Troubleshooting

### Issue: "Error parsing parameter 'cli-input-json': Invalid JSON"

**Solution:**
- Ensure JSON file has valid UTF-8 encoding without BOM
- Check for special characters in environment variable values
- Use `[System.IO.File]::WriteAllText()` with UTF-8 encoding in PowerShell

### Issue: Deployment stuck in "IN_PROGRESS"

**Possible causes:**
1. New task failing health checks
2. Container image issues
3. Resource constraints

**Solution:**
```powershell
# Check task status
aws ecs describe-tasks --cluster elevareai-cluster --tasks <task-arn> --region us-east-1

# Check logs
aws logs tail /ecs/elevareai-api --since 10m --region us-east-1
```

### Issue: Still getting 401 errors after update

**Possible causes:**
1. Old task still running (deployment not complete)
2. Key was copied incorrectly (extra spaces, truncated)
3. Key not activated yet on OpenAI side

**Solution:**
1. Wait for deployment to complete (check rolloutState)
2. Verify the key in task definition matches OpenAI dashboard
3. Test the key directly with OpenAI API

### Issue: Service won't update to new revision

**Solution:**
```powershell
# Force stop current tasks
aws ecs update-service `
    --cluster elevareai-cluster `
    --service elevareai-api `
    --force-new-deployment `
    --region us-east-1
```

---

## 📋 Checklist

Use this checklist when rotating the OpenAI API key:

- [ ] Create new OpenAI API key
- [ ] Copy the full key (verify it starts with `sk-`)
- [ ] Update ECS task definition with new key
- [ ] Create new task definition revision
- [ ] Update ECS service to use new revision
- [ ] Monitor deployment progress (wait for COMPLETED)
- [ ] Verify new task is running with new revision
- [ ] Check application logs for errors
- [ ] Test API endpoint that uses OpenAI
- [ ] Revoke old OpenAI API key
- [ ] Document the change (date, reason, new key ID)
- [ ] Update any local `.env` files (for development)

---

## 📞 Support

If you encounter issues:

1. **Check CloudWatch Logs:**
   - Go to CloudWatch → Log Groups → `/ecs/elevareai-api`
   - Look for error messages

2. **Check ECS Service Events:**
   - Go to ECS → Clusters → Services → Events tab
   - Review recent events for issues

3. **Verify AWS Permissions:**
   - Ensure your AWS user/role has:
     - `ecs:RegisterTaskDefinition`
     - `ecs:DescribeTaskDefinition`
     - `ecs:UpdateService`
     - `ecs:DescribeServices`

---

## 📚 Related Documentation

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [OpenAI API Keys](https://platform.openai.com/docs/api-reference/authentication)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [AWS Deployment Guide](./_docs/guides/AWS_DEPLOYMENT_GUIDE.md)

---

**Last Updated:** November 2025

