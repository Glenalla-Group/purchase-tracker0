#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="${AWS_REGION:-us-east-1}"
APP_NAME="purchase-tracker"
SECRET_NAME="purchase-tracker/credentials"
CLUSTER_NAME="${APP_NAME}-cluster"
SERVICE_NAME="${APP_NAME}-service"
ROLE_NAME="${APP_NAME}-task-role"

echo -e "${BLUE}🚀 Purchase Tracker - AWS Deployment Script${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install it first.${NC}"
    exit 1
fi

if [ ! -f "credentials.json" ]; then
    echo -e "${RED}❌ credentials.json not found in current directory${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Step 1: Store credentials in Secrets Manager
echo -e "${BLUE}📦 Step 1/6: Storing credentials in AWS Secrets Manager...${NC}"
if aws secretsmanager describe-secret --secret-id $SECRET_NAME --region $REGION &>/dev/null; then
    echo -e "${YELLOW}⚠️  Secret already exists. Updating...${NC}"
    aws secretsmanager update-secret \
        --secret-id $SECRET_NAME \
        --secret-string file://credentials.json \
        --region $REGION &>/dev/null
    echo -e "${GREEN}✅ Credentials updated${NC}"
else
    aws secretsmanager create-secret \
        --name $SECRET_NAME \
        --description "Google credentials for Purchase Tracker" \
        --secret-string file://credentials.json \
        --region $REGION &>/dev/null
    echo -e "${GREEN}✅ Credentials stored securely${NC}"
fi
echo ""

# Step 2: Create ECR repository
echo -e "${BLUE}📦 Step 2/6: Setting up ECR repository...${NC}"
if ! aws ecr describe-repositories --repository-names $APP_NAME --region $REGION &>/dev/null; then
    aws ecr create-repository \
        --repository-name $APP_NAME \
        --region $REGION &>/dev/null
    echo -e "${GREEN}✅ ECR repository created${NC}"
else
    echo -e "${GREEN}✅ ECR repository already exists${NC}"
fi

ECR_URI=$(aws ecr describe-repositories \
    --repository-names $APP_NAME \
    --region $REGION \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo -e "${BLUE}   Repository: ${ECR_URI}${NC}"
echo ""

# Step 3: Build and push Docker image
echo -e "${BLUE}🐳 Step 3/6: Building and pushing Docker image...${NC}"
echo -e "${YELLOW}   (This may take a few minutes...)${NC}"

# Login to ECR
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ECR_URI 2>/dev/null

# Build image
docker build -t $APP_NAME . -q
docker tag $APP_NAME:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest 2>&1 | grep -E "(digest|latest)" || true
echo -e "${GREEN}✅ Image pushed to ECR${NC}"
echo ""

# Step 4: Create IAM role
echo -e "${BLUE}🔐 Step 4/6: Setting up IAM role and permissions...${NC}"
if ! aws iam get-role --role-name $ROLE_NAME &>/dev/null; then
    # Create trust policy
    cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json &>/dev/null

    # Create secrets policy
    cat > /tmp/secrets-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ],
    "Resource": [
      "arn:aws:secretsmanager:${REGION}:${AWS_ACCOUNT_ID}:secret:${SECRET_NAME}*",
      "arn:aws:secretsmanager:${REGION}:${AWS_ACCOUNT_ID}:secret:purchase-tracker/token*"
    ]
  }]
}
EOF

    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name SecretsAccess \
        --policy-document file:///tmp/secrets-policy.json

    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    # Wait for role to propagate
    sleep 5
    echo -e "${GREEN}✅ IAM role created with Secrets Manager access${NC}"
else
    echo -e "${GREEN}✅ IAM role already exists${NC}"
fi
echo ""

# Step 5: Create CloudWatch log group
echo -e "${BLUE}📊 Step 5/6: Setting up CloudWatch logs...${NC}"
if ! aws logs describe-log-groups --log-group-name-prefix "/ecs/$APP_NAME" --region $REGION | grep -q "/ecs/$APP_NAME" 2>/dev/null; then
    aws logs create-log-group \
        --log-group-name /ecs/$APP_NAME \
        --region $REGION &>/dev/null
    echo -e "${GREEN}✅ CloudWatch log group created${NC}"
