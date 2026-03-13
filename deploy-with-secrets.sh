#!/bin/bash

# Deploy script for Server Status Monitor to Google Cloud Run with Secret Manager
# This script creates secrets, grants permissions, and deploys with secrets mounted as env vars

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="server-status-monitor"
REGION="us-central1"
MEMORY="512Mi"
TIMEOUT="300"
MIN_INSTANCES="0"
MAX_INSTANCES="10"

echo -e "${GREEN}=== Server Status Monitor - Cloud Run Deployment with Secrets ===${NC}\n"

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

SERVICE_ACCOUNT="${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo -e "${GREEN}Project:${NC} $PROJECT_ID"
echo -e "${GREEN}Service:${NC} $SERVICE_NAME"
echo -e "${GREEN}Region:${NC} $REGION"
echo -e "${GREEN}Service Account:${NC} $SERVICE_ACCOUNT\n"

# Enable required APIs
echo -e "${BLUE}Enabling required APIs...${NC}"
gcloud services enable secretmanager.googleapis.com --quiet
gcloud services enable run.googleapis.com --quiet
echo -e "${GREEN}✓ APIs enabled${NC}\n"

# Prompt for secret values
echo -e "${YELLOW}=== Secret Configuration ===${NC}"
echo "Please provide values for secrets (or press Enter to skip if already created):"
echo ""

read -p "Instana API Token: " INSTANA_API_TOKEN
read -p "Instana Base URL (e.g., https://your-instance.instana.io): " INSTANA_BASE_URL
read -p "Instana Agent URL (e.g., http://172.16.0.70:4001): " INSTANA_AGENT_URL
read -p "Instana OTLP Agent URL (e.g., http://172.16.0.70:4000): " INSTANA_OTLP_AGENT_URL

echo ""

# Create secrets if values were provided
if [ -n "$INSTANA_API_TOKEN" ]; then
    echo -e "${BLUE}Creating/updating secret: instana-api-token${NC}"
    echo -n "$INSTANA_API_TOKEN" | gcloud secrets create instana-api-token \
        --data-file=- \
        --replication-policy="automatic" 2>/dev/null || \
    echo -n "$INSTANA_API_TOKEN" | gcloud secrets versions add instana-api-token \
        --data-file=-
    echo -e "${GREEN}✓ instana-api-token created/updated${NC}"
fi

if [ -n "$INSTANA_BASE_URL" ]; then
    echo -e "${BLUE}Creating/updating secret: instana-base-url${NC}"
    echo -n "$INSTANA_BASE_URL" | gcloud secrets create instana-base-url \
        --data-file=- \
        --replication-policy="automatic" 2>/dev/null || \
    echo -n "$INSTANA_BASE_URL" | gcloud secrets versions add instana-base-url \
        --data-file=-
    echo -e "${GREEN}✓ instana-base-url created/updated${NC}"
fi

if [ -n "$INSTANA_AGENT_URL" ]; then
    echo -e "${BLUE}Creating/updating secret: instana-agent-url${NC}"
    echo -n "$INSTANA_AGENT_URL" | gcloud secrets create instana-agent-url \
        --data-file=- \
        --replication-policy="automatic" 2>/dev/null || \
    echo -n "$INSTANA_AGENT_URL" | gcloud secrets versions add instana-agent-url \
        --data-file=-
    echo -e "${GREEN}✓ instana-agent-url created/updated${NC}"
fi

if [ -n "$INSTANA_OTLP_AGENT_URL" ]; then
    echo -e "${BLUE}Creating/updating secret: instana-otlp-agent-url${NC}"
    echo -n "$INSTANA_OTLP_AGENT_URL" | gcloud secrets create instana-otlp-agent-url \
        --data-file=- \
        --replication-policy="automatic" 2>/dev/null || \
    echo -n "$INSTANA_OTLP_AGENT_URL" | gcloud secrets versions add instana-otlp-agent-url \
        --data-file=-
    echo -e "${GREEN}✓ instana-otlp-agent-url created/updated${NC}"
fi

echo ""

# Grant service account access to secrets
echo -e "${BLUE}Granting service account access to secrets...${NC}"
for secret in instana-api-token instana-base-url instana-agent-url instana-otlp-agent-url; do
    # Check if secret exists
    if gcloud secrets describe $secret &>/dev/null; then
        gcloud secrets add-iam-policy-binding $secret \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
        echo -e "${GREEN}✓ Granted access to $secret${NC}"
    fi
done

echo ""

# Prompt for non-secret environment variables
echo -e "${YELLOW}=== Environment Configuration ===${NC}"
read -p "GCS Bucket Name [antarsia_test]: " BUCKET_NAME
BUCKET_NAME=${BUCKET_NAME:-antarsia_test}

read -p "GCS File Path [serviceChk_finprodcoredc2.txt]: " BUCKET_FILE_PATH
BUCKET_FILE_PATH=${BUCKET_FILE_PATH:-serviceChk_finprodcoredc2.txt}

