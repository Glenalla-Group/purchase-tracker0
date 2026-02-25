#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REGION="${AWS_REGION:-us-east-2}"
S3_BUCKET="${S3_BUCKET:-}"
S3_ENV_KEY="${S3_ENV_KEY:-purchase-tracker/.env}"

# Load config file if it exists (secrets.config in same directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/secrets.config" ]; then
    source "$SCRIPT_DIR/secrets.config"
fi

show_help() {
    echo -e "${BLUE}📦 Purchase Tracker - Secrets Manager${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: ./secrets.sh <command>"
    echo ""
    echo "Commands:"
    echo "  upload credentials  - Upload credentials.json to AWS Secrets Manager"
    echo "  upload token       - Upload token.json to AWS Secrets Manager"
    echo "  upload env         - Upload .env file to S3"
    echo "  upload all         - Upload credentials, token, and .env"
    echo "  list               - List all secrets"
    echo "  verify             - Verify secrets exist and are accessible"
    echo ""
    echo "Environment Variables:"
    echo "  S3_BUCKET          - S3 bucket name (required for env upload)"
    echo "  S3_ENV_KEY         - S3 key/path for .env (default: purchase-tracker/.env)"
    echo ""
    echo "Configuration File:"
    echo "  Create secrets.config file to set S3_BUCKET automatically"
    echo "  See secrets.config.example for template"
    echo ""
    echo "Examples:"
    echo "  ./secrets.sh upload credentials"
    echo "  S3_BUCKET=my-bucket ./secrets.sh upload env"
    echo "  source secrets.config && ./secrets.sh upload env"
    echo "  ./secrets.sh upload all"
    echo "  ./secrets.sh verify"
    echo ""
}

check_prerequisites() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI not found${NC}"
        echo -e "${YELLOW}   Install with: pip install awscli${NC}"
        exit 1
    fi

    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        echo -e "${YELLOW}   Run: aws configure${NC}"
        exit 1
    fi
}

upload_secret() {
    local FILE=$1
    local SECRET_NAME=$2
    local DESCRIPTION=$3

    if [ ! -f "$FILE" ]; then
        echo -e "${RED}❌ Error: $FILE not found${NC}"
        return 1
    fi

    echo -e "${BLUE}📤 Uploading $FILE to AWS Secrets Manager...${NC}"

    if aws secretsmanager describe-secret --secret-id $SECRET_NAME --region $REGION &>/dev/null; then
        echo -e "${YELLOW}   ⚠️  Secret exists, updating...${NC}"
        aws secretsmanager update-secret \
            --secret-id $SECRET_NAME \
            --secret-string file://$FILE \
            --region $REGION > /dev/null
    else
        echo -e "${YELLOW}   Creating new secret...${NC}"
        aws secretsmanager create-secret \
            --name $SECRET_NAME \
            --description "$DESCRIPTION" \
            --secret-string file://$FILE \
            --region $REGION > /dev/null
    fi

    echo -e "${GREEN}   ✅ $FILE uploaded successfully${NC}"
}

upload_credentials() {
    upload_secret "credentials.json" "purchase-tracker/credentials" "Google OAuth credentials for Purchase Tracker"
}

upload_token() {
    upload_secret "token.json" "purchase-tracker/token" "Gmail OAuth token for Purchase Tracker"
}

upload_env() {
    local ENV_FILE="${1:-.env}"
    
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}❌ Error: $ENV_FILE not found${NC}"
        echo -e "${YELLOW}   Looking for: $(pwd)/$ENV_FILE${NC}"
        return 1
    fi

    if [ -z "$S3_BUCKET" ]; then
        echo -e "${RED}❌ Error: S3_BUCKET environment variable not set${NC}"
        echo -e "${YELLOW}   Set it with: export S3_BUCKET=your-bucket-name${NC}"
        echo -e "${YELLOW}   Or run: S3_BUCKET=your-bucket-name ./secrets.sh upload env${NC}"
        return 1
    fi

    echo -e "${BLUE}📤 Uploading $ENV_FILE to S3...${NC}"
    echo -e "${BLUE}   Bucket: $S3_BUCKET${NC}"
    echo -e "${BLUE}   Key: $S3_ENV_KEY${NC}"

    if aws s3 cp "$ENV_FILE" "s3://${S3_BUCKET}/${S3_ENV_KEY}" --region $REGION; then
        echo -e "${GREEN}   ✅ $ENV_FILE uploaded successfully to s3://${S3_BUCKET}/${S3_ENV_KEY}${NC}"
        
        # Verify upload
        if aws s3 ls "s3://${S3_BUCKET}/${S3_ENV_KEY}" --region $REGION &>/dev/null; then
            echo -e "${GREEN}   ✅ Verified: File exists in S3${NC}"
        else
            echo -e "${YELLOW}   ⚠️  Warning: Could not verify file in S3${NC}"
        fi
    else
        echo -e "${RED}   ❌ Failed to upload $ENV_FILE to S3${NC}"
        return 1
    fi
}

list_secrets() {
    echo -e "${BLUE}📋 Listing Purchase Tracker secrets...${NC}"
    echo ""
    aws secretsmanager list-secrets \
        --region $REGION \
        --query "SecretList[?starts_with(Name, 'purchase-tracker')].{Name:Name,Description:Description,LastChanged:LastChangedDate}" \
        --output table
}

verify_secrets() {
    echo -e "${BLUE}🔍 Verifying secrets...${NC}"
    echo ""
    
    local secrets=("purchase-tracker/credentials" "purchase-tracker/token")
    local all_good=true
    
    for secret in "${secrets[@]}"; do
        if aws secretsmanager describe-secret --secret-id $secret --region $REGION &>/dev/null; then
            echo -e "${GREEN}   ✅ $secret - OK${NC}"
            
            # Get value to verify it's valid JSON
            if aws secretsmanager get-secret-value --secret-id $secret --region $REGION --query SecretString --output text | jq . &>/dev/null; then
                echo -e "${GREEN}      (Valid JSON)${NC}"
            else
                echo -e "${YELLOW}      ⚠️  Warning: Not valid JSON${NC}"
                all_good=false
            fi
        else
            echo -e "${RED}   ❌ $secret - NOT FOUND${NC}"
            all_good=false
        fi
    done
    
    echo ""
    if [ "$all_good" = true ]; then
        echo -e "${GREEN}✅ All secrets verified successfully!${NC}"
    else
        echo -e "${YELLOW}⚠️  Some secrets have issues${NC}"
        exit 1
    fi
}

# Main script
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

check_prerequisites

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${BLUE}🔐 AWS Secrets Manager${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}   AWS Account: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${BLUE}   Region: ${REGION}${NC}"
echo ""

case "$1" in
    upload)
        case "$2" in
            credentials)
                upload_credentials
                ;;
            token)
                upload_token
                ;;
            env)
                upload_env
                ;;
            all)
                upload_credentials
                upload_token
                if [ -n "$S3_BUCKET" ]; then
                    upload_env
                else
                    echo -e "${YELLOW}   ⚠️  Skipping .env upload (S3_BUCKET not set)${NC}"
                    echo -e "${YELLOW}   Set S3_BUCKET to upload .env file${NC}"
                fi
                ;;
            *)
                echo -e "${RED}❌ Unknown upload target: $2${NC}"
                echo -e "${YELLOW}   Use: credentials, token, env, or all${NC}"
                exit 1
                ;;
        esac
        echo ""
        echo -e "${GREEN}✅ Upload complete!${NC}"
        ;;
    list)
        list_secrets
        ;;
    verify)
        verify_secrets
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

exit 0

