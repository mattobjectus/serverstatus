# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY process_server_status_entities.py .

# Copy setup files (needed for entity type definitions)
COPY setup/ ./setup/

# Create directory for certificates (will be mounted or provided via env)
RUN mkdir -p /app/certs

# Set environment variables for Cloud Run
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run the application as an endpoint
CMD ["python", "process_server_status_entities.py"]