read -p "Dashboard Name [Finacle Monitor]: " DASHBOARD_NAME
DASHBOARD_NAME=${DASHBOARD_NAME:-Finacle Monitor}

read -p "Widget Name [Service Status]: " WIDGET_NAME
WIDGET_NAME=${WIDGET_NAME:-Service Status}

read -p "Finacle Host [finprodcoredc2]: " FINACLE_HOST
FINACLE_HOST=${FINACLE_HOST:-finprodcoredc2}

read -p "Event Duration (ms) [180000]: " EVENT_DURATION
EVENT_DURATION=${EVENT_DURATION:-180000}

read -p "Max Scheduled Interval (ms) [60000]: " MAX_SCHEDULED_INTERVAL
MAX_SCHEDULED_INTERVAL=${MAX_SCHEDULED_INTERVAL:-60000}

echo ""

# Build secrets parameter
SECRETS_PARAM=""
if gcloud secrets describe instana-api-token &>/dev/null; then
    SECRETS_PARAM="${SECRETS_PARAM}API_TOKEN=instana-api-token:latest,"
fi
if gcloud secrets describe instana-base-url &>/dev/null; then
    SECRETS_PARAM="${SECRETS_PARAM}BASE_URL=instana-base-url:latest,"
fi
if gcloud secrets describe instana-agent-url &>/dev/null; then
    SECRETS_PARAM="${SECRETS_PARAM}AGENT_URL=instana-agent-url:latest,"
fi
if gcloud secrets describe instana-otlp-agent-url &>/dev/null; then
    SECRETS_PARAM="${SECRETS_PARAM}OTLP_AGENT_URL=instana-otlp-agent-url:latest,"
fi
# Remove trailing comma
SECRETS_PARAM=${SECRETS_PARAM%,}

# Prompt for deployment confirmation
echo -e "\n${YELLOW}Ready to deploy with the following configuration:${NC}"
echo "  Project: $PROJECT_ID"
echo "  Service: $SERVICE_NAME"
echo "  Region: $REGION"
echo "  Bucket: $BUCKET_NAME"
echo "  File Path: $BUCKET_FILE_PATH"
echo "  Dashboard: $DASHBOARD_NAME"
echo "  Widget: $WIDGET_NAME"
echo "  Finacle Host: $FINACLE_HOST"
echo "  Secrets: ${SECRETS_PARAM:-None}"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Deploy to Cloud Run
echo -e "\n${GREEN}Deploying to Cloud Run...${NC}"

DEPLOY_CMD="gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory $MEMORY \
  --timeout $TIMEOUT \
  --min-instances $MIN_INSTANCES \
  --max-instances $MAX_INSTANCES \
  --service-account=$SERVICE_ACCOUNT \
  --set-env-vars=\"BUCKET_NAME=${BUCKET_NAME},BUCKET_FILE_PATH=${BUCKET_FILE_PATH},PROJECT_NAME=${PROJECT_ID},DASHBOARD_NAME=${DASHBOARD_NAME},WIDGET_NAME=${WIDGET_NAME},FINACLE_HOST=${FINACLE_HOST},AS_ENDPOINT=True,LOOP_PAUSE_IN_SECONDS=-1,EVENT_DURATION=${EVENT_DURATION},MAX_SCHEDULED_INTERVAL_IN_MILLIS=${MAX_SCHEDULED_INTERVAL}\""

# Add secrets if any exist
if [ -n "$SECRETS_PARAM" ]; then
    DEPLOY_CMD="${DEPLOY_CMD} --update-secrets=\"${SECRETS_PARAM}\""
fi

# Execute deployment
eval $DEPLOY_CMD

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format 'value(status.url)')

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "${GREEN}Service URL:${NC} $SERVICE_URL"
echo -e "${GREEN}Endpoint:${NC} $SERVICE_URL/api/v1/service/status"

# Test the endpoint
echo -e "\n${YELLOW}Testing endpoint...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/api/v1/service/status" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Endpoint is responding (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}⚠ Endpoint test returned HTTP $HTTP_CODE - check logs${NC}"
fi

# Show useful commands
echo -e "\n${GREEN}Useful commands:${NC}"
echo -e "${BLUE}View logs:${NC}"
echo "  gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"

echo -e "\n${BLUE}Update a secret:${NC}"
echo "  echo -n 'new-value' | gcloud secrets versions add instana-api-token --data-file=-"
echo "  gcloud run deploy $SERVICE_NAME --region $REGION  # Deploy new revision"

echo -e "\n${BLUE}Set up scheduled execution:${NC}"
echo "  gcloud scheduler jobs create http ${SERVICE_NAME}-job \\"
echo "    --schedule=\"*/5 * * * *\" \\"
echo "    --uri=\"$SERVICE_URL/api/v1/service/status\" \\"
echo "    --http-method=GET \\"
echo "    --location=$REGION"

echo -e "\n${GREEN}Done!${NC}"
