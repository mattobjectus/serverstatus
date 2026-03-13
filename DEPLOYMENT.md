# Cloud Run Deployment Guide

This guide explains how to deploy the `process_server_status_entities.py` application to Google Cloud Run using Docker.

## Prerequisites

1. **Google Cloud SDK** installed and configured

   ```bash
   gcloud --version
   ```

2. **Docker** installed locally (for testing)

   ```bash
   docker --version
   ```

3. **GCP Project** with the following APIs enabled:
   - Cloud Run API
   - Container Registry API (or Artifact Registry)
   - Cloud Storage API
   - Cloud Build API (optional, for automated builds)

4. **IAM Permissions**: Your service account needs:
   - `roles/run.admin` - Deploy to Cloud Run
   - `roles/storage.objectViewer` - Read from GCS bucket
   - `roles/iam.serviceAccountUser` - Act as service account

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.cloudrun.example .env.cloudrun
# Edit .env.cloudrun with your actual values
```

**Important Cloud Run Settings:**

- Set `AS_ENDPOINT=True` to run as a Flask web service
- Set `LOOP_PAUSE_IN_SECONDS=-1` for single execution per request
- Remove or comment out `GOOGLE_APPLICATION_CREDENTIALS` (Cloud Run uses Workload Identity)

### 2. Build Docker Image Locally (Optional Testing)

```bash
# Build the image
docker build -t server-status-monitor .

# Test locally with environment file
docker run -p 8080:8080 --env-file .env.cloudrun server-status-monitor

# OR test with GCP credentials mounted (for local testing with GCS access)
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v /path/to/your/service-account-key.json:/app/certs/credentials.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  server-status-monitor

# Test the endpoint
curl http://localhost:8080/api/v1/service/status
```

**Note:** When running locally in Docker, you need to provide GCP credentials. See the "Local Docker Testing with GCP Credentials" section below for details.

”∏

### 3. Deploy to Cloud Run

#### Option A: Using gcloud CLI (Recommended)

```bash
# Set your GCP project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy in one command
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 300 \
  --set-env-vars "AS_ENDPOINT=True,LOOP_PAUSE_IN_SECONDS=-1" \
  --set-env-vars "BUCKET_NAME=your-bucket-name" \
  --set-env-vars "BUCKET_FILE_PATH=serviceChk_finprodcoredc2.txt" \
  --set-env-vars "PROJECT_NAME=your-project-id" \
  --set-env-vars "BASE_URL=https://your-instance.instana.io" \
  --set-env-vars "API_TOKEN=your-api-token" \
  --set-env-vars "DASHBOARD_NAME=Finacle Monitor" \
  --set-env-vars "WIDGET_NAME=Service Status" \
  --set-env-vars "FINACLE_HOST=your-host" \
  --set-env-vars "AGENT_URL=http://your-agent:4001" \
  --set-env-vars "OTLP_AGENT_URL=http://your-agent:4000" \
  --set-env-vars "EVENT_DURATION=180000" \
  --set-env-vars "MAX_SCHEDULED_INTERVAL_IN_MILLIS=60000"
```

#### Option B: Using Cloud Build

```bash
# Submit build to Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Or use the included script
./deploy.sh
```

#### Option C: Manual Build and Push

```bash
# Set variables
PROJECT_ID=$(gcloud config get-value project)
IMAGE_NAME=gcr.io/$PROJECT_ID/server-status-monitor

# Build and tag
docker build -t $IMAGE_NAME .

# Push to Container Registry
docker push $IMAGE_NAME

# Deploy to Cloud Run
gcloud run deploy server-status-monitor \
  --image $IMAGE_NAME \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080
```

### 4. Configure Environment Variables in Cloud Run

After deployment, set environment variables via the Cloud Console or CLI:

```bash
gcloud run services update server-status-monitor \
  --region us-central1 \
  --update-env-vars "BUCKET_NAME=your-bucket-name,PROJECT_NAME=your-project-id"
```

Or use the Cloud Console:

1. Go to Cloud Run → Select your service
2. Click "Edit & Deploy New Revision"
3. Go to "Variables & Secrets" tab
4. Add environment variables from `.env.cloudrun.example`

### 5. Set Up Service Account (Recommended)

Create a dedicated service account with minimal permissions:

```bash
# Create service account
gcloud iam service-accounts create server-status-monitor \
  --display-name="Server Status Monitor"

