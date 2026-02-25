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
APP_NAME="purchase-tracker-backend"
ECR_REPOSITORY="purchase-tracker-backend"
CLUSTER_NAME="purchase-tracker-cluster"
SERVICE_NAME="purchase-tracker-task-service1"
TASK_FAMILY="purchase-tracker-task"

show_help() {
    echo -e "${BLUE}🚀 Purchase Tracker - Deployment Manager${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  update      - Build, push and deploy updated image (default)"
    echo "  force       - Force new deployment without building"
    echo "  logs        - Tail CloudWatch logs"
    echo "  status      - Check deployment status"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh              # Update and deploy"
    echo "  ./deploy.sh update       # Same as above"
    echo "  ./deploy.sh force        # Force redeploy without rebuild"
    echo "  ./deploy.sh logs         # Watch logs"
    echo ""
}

check_prerequisites() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI not found${NC}"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found${NC}"
        exit 1
    fi

    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        exit 1
    fi
}

build_and_push() {
    local ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPOSITORY}"
    
    echo -e "${BLUE}Step 1/3: Building Docker image...${NC}"
    docker build -t ${APP_NAME}:latest . > /dev/null 2>&1
    echo -e "${GREEN}   ✅ Image built${NC}"
    echo ""

    echo -e "${BLUE}Step 2/3: Pushing to ECR...${NC}"
    aws ecr get-login-password --region ${REGION} | \
        docker login --username AWS --password-stdin ${ECR_URI} 2>/dev/null
    
    docker tag ${APP_NAME}:latest ${ECR_URI}:latest
    docker tag ${APP_NAME}:latest ${ECR_URI}:$(date +%Y%m%d-%H%M%S)
    docker push ${ECR_URI}:latest > /dev/null 2>&1
    echo -e "${GREEN}   ✅ Image pushed to ECR${NC}"
    echo ""
}

force_deploy() {
    echo -e "${BLUE}Step 3/3: Deploying to ECS...${NC}"
    
    if aws ecs describe-services \
        --cluster ${CLUSTER_NAME} \
        --services ${SERVICE_NAME} \
        --region ${REGION} \
        --query 'services[0].serviceName' \
        --output text | grep -q "${SERVICE_NAME}"; then
        
        aws ecs update-service \
            --cluster ${CLUSTER_NAME} \
            --service ${SERVICE_NAME} \
            --force-new-deployment \
            --region ${REGION} > /dev/null
        
        echo -e "${GREEN}   ✅ Deployment triggered${NC}"
    else
        echo -e "${RED}   ❌ Service not found: ${SERVICE_NAME}${NC}"
        exit 1
    fi
    echo ""
}

show_status() {
    echo -e "${BLUE}📊 Deployment Status${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Get service info
    aws ecs describe-services \
        --cluster ${CLUSTER_NAME} \
        --services ${SERVICE_NAME} \
        --region ${REGION} \
        --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,TaskDef:taskDefinition}' \
        --output table
    
    echo ""
    echo -e "${BLUE}Recent Events:${NC}"
    aws ecs describe-services \
        --cluster ${CLUSTER_NAME} \
        --services ${SERVICE_NAME} \
        --region ${REGION} \
        --query 'services[0].events[0:3].{Time:createdAt,Message:message}' \
        --output table
}

tail_logs() {
    echo -e "${BLUE}📝 Tailing CloudWatch logs...${NC}"
    echo -e "${YELLOW}   (Press Ctrl+C to stop)${NC}"
    echo ""
    
    aws logs tail /ecs/${TASK_FAMILY} --follow --region ${REGION}
}

# Main script
check_prerequisites

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

COMMAND=${1:-update}

case "$COMMAND" in
    update)
        echo -e "${BLUE}🚀 Rebuild and Deploy Purchase Tracker${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BLUE}   AWS Account: ${AWS_ACCOUNT_ID}${NC}"
        echo -e "${BLUE}   Region: ${REGION}${NC}"
        echo -e "${BLUE}   ECR: ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPOSITORY}${NC}"
        echo ""
        
        build_and_push
        force_deploy
        
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✅ Deployment Complete!${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${BLUE}💡 Monitor deployment:${NC}"
        echo "   ./deploy.sh logs     # Watch logs"
        echo "   ./deploy.sh status   # Check status"
        echo ""
        ;;
    force)
        echo -e "${BLUE}🚀 Force Redeploy${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        force_deploy
        echo -e "${GREEN}✅ Redeploy triggered!${NC}"
        echo ""
        ;;
    logs)
        tail_logs
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

exit 0

