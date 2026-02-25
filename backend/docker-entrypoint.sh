#!/bin/bash
set -e

echo "============================================================"
echo "Docker Entrypoint - Starting"
echo "ENVIRONMENT: ${ENVIRONMENT:-not set}"
echo "AWS_REGION: ${AWS_REGION:-us-east-2}"
echo "============================================================"

# Fetch credentials from AWS Secrets Manager if in production
if [ "$ENVIRONMENT" = "production" ]; then
    echo "🔐 Production mode detected - fetching credentials from AWS Secrets Manager..."
    
    # Set AWS region
    export AWS_DEFAULT_REGION=${AWS_REGION:-us-east-2}
    
    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        echo "❌ ERROR: AWS CLI not found in container!"
        echo "   Gmail features will not work"
    else
        echo "✓ AWS CLI available"
        
        # Try to fetch OAuth client credentials
        echo "📥 Fetching credentials.json from AWS Secrets Manager..."
        if aws secretsmanager get-secret-value \
            --secret-id purchase-tracker/credentials \
            --region ${AWS_DEFAULT_REGION} \
            --query SecretString \
            --output text > /app/credentials.json 2>/tmp/aws-error.log; then
            chmod 600 /app/credentials.json
            echo "✅ credentials.json loaded successfully"
        else
            echo "❌ Failed to fetch credentials.json"
            cat /tmp/aws-error.log
            echo "   Gmail features will not work"
            echo "   Run: ./setup-aws-secrets.sh to upload secrets"
        fi
        
        # Try to fetch OAuth token
        echo "📥 Fetching token.json from AWS Secrets Manager..."
        if aws secretsmanager get-secret-value \
            --secret-id purchase-tracker/token \
            --region ${AWS_DEFAULT_REGION} \
            --query SecretString \
            --output text > /app/token.json 2>/tmp/aws-error.log; then
            chmod 600 /app/token.json
            echo "✅ token.json loaded successfully"
        else
            echo "❌ Failed to fetch token.json"
            cat /tmp/aws-error.log
            echo "   Gmail features will not work"
            echo "   Run: ./setup-aws-secrets.sh to upload secrets"
        fi
        
        # Verify files exist
        if [ -f "/app/credentials.json" ] && [ -f "/app/token.json" ]; then
            echo "✅ All credentials loaded successfully"
        else
            echo "⚠️  Some credentials are missing - Gmail features may not work"
        fi
    fi
else
    echo "📝 Development/Local mode - using local credential files"
    if [ -f "/app/credentials.json" ]; then
        echo "✓ credentials.json found"
    else
        echo "⚠️  credentials.json not found"
    fi
    if [ -f "/app/token.json" ]; then
        echo "✓ token.json found"
    else
        echo "⚠️  token.json not found"
    fi
fi

echo "============================================================"
echo "Starting application..."
echo "============================================================"

# Execute the main command
exec "$@"

