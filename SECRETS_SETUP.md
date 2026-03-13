# Google Cloud Secret Manager Setup Guide

This guide explains how to use Google Cloud Secret Manager to securely store sensitive configuration values (like API tokens) and make them available as environment variables in Cloud Run.

## Table of Contents

- [Why Use Secret Manager](#why-use-secret-manager)
- [Creating Secrets](#creating-secrets)
- [Using Secrets in Cloud Run](#using-secrets-in-cloud-run)
- [Local Development with Secrets](#local-development-with-secrets)
- [Best Practices](#best-practices)

---

## Why Use Secret Manager

**Benefits:**

- ✅ Secrets are encrypted at rest and in transit
- ✅ Centralized secret management across services
- ✅ Automatic secret rotation support
- ✅ Audit logging of secret access
- ✅ Version control for secrets
- ✅ No secrets in environment variables or code

**When to use Secret Manager:**

- API tokens (Instana API token)
- Database passwords
- Service account keys
- OAuth client secrets
- Any sensitive configuration data

---

## Creating Secrets

### Step 1: Enable Secret Manager API

```bash
# Enable the Secret Manager API
gcloud services enable secretmanager.googleapis.com
```

### Step 2: Create Secrets

Create secrets for sensitive values in your application:

```bash
# Set your project ID
PROJECT_ID=$(gcloud config get-value project)

# Create secret for Instana API token
echo -n "your-instana-api-token" | gcloud secrets create instana-api-token \
  --data-file=- \
  --replication-policy="automatic"

# Create secret for Instana base URL (optional, but good practice)
echo -n "https://your-instance.instana.io" | gcloud secrets create instana-base-url \
  --data-file=- \
  --replication-policy="automatic"

# Create secret for agent URL
echo -n "http://172.16.0.70:4001" | gcloud secrets create instana-agent-url \
  --data-file=- \
  --replication-policy="automatic"

# Create secret for OTLP agent URL
echo -n "http://172.16.0.70:4000" | gcloud secrets create instana-otlp-agent-url \
  --data-file=- \
  --replication-policy="automatic"
```

### Step 3: Grant Service Account Access to Secrets

```bash
# Grant the Cloud Run service account access to read secrets
SERVICE_ACCOUNT=server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com

# Grant access to each secret
gcloud secrets add-iam-policy-binding instana-api-token \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding instana-base-url \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding instana-agent-url \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding instana-otlp-agent-url \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 4: Verify Secrets

```bash
# List all secrets
gcloud secrets list

# View secret metadata (not the actual value)
gcloud secrets describe instana-api-token

# Access secret value (for testing)
gcloud secrets versions access latest --secret="instana-api-token"
```

---

## Using Secrets in Cloud Run

### Method 1: Mount Secrets as Environment Variables (Recommended)

This makes secrets available as environment variables, just like regular env vars.

```bash
# Deploy with secrets mounted as environment variables
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --service-account=server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com \
  --update-secrets="API_TOKEN=instana-api-token:latest" \
  --update-secrets="BASE_URL=instana-base-url:latest" \
  --update-secrets="AGENT_URL=instana-agent-url:latest" \
  --update-secrets="OTLP_AGENT_URL=instana-otlp-agent-url:latest" \
  --set-env-vars="BUCKET_NAME=antarsia_test" \
  --set-env-vars="BUCKET_FILE_PATH=serviceChk_finprodcoredc2.txt" \
  --set-env-vars="PROJECT_NAME=${PROJECT_ID}" \
  --set-env-vars="DASHBOARD_NAME=Finacle Monitor" \
  --set-env-vars="WIDGET_NAME=Service Status" \
  --set-env-vars="FINACLE_HOST=finprodcoredc2" \
  --set-env-vars="AS_ENDPOINT=True" \
  --set-env-vars="LOOP_PAUSE_IN_SECONDS=-1"
```

**How it works:**

- Cloud Run automatically fetches the secret value from Secret Manager
- The secret is exposed as an environment variable (e.g., `API_TOKEN`)
- Your Python code reads it using `os.getenv('API_TOKEN')` - no code changes needed!

### Method 2: Mount Secrets as Files

Alternatively, mount secrets as files in the container:

```bash
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --update-secrets="/secrets/api-token=instana-api-token:latest" \
  --update-secrets="/secrets/base-url=instana-base-url:latest"
```

Then read from files in your code:

```python
with open('/secrets/api-token', 'r') as f:
    api_token = f.read().strip()
```

### Method 3: Using Cloud Console

1. Go to Cloud Run → Select your service
2. Click "Edit & Deploy New Revision"
3. Go to "Variables & Secrets" tab
4. Click "Reference a Secret"
5. Select the secret and choose:
   - **Exposed as environment variable**: Enter variable name (e.g., `API_TOKEN`)
   - **Mounted as volume**: Enter mount path (e.g., `/secrets/api-token`)
6. Click "Deploy"

---

## Local Development with Secrets

### Option 1: Use .env File (Development Only)

For local development, continue using `.env` file:

```bash
# .env (local development only - DO NOT COMMIT)
API_TOKEN=your-instana-api-token
BASE_URL=https://your-instance.instana.io
AGENT_URL=http://172.16.0.70:4001
OTLP_AGENT_URL=http://172.16.0.70:4000
```

### Option 2: Fetch Secrets from Secret Manager

For local testing with actual secrets:

```bash
# Fetch secret and set as environment variable
export API_TOKEN=$(gcloud secrets versions access latest --secret="instana-api-token")
export BASE_URL=$(gcloud secrets versions access latest --secret="instana-base-url")

# Run the application
python process_server_status_entities.py
```

### Option 3: Create a Local Secrets Script

Create `load-secrets.sh`:

```bash
#!/bin/bash
# Load secrets from Secret Manager for local development

export API_TOKEN=$(gcloud secrets versions access latest --secret="instana-api-token")
export BASE_URL=$(gcloud secrets versions access latest --secret="instana-base-url")
export AGENT_URL=$(gcloud secrets versions access latest --secret="instana-agent-url")
export OTLP_AGENT_URL=$(gcloud secrets versions access latest --secret="instana-otlp-agent-url")

# Non-secret environment variables
export BUCKET_NAME=antarsia_test
export BUCKET_FILE_PATH=serviceChk_finprodcoredc2.txt
export PROJECT_NAME=$(gcloud config get-value project)
export DASHBOARD_NAME="Finacle Monitor"
export WIDGET_NAME="Service Status"
export FINACLE_HOST=finprodcoredc2
export AS_ENDPOINT=True
export LOOP_PAUSE_IN_SECONDS=-1

echo "Secrets loaded from Secret Manager"
```

Then use it:

```bash
chmod +x load-secrets.sh
source load-secrets.sh
python process_server_status_entities.py
```

---

## Managing Secrets

### Update a Secret

```bash
# Add a new version of a secret
echo -n "new-api-token-value" | gcloud secrets versions add instana-api-token \
  --data-file=-

# Cloud Run will automatically use the latest version
```

### List Secret Versions

```bash
# List all versions of a secret
gcloud secrets versions list instana-api-token

# Access a specific version
gcloud secrets versions access 2 --secret="instana-api-token"
```

### Delete a Secret

```bash
# Delete a specific version
gcloud secrets versions destroy 1 --secret="instana-api-token"

# Delete the entire secret
gcloud secrets delete instana-api-token
```

### Rotate Secrets

```bash
# Create new version
echo -n "new-token" | gcloud secrets versions add instana-api-token --data-file=-

# Deploy new revision to pick up the new version
gcloud run deploy server-status-monitor \
  --region us-central1 \
  --update-secrets="API_TOKEN=instana-api-token:latest"

# Disable old version
gcloud secrets versions disable 1 --secret="instana-api-token"
```

---

## Complete Deployment Example

Here's a complete deployment using secrets:

```bash
#!/bin/bash
# deploy-with-secrets.sh

PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT=server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com

# Create secrets (first time only)
echo -n "your-instana-api-token" | gcloud secrets create instana-api-token --data-file=- || true
echo -n "https://your-instance.instana.io" | gcloud secrets create instana-base-url --data-file=- || true
echo -n "http://172.16.0.70:4001" | gcloud secrets create instana-agent-url --data-file=- || true
echo -n "http://172.16.0.70:4000" | gcloud secrets create instana-otlp-agent-url --data-file=- || true

# Grant access to secrets
for secret in instana-api-token instana-base-url instana-agent-url instana-otlp-agent-url; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" || true
done

# Deploy with secrets
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --service-account=${SERVICE_ACCOUNT} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 300 \
  --update-secrets="API_TOKEN=instana-api-token:latest,BASE_URL=instana-base-url:latest,AGENT_URL=instana-agent-url:latest,OTLP_AGENT_URL=instana-otlp-agent-url:latest" \
  --set-env-vars="BUCKET_NAME=antarsia_test,BUCKET_FILE_PATH=serviceChk_finprodcoredc2.txt,PROJECT_NAME=${PROJECT_ID},DASHBOARD_NAME=Finacle Monitor,WIDGET_NAME=Service Status,FINACLE_HOST=finprodcoredc2,AS_ENDPOINT=True,LOOP_PAUSE_IN_SECONDS=-1,EVENT_DURATION=180000,MAX_SCHEDULED_INTERVAL_IN_MILLIS=60000"

echo "Deployment complete with secrets!"
```

---

## Best Practices

### ✅ DO

- **Use Secret Manager for all sensitive data** (API tokens, passwords, keys)
- **Use latest version** in Cloud Run (`--update-secrets="VAR=secret:latest"`)
- **Grant minimal permissions** (only `secretmanager.secretAccessor` role)
- **Use descriptive secret names** (e.g., `instana-api-token` not `token1`)
- **Rotate secrets regularly** (add new versions, disable old ones)
- **Use separate secrets per environment** (dev, staging, prod)
- **Audit secret access** using Cloud Logging

### ❌ DON'T

- **Don't commit secrets to git** (use `.gitignore` for `.env` files)
- **Don't hardcode secrets** in code or Dockerfiles
- **Don't share secrets across projects** (create separate secrets)
- **Don't use secrets for non-sensitive data** (use env vars for those)
- **Don't grant broad access** (avoid `roles/secretmanager.admin`)
- **Don't delete secrets without backup** (disable versions first)

---

## Troubleshooting

### Issue: "Permission denied" accessing secret

**Solution:**

```bash
# Grant access to the service account
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

### Issue: Secret not updating in Cloud Run

**Solution:**

```bash
# Deploy a new revision to pick up secret changes
gcloud run deploy server-status-monitor \
  --region us-central1 \
  --update-secrets="API_TOKEN=instana-api-token:latest"
```

### Issue: Can't access secrets locally

**Solution:**

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Verify you have access
gcloud secrets versions access latest --secret="instana-api-token"
```

---

## Summary

**For Cloud Run (Production):**

```bash
# Mount secrets as environment variables
gcloud run deploy server-status-monitor \
  --update-secrets="API_TOKEN=instana-api-token:latest" \
  --update-secrets="BASE_URL=instana-base-url:latest"
```

**For Local Development:**

```bash
# Use .env file or fetch from Secret Manager
export API_TOKEN=$(gcloud secrets versions access latest --secret="instana-api-token")
python process_server_status_entities.py
```

**No code changes needed!** Your application continues to use `os.getenv('API_TOKEN')` and it works in both environments.
