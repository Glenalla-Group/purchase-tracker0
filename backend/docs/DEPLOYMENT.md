# Purchase Tracker - Deployment Guide

## 🚀 Quick Reference

### Two Main Scripts

1. **`deploy.sh`** - Build and deploy your application
2. **`secrets.sh`** - Manage AWS Secrets Manager

---

## 📦 Secrets Management (`secrets.sh`)

Manage Gmail OAuth credentials in AWS Secrets Manager.

### Commands

```bash
# Upload credentials.json
./secrets.sh upload credentials

# Upload token.json
./secrets.sh upload token

# Upload both files
./secrets.sh upload all

# List all secrets
./secrets.sh list

# Verify secrets are valid
./secrets.sh verify
```

### Example Workflow

```bash
# 1. After updating credentials locally
./secrets.sh upload credentials

# 2. After re-authenticating (new token)
./secrets.sh upload token

# 3. Verify everything is set up correctly
./secrets.sh verify
```

---

## 🚀 Deployment (`deploy.sh`)

Build, push and deploy your application to AWS ECS.

### Commands

```bash
# Build new image and deploy
./deploy.sh update

# Force redeploy without rebuilding
./deploy.sh force

# Watch CloudWatch logs
./deploy.sh logs

# Check deployment status
./deploy.sh status
```

### Example Workflow

```bash
# 1. After making code changes
./deploy.sh update

# 2. Monitor deployment
./deploy.sh logs

# 3. Check status
./deploy.sh status
```

---

## 🏁 Initial Setup (First Time Only)

For first-time deployment to AWS, use:

```bash
./deploy-to-aws.sh
```

This script:
- Creates ECR repository
- Sets up IAM roles with proper permissions
- Creates ECS cluster and service
- Uploads secrets to Secrets Manager
- Deploys the initial application

**Note**: Only run this once. After initial setup, use `deploy.sh` for updates.

---

## 📋 Current AWS Resources

### ECS Configuration
- **Region**: `us-east-2`
- **Cluster**: `purchase-tracker-cluster`
- **Service**: `purchase-tracker-task-service1`
- **Task Family**: `purchase-tracker-task`
- **Container**: `purchase-tracker-container`

### ECR
- **Repository**: `purchase-tracker-backend`
- **URI**: `{AWS_ACCOUNT_ID}.dkr.ecr.us-east-2.amazonaws.com/purchase-tracker-backend`

### Secrets Manager
- `purchase-tracker/credentials` - Gmail OAuth client credentials
- `purchase-tracker/token` - Gmail OAuth access token

### IAM
- **Execution Role**: `ecsTaskExecutionRole`
- **Task Role**: `ecsTaskExecutionRole` (same, has Secrets Manager access)

---

## 🔍 Monitoring & Debugging

### Check Deployment Status
```bash
./deploy.sh status
```

### Watch Logs
```bash
./deploy.sh logs
```

### Verify Credentials
```bash
./secrets.sh verify
```

### Manual AWS CLI Commands

```bash
# Check ECS service
aws ecs describe-services \
  --cluster purchase-tracker-cluster \
  --services purchase-tracker-task-service1 \
  --region us-east-2

# View recent logs
aws logs tail /ecs/purchase-tracker-task --region us-east-2 --since 5m

# Check secrets
aws secretsmanager list-secrets --region us-east-2 \
  --query "SecretList[?starts_with(Name, 'purchase-tracker')]"
```

---

## ✅ Success Indicators

After deployment, check logs for:

```
✅ credentials.json loaded successfully
✅ token.json loaded successfully
✅ Gmail API Connection Test - SUCCESS
✅ Application startup complete
```

### Health Check Endpoints

```bash
# Basic health
curl https://your-domain.com/health

# Gmail authentication status
curl https://your-domain.com/health/gmail
```

---

## 🔧 Troubleshooting

### Credentials Not Loading

1. Verify secrets exist:
   ```bash
   ./secrets.sh verify
   ```

2. Check if ENVIRONMENT variable is set:
   ```bash
   ./deploy.sh logs | grep "ENVIRONMENT:"
   ```
   Should show: `ENVIRONMENT: production`

3. Verify IAM permissions are correct:
   ```bash
   aws iam get-role-policy \
     --role-name ecsTaskExecutionRole \
     --policy-name PurchaseTrackerSecretsAccess \
     --region us-east-2
   ```

### Deployment Fails

1. Check service events:
   ```bash
   ./deploy.sh status
   ```

2. View detailed logs:
   ```bash
   ./deploy.sh logs
   ```

3. Force new deployment:
   ```bash
   ./deploy.sh force
   ```

---

## 📁 Script Summary

| Script | Purpose | Usage |
|--------|---------|-------|
| `deploy.sh` | Build & deploy updates | `./deploy.sh update` |
| `secrets.sh` | Manage AWS secrets | `./secrets.sh upload all` |
| `deploy-to-aws.sh` | Initial AWS setup | `./deploy-to-aws.sh` (once) |
| `docker-entrypoint.sh` | Container startup | (automatic) |

---

## 🎯 Common Workflows

### Update Application Code
```bash
# Make your changes, then:
./deploy.sh update
./deploy.sh logs  # Monitor deployment
```

### Refresh Gmail Token
```bash
# Locally re-authenticate
python authenticate.py

# Upload new token
./secrets.sh upload token

# Force redeploy to use new token
./deploy.sh force
```

### Check Everything is Working
```bash
./secrets.sh verify
./deploy.sh status
./deploy.sh logs | grep "Gmail API Connection Test"
```

---

**Last Updated**: 2025-11-11  
**AWS Region**: us-east-2  
**Environment**: Production