# Grant Storage Object Viewer role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Attach to Cloud Run service
gcloud run services update server-status-monitor \
  --region us-central1 \
  --service-account=server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## Testing the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe server-status-monitor \
  --region us-central1 \
  --format 'value(status.url)')

# Test the endpoint
curl $SERVICE_URL/api/v1/service/status
```

## Scheduled Execution with Cloud Scheduler

To run the service on a schedule:

```bash
# Create a Cloud Scheduler job
gcloud scheduler jobs create http server-status-monitor-job \
  --schedule="*/5 * * * *" \
  --uri="$SERVICE_URL/api/v1/service/status" \
  --http-method=GET \
  --location=us-central1 \
  --description="Run server status monitor every 5 minutes"
```

## Local Docker Testing with GCP Credentials

When running the Docker container locally (not on Cloud Run), you need to provide Google Cloud credentials for accessing GCS buckets.

### Option 1: Mount Service Account Key (Recommended for Local Testing)

```bash
# 1. Download your service account key from GCP Console
# Go to: IAM & Admin → Service Accounts → Select account → Keys → Add Key → Create new key (JSON)

# 2. Save the key file locally (e.g., ~/gcp-keys/service-account-key.json)

# 3. Run Docker with mounted credentials
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v ~/gcp-keys/service-account-key.json:/app/certs/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json \
  server-status-monitor
```

### Option 2: Use Application Default Credentials (ADC)

```bash
# 1. Authenticate with gcloud
gcloud auth application-default login

# 2. Mount the ADC credentials directory
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  server-status-monitor
```

### Option 3: Build Credentials into Image (NOT RECOMMENDED - Security Risk)

**Warning:** Only use this for testing in isolated environments. Never commit credentials to version control.

```dockerfile
# Add to Dockerfile (temporary testing only)
COPY /path/to/service-account-key.json /app/certs/credentials.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/certs/credentials.json
```

### Option 4: Pass Credentials as Environment Variable (NOT RECOMMENDED)

```bash
# Read the JSON key and pass as env var (not secure)
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -e GOOGLE_APPLICATION_CREDENTIALS_JSON="$(cat ~/gcp-keys/service-account-key.json)" \
  server-status-monitor
```

**Note:** This requires modifying the Python code to write the JSON to a file at runtime.

### Testing Without GCS (Local File Override)

For testing without GCS access, use the local file override:

```bash
# In .env.cloudrun, set:
USE_LOCAL_FILE_INSTEAD_OF_BUCKET_PATH=test/demo/serviceChk_finprodcoredc.txt

# Copy test files into the container
docker run -p 8080:8080 \
  --env-file .env.cloudrun \
  -v $(pwd)/test:/app/test:ro \
  server-status-monitor
```

## Cloud Run Authentication (Production)

When deployed to Cloud Run, authentication is handled automatically through **Workload Identity** or the attached service account. No manual credential configuration is needed.

### Automatic Authentication in Cloud Run

Cloud Run automatically provides credentials to your application through:

1. **Default Service Account**: Uses the Compute Engine default service account
2. **Custom Service Account**: Attach a dedicated service account with minimal permissions

```bash
# Deploy with custom service account
gcloud run deploy server-status-monitor \
  --source . \
  --region us-central1 \
  --service-account=server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### Required IAM Permissions

The service account needs these roles:

```bash
# Storage Object Viewer - to read from GCS bucket
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Or grant access to specific bucket only
gsutil iam ch serviceAccount:server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com:objectViewer \
  gs://your-bucket-name
```

### Verify Authentication in Cloud Run

```bash
# Check service account attached to Cloud Run service
gcloud run services describe server-status-monitor \
  --region us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"

# View logs to check for authentication errors
gcloud run services logs read server-status-monitor \
  --region us-central1 \
  --limit 50
```

## Monitoring and Logs

View logs:

```bash
gcloud run services logs read server-status-monitor \
  --region us-central1 \
  --limit 50
```

Or use Cloud Console:

1. Go to Cloud Run → Select your service
2. Click "Logs" tab

## Troubleshooting

### Issue: Authentication errors with GCS

**Solution**: Ensure the Cloud Run service account has `roles/storage.objectViewer` permission on the bucket.

```bash
gsutil iam ch serviceAccount:server-status-monitor@YOUR_PROJECT_ID.iam.gserviceaccount.com:objectViewer \
  gs://your-bucket-name
```

### Issue: Container fails to start

**Solution**: Check logs for errors:

```bash
gcloud run services logs read server-status-monitor --region us-central1
```

