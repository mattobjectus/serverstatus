#!/bin/bash

# Deploy script for Server Status Monitor to Google Cloud Run
# This script builds and deploys the application to Cloud Run

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="server-status-monitor"
REGION="us-central1"
MEMORY="512Mi"
TIMEOUT="300"
MIN_INSTANCES="0"
MAX_INSTANCES="10"

echo -e "${GREEN}=== Server Status Monitor - Cloud Run Deployment ===${NC}\n"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project is set${NC}"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${GREEN}Project:${NC} $PROJECT_ID"
echo -e "${GREEN}Service:${NC} $SERVICE_NAME"
echo -e "${GREEN}Region:${NC} $REGION\n"

# Check if .env.cloudrun exists
if [ ! -f ".env.cloudrun" ]; then
    echo -e "${YELLOW}Warning: .env.cloudrun not found${NC}"
    echo "Creating from example..."
    if [ -f ".env.cloudrun.example" ]; then
        cp .env.cloudrun.example .env.cloudrun
        echo -e "${YELLOW}Please edit .env.cloudrun with your configuration before deploying${NC}"
        exit 1
    else
        echo -e "${RED}Error: .env.cloudrun.example not found${NC}"
        exit 1
    fi
fi

# Parse environment variables from .env.cloudrun
echo -e "${GREEN}Loading environment variables...${NC}"
ENV_VARS=""
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ $key =~ ^#.*$ ]] && continue
    [[ -z $key ]] && continue
    
    # Remove quotes from value
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    
    # Add to ENV_VARS
    if [ -n "$ENV_VARS" ]; then
        ENV_VARS="$ENV_VARS,$key=$value"
    else
        ENV_VARS="$key=$value"
    fi
done < .env.cloudrun

# Prompt for deployment confirmation
echo -e "\n${YELLOW}Ready to deploy. This will:${NC}"
echo "  1. Build Docker image from source"
echo "  2. Deploy to Cloud Run in region: $REGION"
echo "  3. Configure environment variables"
echo "  4. Set memory to $MEMORY and timeout to ${TIMEOUT}s"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Deploy to Cloud Run
echo -e "\n${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory $MEMORY \
  --timeout $TIMEOUT \
  --min-instances $MIN_INSTANCES \
  --max-instances $MAX_INSTANCES \
  --set-env-vars "$ENV_VARS"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format 'value(status.url)')

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "${GREEN}Service URL:${NC} $SERVICE_URL"
echo -e "${GREEN}Endpoint:${NC} $SERVICE_URL/api/v1/service/status"

# Test the endpoint
echo -e "\n${YELLOW}Testing endpoint...${NC}"
if curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/api/v1/service/status" | grep -q "200"; then
    echo -e "${GREEN}✓ Endpoint is responding${NC}"
else
    echo -e "${YELLOW}⚠ Endpoint test failed - check logs${NC}"
fi

# Show logs command
echo -e "\n${GREEN}View logs:${NC}"
echo "  gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"

# Show scheduler setup command
echo -e "\n${GREEN}Set up scheduled execution:${NC}"
echo "  gcloud scheduler jobs create http ${SERVICE_NAME}-job \\"
echo "    --schedule=\"*/5 * * * *\" \\"
echo "    --uri=\"$SERVICE_URL/api/v1/service/status\" \\"
echo "    --http-method=GET \\"
echo "    --location=$REGION"

echo -e "\n${GREEN}Done!${NC}"