else
    echo -e "${GREEN}✅ CloudWatch log group already exists${NC}"
fi
echo ""

# Step 6: Create/Update ECS resources
echo -e "${BLUE}☁️  Step 6/6: Deploying to ECS...${NC}"

# Check if cluster exists
if ! aws ecs describe-clusters --clusters $CLUSTER_NAME --region $REGION | grep -q "ACTIVE" 2>/dev/null; then
    echo -e "${YELLOW}   Creating ECS cluster...${NC}"
    aws ecs create-cluster \
        --cluster-name $CLUSTER_NAME \
        --region $REGION &>/dev/null
    echo -e "${GREEN}   ✅ Cluster created${NC}"
else
    echo -e "${GREEN}   ✅ Cluster already exists${NC}"
fi

# Create task definition
cat > /tmp/task-definition.json << EOF
{
  "family": "$APP_NAME",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}",
  "containerDefinitions": [
    {
      "name": "$APP_NAME",
      "image": "${ECR_URI}:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "HOST",
          "value": "0.0.0.0"
        },
        {
          "name": "PORT",
          "value": "8000"
        },
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "AWS_REGION",
          "value": "${REGION}"
        },
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "${REGION}"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/$APP_NAME",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Register task definition
TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region $REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo -e "${GREEN}   ✅ Task definition registered${NC}"

# Check if service exists
if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION | grep -q "ACTIVE" 2>/dev/null; then
    echo -e "${YELLOW}   Updating existing service...${NC}"
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $TASK_DEF_ARN \
        --force-new-deployment \
        --region $REGION &>/dev/null
    echo -e "${GREEN}   ✅ Service updated${NC}"
else
    echo -e "${YELLOW}   Creating new service...${NC}"
    
    # Get VPC and subnet info
    VPC_ID=$(aws ec2 describe-vpcs \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' \
        --output text \
        --region $REGION)
    
    SUBNET_IDS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query 'Subnets[*].SubnetId' \
        --output text \
        --region $REGION | tr '\t' ',')
    
    # Create security group if needed
    SG_NAME="${APP_NAME}-sg"
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region $REGION 2>/dev/null)
    
    if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --group-name $SG_NAME \
            --description "Security group for $APP_NAME" \
            --vpc-id $VPC_ID \
            --region $REGION \
            --query 'GroupId' \
            --output text)
        
        # Allow inbound on port 8000
        aws ec2 authorize-security-group-ingress \
            --group-id $SG_ID \
            --protocol tcp \
            --port 8000 \
            --cidr 0.0.0.0/0 \
            --region $REGION &>/dev/null || true
        
        echo -e "${GREEN}   ✅ Security group created${NC}"
    fi
    
    # Create service
    aws ecs create-service \
        --cluster $CLUSTER_NAME \
        --service-name $SERVICE_NAME \
        --task-definition $TASK_DEF_ARN \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
        --region $REGION &>/dev/null
    
    echo -e "${GREEN}   ✅ Service created${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✨ Deployment Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📝 Deployment Summary:${NC}"
echo "   • Region: $REGION"
echo "   • Cluster: $CLUSTER_NAME"
echo "   • Service: $SERVICE_NAME"
echo "   • ECR: $ECR_URI"
echo "   • Task Role: $ROLE_NAME"
echo "   • Secret: $SECRET_NAME"
echo ""
echo -e "${BLUE}📊 View logs:${NC}"
echo "   aws logs tail /ecs/$APP_NAME --follow --region $REGION"
echo ""
echo -e "${BLUE}🔍 Check service status:${NC}"
echo "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo ""
echo -e "${BLUE}🌐 Get task public IP (once running):${NC}"
echo "   aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --region $REGION --query 'taskArns[0]' --output text | xargs -I {} aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks {} --region $REGION --query 'tasks[0].attachments[0].details[?name==\`networkInterfaceId\`].value' --output text | xargs -I {} aws ec2 describe-network-interfaces --network-interface-ids {} --region $REGION --query 'NetworkInterfaces[0].Association.PublicIp' --output text"
echo ""
echo -e "${YELLOW}⏳ Note: Service may take 2-3 minutes to start${NC}"

# Clean up temp files
rm -f /tmp/trust-policy.json /tmp/secrets-policy.json /tmp/task-definition.json

exit 0