Common issues:

- Missing required environment variables
- Invalid API tokens
- Network connectivity to Instana agent

### Issue: Timeout errors

**Solution**: Increase timeout:

```bash
gcloud run services update server-status-monitor \
  --region us-central1 \
  --timeout=300
```

### Issue: Memory errors

**Solution**: Increase memory allocation:

```bash
gcloud run services update server-status-monitor \
  --region us-central1 \
  --memory=1Gi
```

## Configuration Options

### Running Modes

The application supports three modes via environment variables:

1. **Endpoint Mode** (Recommended for Cloud Run)

   ```
   AS_ENDPOINT=True
   LOOP_PAUSE_IN_SECONDS=-1
   ```

   Runs as a Flask web service, processes on each HTTP request

2. **Loop Mode** (Not recommended for Cloud Run)

   ```
   AS_ENDPOINT=False
   LOOP_PAUSE_IN_SECONDS=30
   ```

   Continuously loops with pause between iterations

3. **Single Execution Mode**
   ```
   AS_ENDPOINT=False
   LOOP_PAUSE_IN_SECONDS=-1
   ```
   Runs once and exits

### Environment Variables Reference

| Variable                                | Required | Description           | Example                   |
| --------------------------------------- | -------- | --------------------- | ------------------------- |
| `AS_ENDPOINT`                           | Yes      | Run as Flask endpoint | `True`                    |
| `BUCKET_NAME`                           | Yes      | GCS bucket name       | `antarsia_test`           |
| `BUCKET_FILE_PATH`                      | Yes      | File path in bucket   | `serviceChk.txt`          |
| `PROJECT_NAME`                          | Yes      | GCP project ID        | `my-project`              |
| `BASE_URL`                              | Yes      | Instana instance URL  | `https://xxx.instana.io`  |
| `API_TOKEN`                             | Yes      | Instana API token     | `abc123...`               |
| `DASHBOARD_NAME`                        | Yes      | Dashboard name        | `Finacle Monitor`         |
| `WIDGET_NAME`                           | Yes      | Widget name           | `Service Status`          |
| `FINACLE_HOST`                          | Yes      | Finacle hostname      | `finprodcoredc2`          |
| `AGENT_URL`                             | Yes      | Instana agent URL     | `http://172.16.0.70:4001` |
| `OTLP_AGENT_URL`                        | Yes      | OTLP agent URL        | `http://172.16.0.70:4000` |
| `EVENT_DURATION`                        | No       | Event duration (ms)   | `180000`                  |
| `MAX_SCHEDULED_INTERVAL_IN_MILLIS`      | No       | Scheduler interval    | `60000`                   |
| `LOOP_PAUSE_IN_SECONDS`                 | No       | Loop pause time       | `-1`                      |
| `USE_LOCAL_FILE_INSTEAD_OF_BUCKET_PATH` | No       | Local file override   | (empty)                   |
| `SKIP_EVENT_GENERATION`                 | No       | Skip events           | `False`                   |

## Cost Optimization

Cloud Run charges based on:

- Request count
- CPU and memory usage
- Execution time

To optimize costs:

1. Use Cloud Scheduler to control execution frequency
2. Set appropriate memory limits (512Mi is usually sufficient)
3. Set reasonable timeout values (60-300 seconds)
4. Use `--min-instances=0` to scale to zero when idle

## Security Best Practices

1. **Use Secret Manager** for sensitive values:

   ```bash
   echo -n "your-api-token" | gcloud secrets create instana-api-token --data-file=-

   gcloud run services update server-status-monitor \
     --region us-central1 \
     --update-secrets=API_TOKEN=instana-api-token:latest
   ```

2. **Restrict access** with IAM:

   ```bash
   gcloud run services remove-iam-policy-binding server-status-monitor \
     --region us-central1 \
     --member="allUsers" \
     --role="roles/run.invoker"
   ```

3. **Use VPC Connector** for private network access to Instana agents

4. **Enable Binary Authorization** for container image verification

## Cleanup

To delete the Cloud Run service:

```bash
gcloud run services delete server-status-monitor --region us-central1
```

To delete the container images:

```bash
gcloud container images delete gcr.io/YOUR_PROJECT_ID/server-status-monitor --quiet
```

## Support

For issues or questions:

- Check Cloud Run logs: `gcloud run services logs read server-status-monitor`
- Review application README.MD for configuration details
- Verify all environment variables are set correctly
