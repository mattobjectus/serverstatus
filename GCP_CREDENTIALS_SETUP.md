# GCP Credentials Setup Guide

This guide explains how to set up Google Cloud Platform credentials for the Server Status Monitor application in different environments.

## Table of Contents

- [Cloud Run (Production)](#cloud-run-production)
- [Local Docker Testing](#local-docker-testing)
- [Local Development (No Docker)](#local-development-no-docker)
- [Troubleshooting](#troubleshooting)

---

## Cloud Run (Production)

### ✅ Automatic Authentication (Recommended)

When deployed to Cloud Run, **no manual credential configuration is needed**. Cloud Run automatically provides credentials through Workload Identity.

### Step 1: Create a Service Account

```bash
# Create a dedicated service account
gcloud iam service-accounts create server-status-monitor \
  --display-name="Server Status Monitor" \
  --description="Service account for server status monitoring application"
```

### Step 2: Grant Required Permissions

The service account needs both `storage.buckets.get` and `storage.objects.get` permissions. Use one of these approaches:

**Option A: Grant Storage Object Viewer role (Project-level)**

```bash
# Get your project ID
PROJECT_ID=$(gcloud config get-value project)

# Grant Storage Object Viewer role (includes both bucket and object access)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

**Option B: Grant bucket-specific access (More Secure - Recommended)**

```bash
# Grant both roles at bucket level
gsutil iam ch serviceAccount:server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectViewer \
  gs://antarsia_test

# Verify permissions
gsutil iam get gs://antarsia_test
```

**Option C: Use Legacy Bucket ACLs (Alternative)**

```bash
# Grant READER access to bucket
gsutil acl ch -u server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com:R \
  gs://antarsia_test
```

**Note:** The `storage.objectViewer` role includes both `storage.buckets.get` and `storage.objects.get` permissions, which are required for the application to access GCS buckets.

### Step 3: Deploy with Service Account

```bash
# Deploy Cloud Run service with the service account attached
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --service-account=server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com \
  --allow-unauthenticated
```

### Step 4: Verify Authentication

```bash
# Check which service account is attached
gcloud run services describe server-status-monitor \
  --region us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"

# Test the service
SERVICE_URL=$(gcloud run services describe server-status-monitor \
  --region us-central1 \
  --format='value(status.url)')
curl $SERVICE_URL/api/v1/service/status
```

### Important Notes for Cloud Run

- ✅ **DO NOT** set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- ✅ **DO NOT** include credential files in the Docker image
- ✅ Cloud Run automatically injects credentials at runtime
- ✅ Use the service account attached to the Cloud Run service

---

## Local Docker Testing

When running the Docker container locally, you need to provide credentials manually.

### Option 1: Mount Service Account Key (Recommended)

**Step 1: Create and Download Service Account Key**

```bash
# Create service account (if not already created)
gcloud iam service-accounts create server-status-monitor-local \
  --display-name="Server Status Monitor Local Testing"

# Grant permissions
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:server-status-monitor-local@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Create and download key
gcloud iam service-accounts keys create ~/gcp-keys/server-status-monitor-key.json \
  --iam-account=server-status-monitor-local@${PROJECT_ID}.iam.gserviceaccount.com
```

**Step 2: Run Docker with Mounted Credentials**

```bash
# Build the image
docker build -t server-status-monitor .

# Run with mounted credentials
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v ~/gcp-keys/server-status-monitor-key.json:/app/certs/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  server-status-monitor

# Test the endpoint
curl http://localhost:8080/api/v1/service/status
```

### Option 2: Use Application Default Credentials (ADC)

**Step 1: Authenticate with gcloud**

```bash
# Login and set application default credentials
gcloud auth application-default login
```

**Step 2: Run Docker with ADC Mounted**

```bash
# Mount the gcloud config directory
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  server-status-monitor
```

### Option 3: Test Without GCS (Local File Override)

For testing without GCS access:

**Step 1: Configure Local File Override**

Edit `.env.cloudrun`:

```bash
USE_LOCAL_FILE_INSTEAD_OF_BUCKET_PATH=test/demo/serviceChk_finprodcoredc.txt
```

**Step 2: Run Docker with Test Files Mounted**

```bash
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v $(pwd)/test:/app/test:ro \
  server-status-monitor
```

---

## Local Development (No Docker)

For running the Python script directly on your local machine.

### Option 1: Use Service Account Key File

**Step 1: Download Service Account Key**

```bash
# Create service account and key (if not already done)
PROJECT_ID=$(gcloud config get-value project)
gcloud iam service-accounts keys create ~/gcp-keys/server-status-monitor-key.json \
  --iam-account=server-status-monitor-local@${PROJECT_ID}.iam.gserviceaccount.com
```

**Step 2: Set Environment Variable**

```bash
# Set the credentials path
export GOOGLE_APPLICATION_CREDENTIALS=~/gcp-keys/server-status-monitor-key.json

# Run the application
python process_server_status_entities.py
```

Or add to your `.env` file:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/Users/yourusername/gcp-keys/server-status-monitor-key.json
```

### Option 2: Use Application Default Credentials

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Run the application (no GOOGLE_APPLICATION_CREDENTIALS needed)
python process_server_status_entities.py
```

### Option 3: Use Local File (No GCS)

Edit `.env`:

```bash
USE_LOCAL_FILE_INSTEAD_OF_BUCKET_PATH=test/demo/serviceChk_finprodcoredc.txt
```

Then run:

```bash
python process_server_status_entities.py
```

---

## Troubleshooting

### Issue: "Could not automatically determine credentials"

**Cause:** No credentials are configured.

**Solution:**

```bash
# For local development
gcloud auth application-default login

# For Docker
docker run -v ~/gcp-keys/key.json:/app/certs/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  ...
```

### Issue: "Permission denied" or "storage.buckets.get access denied" when accessing GCS bucket

**Cause:** Service account lacks required permissions (`storage.buckets.get` and/or `storage.objects.get`).

**Solution - Grant proper IAM roles:**

```bash
PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME=your-bucket-name
SERVICE_ACCOUNT=server-status-monitor@${PROJECT_ID}.iam.gserviceaccount.com

# Option 1: Grant Storage Object Viewer at project level (includes both permissions)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectViewer"

# Option 2: Grant at bucket level (more secure)
gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectViewer \
  gs://${BUCKET_NAME}

# Option 3: If using legacy ACLs
gsutil acl ch -u ${SERVICE_ACCOUNT}:R gs://${BUCKET_NAME}

# Verify permissions were granted
gsutil iam get gs://${BUCKET_NAME} | grep ${SERVICE_ACCOUNT}
```

**Verify the service account has the correct permissions:**

```bash
# Check IAM policy on bucket
gsutil iam get gs://${BUCKET_NAME}

# Test access with service account
gcloud storage ls gs://${BUCKET_NAME} \
  --impersonate-service-account=${SERVICE_ACCOUNT}
```

### Issue: "Service account key file not found" in Docker

**Cause:** File path is incorrect or not mounted.

**Solution:**

```bash
# Verify the key file exists locally
ls -la ~/gcp-keys/server-status-monitor-key.json

# Use absolute path in docker run
docker run -v /Users/yourusername/gcp-keys/server-status-monitor-key.json:/app/certs/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  ...
```

### Issue: Cloud Run service can't access GCS

**Cause:** Service account not attached or lacks permissions.

**Solution:**

```bash
# Check current service account
gcloud run services describe server-status-monitor \
  --region us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"

# Update service account
gcloud run services update server-status-monitor \
  --region us-central1 \
  --service-account=server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Grant permissions
gsutil iam ch serviceAccount:server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com:objectViewer \
  gs://your-bucket-name
```

### Issue: "Invalid credentials" error

**Cause:** Service account key is expired or revoked.

**Solution:**

```bash
# List existing keys
gcloud iam service-accounts keys list \
  --iam-account=server-status-monitor-local@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Delete old key
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=server-status-monitor-local@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Create new key
gcloud iam service-accounts keys create ~/gcp-keys/new-key.json \
  --iam-account=server-status-monitor-local@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

---

## Security Best Practices

### ✅ DO

- Use dedicated service accounts with minimal permissions
- Grant bucket-specific access instead of project-wide
- Use Cloud Run's automatic authentication in production
- Store service account keys securely (never commit to git)
- Rotate service account keys regularly
- Use Secret Manager for sensitive values in Cloud Run

### ❌ DON'T

- Don't commit service account keys to version control
- Don't build credentials into Docker images
- Don't use personal user credentials in production
- Don't grant overly broad permissions (e.g., `roles/owner`)
- Don't share service account keys across environments
- Don't set `GOOGLE_APPLICATION_CREDENTIALS` in Cloud Run

---

## Quick Reference

### Cloud Run Deployment

```bash
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --service-account=server-status-monitor@PROJECT_ID.iam.gserviceaccount.com
```

### Local Docker Testing

```bash
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v ~/gcp-keys/key.json:/app/certs/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  server-status-monitor
```

### Local Development

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/gcp-keys/key.json
python process_server_status_entities.py
```

---

## Additional Resources

- [Google Cloud Authentication Overview](https://cloud.google.com/docs/authentication)
- [Service Accounts Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [Cloud Run Authentication](https://cloud.google.com/run/docs/authenticating/service-to-service)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
