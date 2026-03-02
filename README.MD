# Finacle Server Status

A Python-based monitoring system that tracks server/service status, uploads data to Google Cloud Storage, and integrates with Instana for dashboard visualization and alerting.

## Overview

This project consists of two main components:

1. **storebucket.py** - Continuously uploads service status files to Google Cloud Storage. This is for testing
2. **processServerStatus.py** - Reads status data from GCS, updates Instana dashboards, and manages service alerts/events

## Features

- 📊 **Real-time Service Monitoring** - Tracks service status (Up/Down) with process and port information
- ☁️ **Cloud Storage Integration** - Uploads status data to Google Cloud Storage buckets
- 📈 **Instana Dashboard Updates** - Automatically updates custom Instana dashboards with formatted service status tables
- 🚨 **Event Management** - Creates and closes Instana events based on service status changes
- 🔄 **Continuous Monitoring** - Runs in a loop to provide ongoing monitoring capabilities
- 🌐 **REST API** - Exposes endpoints for manual triggering and health checks

## Prerequisites

- Python 3.x
- Google Cloud Platform account with Storage API enabled
- Instana monitoring instance with API access
- Required Python packages:
  - `google-cloud-storage`
  - `requests`
  - `flask`
  - `python-dotenv`

## Installation

1. Clone this repository
2. Install required dependencies:
   ```bash
   pip install google-cloud-storage requests flask python-dotenv
   ```
3. Set up Google Cloud credentials (see Configuration section)
4. Configure environment variables in `.env` file

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Google Cloud Storage
BUCKET_NAME=your-bucket-name
BUCKET_FILE_PATH=serviceChk_finprodcoredc2.txt
PROJECT_NAME=your-gcp-project-id

# Instana Configuration
BASE_URL=https://your-instance.instana.io
API_TOKEN=your-instana-api-token
DASHBOARD_NAME=Finacle Monitor
WIDGET_NAME=finprodcoredc2 Service Status
AGENT_URL=http://your-agent-url:4001
EVENT_DURATION=3600000
FINACLE_HOST=finprodcoredc2
```

### Google Cloud Authentication!

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your service account key file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

## Usage

### Upload Service Status to GCS

Run the storage uploader to continuously upload status files:

```bash
python store_demo_server_status_file.py
```

This script will upload `serviceChk_finprodcoredc2.txt` to the configured GCS bucket every 5 seconds.

### Update Instana Dashboard

Run the dashboard updater to process status data and update Instana:

```bash
python process_server_status.py
```

This script will:

- Read the Text file from GCS
- Parse service status information
- Update the Instana dashboard with a formatted markdown table
- Create events for services that are down
- Close events for services that are back up

### REST API Endpoints

When running as a Flask application, the following endpoints are available:

- `GET /hello?name=World` - Simple health check endpoint
- `GET /api/v1/service/status` - Manually trigger dashboard update and return results

Start the Flask server:

```bash
python process_server_status.py
```

The server will run on `http://0.0.0.0:5555`

## File Structure

- `store_demo_server_status_file.py` - GCS upload script
- `process_server_status.py` - Main dashboard update and event management script
- `test/demo/serviceChk_finprodcoredc2.txt` - Service status input file
- `.env` - Environment configuration (not tracked in git)

## Service Status Format

The service status file should contain the following columns:

| Service Name | Status | PPID  | Limo Port |
| ------------ | ------ | ----- | --------- |
| ServiceA     | Up     | 12345 | 8080      |
| ServiceB     | Down   | 12346 | 8081      |

Services marked as "Down" or "Offline" will be highlighted in bold on the dashboard and trigger critical events.

## Event Management

The system automatically manages Instana events:

- **Service Down**: Creates a severity 10 (critical) event with suffix "is Offline"
- **Service Up**: Creates a severity -1 (resolution) event with suffix "is Online"
- **Event Lifecycle**: Automatically closes stale events when service status changes

## TODO

- [ ] Only delete existing alerts if close to expiration
- [ ] Adjust start time of new events to match old ones when replacing
- [ ] Add comprehensive error handling
- [ ] Run as a scheduled task on Cloud Run
- [ ] Add structured logging
- [ ] Improve event state change detection

## License

This project is for internal use and demonstration purposes.

## Support

For issues or questions, please contact the development team.
